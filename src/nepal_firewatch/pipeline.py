from __future__ import annotations
from .config import SETTINGS
from .firms import fetch_all, load_demo
from .normalize import normalize
from .boundaries import BoundaryResolver, download_boundaries
from .ward import BipadWardResolver
from . import db
from .events import ingest
from .cards import make_card
from .export import export_all, write_health
from .utils import ensure_dirs


def _attach_locations(records: list[dict], resolver: BoundaryResolver) -> list[dict]:
    out = []
    for r in records:
        loc = resolver.resolve(r["latitude"], r["longitude"])
        if loc is None:
            # FIRMS bounding box includes a small area outside Nepal.
            continue
        r.update(loc)
        out.append(r)
    return out


def _event_dict(con, event_id: str) -> dict:
    return dict(
        con.execute(
            "SELECT * FROM events WHERE event_id=?", (event_id,)
        ).fetchone()
    )


def _event_detections(con, event_id: str) -> list[dict]:
    return [
        dict(r)
        for r in con.execute(
            "SELECT * FROM detections WHERE event_id=? ORDER BY observed_utc",
            (event_id,),
        ).fetchall()
    ]


def run_pipeline(demo: bool = False) -> dict:
    s = SETTINGS
    ensure_dirs(s.db_path.parent, s.cards_dir, s.map_data_dir)

    if demo:
        raw = load_demo(s.demo_csv)
        boundary_path = s.demo_boundary_path
        db_path = s.db_path.parent / "firewatch_demo.sqlite"
        mode = "demo"
        ward_resolver = None
    else:
        raw = fetch_all(s.firms_map_key, s.sources, s.bbox, s.lookback_days)
        boundary_path = download_boundaries(s.boundary_path, s.boundary_url)
        db_path = s.db_path
        mode = "live"
        ward_resolver = BipadWardResolver(s.db_path.parent / "cache" / "bipad_ward_lookup.json")

    fetched = len(raw)
    records = normalize(raw, s.min_confidence)
    records = _attach_locations(records, BoundaryResolver(boundary_path))

    con = db.connect(db_path)
    try:
        new_detections, new_events, touched = ingest(
            con, records, s.cluster_km, s.cluster_hours
        )

        for event_id in sorted(touched):
            event = _event_dict(con, event_id)
            ward = None
            if ward_resolver is not None:
                ward = ward_resolver.resolve(event["centroid_lat"], event["centroid_lon"])
                db.set_event_ward(con, event_id, ward)
                event = _event_dict(con, event_id)
                if ward:
                    # Keep any geometry transient for card rendering; it is not stored in SQLite.
                    event.update(ward)
            detections = _event_detections(con, event_id)
            rel = f"cards/{event_id}.png"
            make_card(event, detections, s.docs_dir / rel, boundary_path=boundary_path)
            db.set_card_path(con, event_id, rel)

        db.record_run(con, fetched, new_detections, new_events, mode)
        con.commit()

        export_all(con, s.map_data_dir)
        health = write_health(
            con,
            s.map_data_dir,
            fetched=fetched,
            new_detections=new_detections,
            new_events=new_events,
            mode=mode,
        )
    finally:
        con.close()

    return {
        "fetched": fetched,
        "new_detections": new_detections,
        "new_events": new_events,
        "health": health,
    }

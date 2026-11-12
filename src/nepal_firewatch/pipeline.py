from __future__ import annotations
from pathlib import Path
from .config import SETTINGS
from .firms import fetch_all, load_demo
from .normalize import normalize
from .boundaries import BoundaryResolver, download_boundaries
from . import db
from .events import ingest
from .cards import make_card
from .export import export_all
from .utils import ensure_dirs


def _attach_locations(records: list[dict], resolver: BoundaryResolver) -> list[dict]:
    out = []
    for r in records:
        loc = resolver.resolve(r["latitude"], r["longitude"])
        if loc is None:
            # FIRMS bounding box includes a small area outside Nepal; discard points not inside Nepal polygons.
            continue
        r.update(loc)
        out.append(r)
    return out


def _event_dict(con, event_id: str) -> dict:
    return dict(con.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone())


def _event_detections(con, event_id: str) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT * FROM detections WHERE event_id=? ORDER BY observed_utc", (event_id,)).fetchall()]


def run_pipeline(demo: bool = False) -> dict:
    s = SETTINGS
    ensure_dirs(s.db_path.parent, s.cards_dir, s.map_data_dir)

    if demo:
        raw = load_demo(s.demo_csv)
        boundary_path = s.demo_boundary_path
        db_path = s.db_path.parent / "firewatch_demo.sqlite"
    else:
        raw = fetch_all(s.firms_map_key, s.sources, s.bbox, s.lookback_days)
        boundary_path = download_boundaries(s.boundary_path, s.boundary_url)
        db_path = s.db_path

    fetched = len(raw)
    records = normalize(raw, s.min_confidence)
    records = _attach_locations(records, BoundaryResolver(boundary_path))
    con = db.connect(db_path)
    new_detections, new_events, touched = ingest(con, records, s.cluster_km, s.cluster_hours)

    for event_id in sorted(touched):
        event = _event_dict(con, event_id)
        detections = _event_detections(con, event_id)
        rel = f"cards/{event_id}.png"
        make_card(event, detections, s.docs_dir / rel)
        db.set_card_path(con, event_id, rel)
    con.commit()
    export_all(con, s.map_data_dir)
    db.record_run(con, fetched, new_detections, new_events, "demo" if demo else "live")
    con.commit()
    con.close()
    return {"fetched": fetched, "new_detections": new_detections, "new_events": new_events}

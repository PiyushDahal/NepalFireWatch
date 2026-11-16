from __future__ import annotations
import json
from pathlib import Path
from .utils import utcnow_iso


def _fc(features):
    return {"type": "FeatureCollection", "features": features}


def export_all(con, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    events = con.execute("SELECT * FROM events ORDER BY last_seen_utc DESC").fetchall()
    dets = con.execute("SELECT * FROM detections ORDER BY observed_utc DESC").fetchall()

    event_features = []
    for r in events:
        p = dict(r)
        event_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [p.pop("centroid_lon"), p.pop("centroid_lat")],
            },
            "properties": p,
        })

    det_features = []
    for r in dets:
        p = dict(r)
        det_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [p.pop("longitude"), p.pop("latitude")],
            },
            "properties": p,
        })

    (out_dir / "events.geojson").write_text(
        json.dumps(_fc(event_features), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "detections.geojson").write_text(
        json.dumps(_fc(det_features), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lifecycle_counts = {}
    for r in events:
        state = str(r["lifecycle_state"] or "NEW").upper()
        lifecycle_counts[state] = lifecycle_counts.get(state, 0) + 1
    open_event_count = sum(n for state, n in lifecycle_counts.items() if state != "CLOSED")
    summary = {
        "generated_utc": utcnow_iso(),
        "event_count": len(event_features),
        "open_event_count": open_event_count,
        "lifecycle_counts": lifecycle_counts,
        "detection_count": len(det_features),
        "latest_event_utc": events[0]["last_seen_utc"] if events else None,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


def write_health(
    con,
    out_dir: Path,
    fetched: int,
    new_detections: int,
    new_events: int,
    mode: str,
    status: str = "success",
) -> dict:
    """Write a small public health record used by the web dashboard."""
    out_dir.mkdir(parents=True, exist_ok=True)

    database_detections = con.execute(
        "SELECT COUNT(*) FROM detections"
    ).fetchone()[0]
    database_events = con.execute(
        "SELECT COUNT(*) FROM events"
    ).fetchone()[0]
    database_open_events = con.execute(
        "SELECT COUNT(*) FROM events WHERE lifecycle_state != 'CLOSED'"
    ).fetchone()[0]

    health = {
        "last_run_utc": utcnow_iso(),
        "status": status,
        "mode": mode,
        "firms_records_fetched": fetched,
        "new_detections": new_detections,
        "new_events": new_events,
        "database_detections": database_detections,
        "database_events": database_events,
        "database_open_events": database_open_events,
    }

    (out_dir / "health.json").write_text(
        json.dumps(health, indent=2), encoding="utf-8"
    )
    return health

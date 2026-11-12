from __future__ import annotations
import json
from pathlib import Path
from .utils import utcnow_iso


def _fc(features):
    return {"type":"FeatureCollection","features":features}


def export_all(con, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    events = con.execute("SELECT * FROM events ORDER BY last_seen_utc DESC").fetchall()
    dets = con.execute("SELECT * FROM detections ORDER BY observed_utc DESC").fetchall()

    event_features = []
    for r in events:
        p = dict(r)
        event_features.append({
            "type":"Feature",
            "geometry":{"type":"Point","coordinates":[p.pop("centroid_lon"),p.pop("centroid_lat")]},
            "properties":p,
        })
    det_features = []
    for r in dets:
        p = dict(r)
        det_features.append({
            "type":"Feature",
            "geometry":{"type":"Point","coordinates":[p.pop("longitude"),p.pop("latitude")]},
            "properties":p,
        })
    (out_dir/"events.geojson").write_text(json.dumps(_fc(event_features), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir/"detections.geojson").write_text(json.dumps(_fc(det_features), ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "generated_utc": utcnow_iso(),
        "event_count": len(event_features),
        "detection_count": len(det_features),
        "latest_event_utc": events[0]["last_seen_utc"] if events else None,
    }
    (out_dir/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

from __future__ import annotations
from datetime import datetime, timezone
from .utils import haversine_km
from . import db


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _event_id(observed_utc: str, seq: int) -> str:
    d = _dt(observed_utc).strftime("%Y%m%d")
    return f"NFW-{d}-{seq:03d}"


def _next_seq(con, observed_utc: str) -> int:
    prefix = f"NFW-{_dt(observed_utc).strftime('%Y%m%d')}-"
    rows = con.execute("SELECT event_id FROM events WHERE event_id LIKE ?", (prefix + "%",)).fetchall()
    nums = []
    for r in rows:
        try: nums.append(int(r["event_id"].split("-")[-1]))
        except Exception: pass
    return (max(nums) if nums else 0) + 1


def find_matching_event(con, d: dict, cluster_km: float, cluster_hours: float):
    rows = con.execute("SELECT * FROM events WHERE status='active'").fetchall()
    t = _dt(d["observed_utc"])
    best = None
    best_dist = float("inf")
    for e in rows:
        hours = abs((t - _dt(e["last_seen_utc"])).total_seconds()) / 3600.0
        if hours > cluster_hours:
            continue
        dist = haversine_km(d["latitude"], d["longitude"], e["centroid_lat"], e["centroid_lon"])
        if dist <= cluster_km and dist < best_dist:
            best, best_dist = e, dist
    return best


def ingest(con, detections: list[dict], cluster_km: float, cluster_hours: float) -> tuple[int, int, set[str]]:
    new_det = 0
    new_evt = 0
    touched: set[str] = set()
    for d in sorted(detections, key=lambda x: x["observed_utc"]):
        if db.detection_exists(con, d["detection_id"]):
            continue
        match = find_matching_event(con, d, cluster_km, cluster_hours)
        if match is None:
            event_id = _event_id(d["observed_utc"], _next_seq(con, d["observed_utc"]))
            db.insert_event(con, {
                "event_id": event_id,
                "first_seen_utc": d["observed_utc"], "last_seen_utc": d["observed_utc"],
                "centroid_lat": d["latitude"], "centroid_lon": d["longitude"],
                "max_frp": d.get("frp"), "province": d.get("province"),
                "district": d.get("district"), "local_name": d.get("local_name"),
                "local_type": d.get("local_type"),
            })
            new_evt += 1
        else:
            event_id = match["event_id"]
        db.insert_detection(con, d, event_id)
        db.refresh_event(con, event_id)
        touched.add(event_id)
        new_det += 1
    con.commit()
    return new_det, new_evt, touched

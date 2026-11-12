from __future__ import annotations
from datetime import datetime, timezone
from math import radians, sin, cos, asin, sqrt
from pathlib import Path
import hashlib


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * r * asin(sqrt(a))


def detection_uid(source: str, lat: float, lon: float, observed_utc: str, frp: float | None) -> str:
    raw = f"{source}|{lat:.5f}|{lon:.5f}|{observed_utc}|{'' if frp is None else round(frp, 2)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)

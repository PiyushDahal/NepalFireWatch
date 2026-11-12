from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import math
import pandas as pd
from .utils import detection_uid

NPT = ZoneInfo("Asia/Kathmandu")

CONF_RANK = {
    "low": 0, "l": 0,
    "nominal": 1, "n": 1,
    "high": 2, "h": 2,
}


def _confidence_label(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "unknown"
    s = str(value).strip().lower()
    if s in ("l", "low"): return "low"
    if s in ("n", "nominal"): return "nominal"
    if s in ("h", "high"): return "high"
    try:
        x = float(s)
        if x < 30: return "low"
        if x < 80: return "nominal"
        return "high"
    except ValueError:
        return s


def _observed(acq_date, acq_time):
    t = str(int(float(acq_time))).zfill(4)
    dt = datetime.strptime(f"{acq_date} {t}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
    return dt


def normalize(df: pd.DataFrame, min_confidence: str = "nominal") -> list[dict]:
    if df.empty:
        return []
    required = {"latitude", "longitude", "acq_date", "acq_time"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"FIRMS data missing required columns: {sorted(missing)}")

    min_rank = CONF_RANK.get(min_confidence.lower(), 1)
    out = []
    for _, row in df.iterrows():
        confidence = _confidence_label(row.get("confidence"))
        if CONF_RANK.get(confidence, 1) < min_rank:
            continue
        lat, lon = float(row["latitude"]), float(row["longitude"])
        # Nepal bounding guard; final location check occurs against local-level polygons.
        if not (26.2 <= lat <= 30.6 and 79.9 <= lon <= 88.4):
            continue
        dt_utc = _observed(row["acq_date"], row["acq_time"])
        dt_npt = dt_utc.astimezone(NPT)
        frp = None if pd.isna(row.get("frp")) else float(row.get("frp"))
        source = str(row.get("source", row.get("satellite", "VIIRS")))
        record = {
            "source": source,
            "satellite": str(row.get("satellite", "")),
            "instrument": str(row.get("instrument", "VIIRS")),
            "latitude": lat,
            "longitude": lon,
            "observed_utc": dt_utc.isoformat(timespec="seconds"),
            "observed_npt": dt_npt.isoformat(timespec="seconds"),
            "confidence": confidence,
            "frp": frp,
            "daynight": str(row.get("daynight", "")),
            "bright_ti4": None if pd.isna(row.get("bright_ti4")) else float(row.get("bright_ti4")),
            "bright_ti5": None if pd.isna(row.get("bright_ti5")) else float(row.get("bright_ti5")),
        }
        record["detection_id"] = detection_uid(source, lat, lon, record["observed_utc"], frp)
        out.append(record)
    return out

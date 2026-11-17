from __future__ import annotations

from datetime import datetime, timezone


CLASS_LABELS = {
    "anomaly": "Satellite thermal anomaly",
    "probable": "Probable fire signal",
    "high": "High-evidence persistent thermal event",
}

OVERPASS_GAP_MINUTES = 15


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _count_overpasses(detections: list[dict], gap_minutes: int = OVERPASS_GAP_MINUTES) -> int:
    """Count independent satellite overpasses rather than raw hot pixels.

    Detections from the same satellite are treated as one overpass when the time gap
    between consecutive detections is <= gap_minutes. Detections from different
    satellites are always counted independently.
    """
    by_satellite: dict[str, list[datetime]] = {}
    for d in detections:
        sat = str(d.get("satellite") or "UNKNOWN").strip() or "UNKNOWN"
        observed = d.get("observed_utc")
        if observed:
            by_satellite.setdefault(sat, []).append(_dt(str(observed)))

    gap_seconds = gap_minutes * 60
    count = 0
    for times in by_satellite.values():
        if not times:
            continue
        times = sorted(times)
        count += 1
        previous = times[0]
        for current in times[1:]:
            if (current - previous).total_seconds() > gap_seconds:
                count += 1
            previous = current
    return count


def classify_event(detections: list[dict]) -> dict:
    """Classify one clustered event using transparent, additive evidence rules.

    This is an engineering evidence score, not a calibrated probability of wildfire.
    Raw VIIRS pixels from one satellite overpass are not treated as independent
    corroborating observations.
    """
    if not detections:
        return {
            "evidence_score": 0,
            "confidence_class": "anomaly",
            "confidence_label": CLASS_LABELS["anomaly"],
            "satellite_count": 0,
            "overpass_count": 0,
            "duration_hours": 0.0,
            "confidence_reasons": [],
        }

    score = 0
    reasons: list[str] = []

    confidences = {
        str(d.get("confidence") or "").strip().lower() for d in detections
    }
    if "high" in confidences or "h" in confidences:
        score += 1
        reasons.append("At least one VIIRS detection has high FIRMS confidence (+1)")

    frps = [float(d["frp"]) for d in detections if d.get("frp") is not None]
    max_frp = max(frps) if frps else None
    if max_frp is not None and max_frp >= 50.0:
        score += 2
        reasons.append(f"Maximum FRP is {max_frp:.1f} MW (>=50 MW; +2)")
    elif max_frp is not None and max_frp >= 20.0:
        score += 1
        reasons.append(f"Maximum FRP is {max_frp:.1f} MW (>=20 MW; +1)")

    n = len(detections)
    overpass_count = _count_overpasses(detections)

    # Multiple pixels within a single overpass can indicate a spatially larger thermal
    # feature, but they are weaker evidence than an independent repeat observation.
    if n >= 3 and overpass_count == 1:
        score += 1
        reasons.append(f"Single overpass contains {n} VIIRS hot pixels (>=3; +1)")

    if overpass_count >= 3:
        score += 3
        reasons.append(f"Event is detected in {overpass_count} independent overpasses (>=3; +3)")
    elif overpass_count >= 2:
        score += 2
        reasons.append(f"Event is detected in {overpass_count} independent overpasses (>=2; +2)")

    satellites = {
        str(d.get("satellite") or "").strip()
        for d in detections
        if str(d.get("satellite") or "").strip()
    }
    satellite_count = len(satellites)
    if satellite_count >= 2:
        score += 1
        reasons.append(f"Detected by {satellite_count} satellites (+1)")

    times = sorted(_dt(str(d["observed_utc"])) for d in detections if d.get("observed_utc"))
    duration_hours = 0.0
    if len(times) >= 2:
        duration_hours = max(0.0, (times[-1] - times[0]).total_seconds() / 3600.0)
    if duration_hours >= 6.0:
        score += 2
        reasons.append(f"Thermal activity spans {duration_hours:.1f} hours (>=6 h; +2)")
    elif duration_hours >= 1.0:
        score += 1
        reasons.append(f"Thermal activity spans {duration_hours:.1f} hours (>=1 h; +1)")

    if score >= 4:
        confidence_class = "high"
    elif score >= 2:
        confidence_class = "probable"
    else:
        confidence_class = "anomaly"

    return {
        "evidence_score": int(score),
        "confidence_class": confidence_class,
        "confidence_label": CLASS_LABELS[confidence_class],
        "satellite_count": int(satellite_count),
        "overpass_count": int(overpass_count),
        "duration_hours": round(float(duration_hours), 3),
        "confidence_reasons": reasons,
    }

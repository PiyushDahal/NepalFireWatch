from __future__ import annotations

from datetime import datetime, timezone


CLASS_LABELS = {
    "anomaly": "Satellite thermal anomaly",
    "probable": "Probable fire signal",
    "high": "High-evidence persistent thermal event",
}


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def classify_event(detections: list[dict]) -> dict:
    """Classify one clustered event using transparent, additive evidence rules.

    This is an engineering evidence score, not a calibrated probability of wildfire.
    The rules intentionally require corroborating evidence before a public event is
    labelled probable or high-confidence.
    """
    if not detections:
        return {
            "evidence_score": 0,
            "confidence_class": "anomaly",
            "confidence_label": CLASS_LABELS["anomaly"],
            "satellite_count": 0,
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
    if n >= 4:
        score += 3
        reasons.append(f"Event has {n} VIIRS detections (>=4; +3)")
    elif n >= 2:
        score += 2
        reasons.append(f"Event has {n} VIIRS detections (>=2; +2)")

    satellites = {
        str(d.get("satellite") or "").strip()
        for d in detections
        if str(d.get("satellite") or "").strip()
    }
    satellite_count = len(satellites)
    if satellite_count >= 2:
        score += 1
        reasons.append(f"Detected by {satellite_count} satellites (+1)")

    times = sorted(_dt(str(d["observed_utc"])) for d in detections)
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
        "duration_hours": round(float(duration_hours), 3),
        "confidence_reasons": reasons,
    }

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class LifecycleThresholds:
    quiet_hours: float = 8.0
    closed_hours: float = 24.0
    active_overpasses: int = 2
    persistent_overpasses: int = 3
    active_duration_hours: float = 1.0
    persistent_duration_hours: float = 12.0

    def validate(self) -> None:
        if self.quiet_hours < 0:
            raise ValueError("quiet_hours must be >= 0")
        if self.closed_hours <= self.quiet_hours:
            raise ValueError("closed_hours must be greater than quiet_hours")
        if self.active_overpasses < 1:
            raise ValueError("active_overpasses must be >= 1")
        if self.persistent_overpasses < self.active_overpasses:
            raise ValueError("persistent_overpasses must be >= active_overpasses")
        if self.active_duration_hours < 0:
            raise ValueError("active_duration_hours must be >= 0")
        if self.persistent_duration_hours < self.active_duration_hours:
            raise ValueError("persistent_duration_hours must be >= active_duration_hours")


def _parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def classify_lifecycle(
    event: dict[str, Any],
    *,
    now_utc: str | datetime,
    thresholds: LifecycleThresholds | None = None,
) -> dict[str, Any]:
    t = thresholds or LifecycleThresholds()
    t.validate()

    now = _parse_utc(now_utc)
    last_seen = _parse_utc(event["last_seen_utc"])
    inactive_hours = max(0.0, (now - last_seen).total_seconds() / 3600.0)

    overpasses = int(event.get("overpass_count") or 0)
    duration = float(event.get("duration_hours") or 0.0)

    if inactive_hours >= t.closed_hours:
        state = "CLOSED"
        reason = (
            f"No new VIIRS detection for {inactive_hours:.1f} h "
            f"(closed threshold {t.closed_hours:g} h)."
        )
    elif inactive_hours >= t.quiet_hours:
        state = "QUIET"
        reason = (
            f"No new VIIRS detection for {inactive_hours:.1f} h "
            f"(quiet threshold {t.quiet_hours:g} h)."
        )
    elif overpasses >= t.persistent_overpasses or duration >= t.persistent_duration_hours:
        state = "PERSISTENT"
        if overpasses >= t.persistent_overpasses:
            reason = f"Recent detections span {overpasses} independent overpasses."
        else:
            reason = f"Recent detections span {duration:.1f} h."
    elif overpasses >= t.active_overpasses or duration >= t.active_duration_hours:
        state = "ACTIVE"
        if overpasses >= t.active_overpasses:
            reason = f"Recent detections span {overpasses} independent overpasses."
        else:
            reason = f"Recent detections span {duration:.1f} h."
    else:
        state = "NEW"
        reason = "Fresh event with limited independent repeat evidence."

    return {
        "lifecycle_state": state,
        "lifecycle_reason": reason,
        "inactive_hours": round(inactive_hours, 3),
    }

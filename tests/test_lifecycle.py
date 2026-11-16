from datetime import datetime, timezone

import pytest

from src.nepal_firewatch.lifecycle import LifecycleThresholds, classify_lifecycle


NOW = datetime(2026, 11, 13, 20, 0, tzinfo=timezone.utc)


def event(last_seen, *, overpasses=1, duration=0.0):
    return {
        "last_seen_utc": last_seen,
        "overpass_count": overpasses,
        "duration_hours": duration,
    }


def test_new_event():
    r = classify_lifecycle(event("2026-11-13T19:30:00+00:00"), now_utc=NOW)
    assert r["lifecycle_state"] == "NEW"


def test_active_from_repeat_overpass():
    r = classify_lifecycle(
        event("2026-11-13T19:30:00+00:00", overpasses=2),
        now_utc=NOW,
    )
    assert r["lifecycle_state"] == "ACTIVE"


def test_active_from_duration():
    r = classify_lifecycle(
        event("2026-11-13T19:30:00+00:00", duration=2.0),
        now_utc=NOW,
    )
    assert r["lifecycle_state"] == "ACTIVE"


def test_persistent_from_three_overpasses():
    r = classify_lifecycle(
        event("2026-11-13T19:30:00+00:00", overpasses=3),
        now_utc=NOW,
    )
    assert r["lifecycle_state"] == "PERSISTENT"


def test_persistent_from_duration():
    r = classify_lifecycle(
        event("2026-11-13T19:30:00+00:00", duration=13.0),
        now_utc=NOW,
    )
    assert r["lifecycle_state"] == "PERSISTENT"


def test_quiet_overrides_previous_evidence():
    r = classify_lifecycle(
        event("2026-11-13T11:30:00+00:00", overpasses=5, duration=20.0),
        now_utc=NOW,
    )
    assert r["lifecycle_state"] == "QUIET"


def test_closed_overrides_previous_evidence():
    r = classify_lifecycle(
        event("2026-11-12T19:00:00+00:00", overpasses=5, duration=20.0),
        now_utc=NOW,
    )
    assert r["lifecycle_state"] == "CLOSED"


def test_custom_thresholds():
    t = LifecycleThresholds(
        quiet_hours=4,
        closed_hours=12,
        active_overpasses=2,
        persistent_overpasses=4,
        active_duration_hours=1,
        persistent_duration_hours=18,
    )
    r = classify_lifecycle(
        event("2026-11-13T15:00:00+00:00", overpasses=4),
        now_utc=NOW,
        thresholds=t,
    )
    assert r["lifecycle_state"] == "QUIET"


def test_invalid_thresholds():
    with pytest.raises(ValueError):
        LifecycleThresholds(quiet_hours=24, closed_hours=8).validate()

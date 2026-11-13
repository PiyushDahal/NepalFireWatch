from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3

from src.nepal_firewatch import db
from src.nepal_firewatch.confidence import classify_event


def det(i, t, frp=10.0, confidence="nominal", satellite="N20"):
    return {
        "detection_id": i,
        "source": "test",
        "satellite": satellite,
        "instrument": "VIIRS",
        "latitude": 27.7,
        "longitude": 85.3,
        "observed_utc": t,
        "observed_npt": t,
        "confidence": confidence,
        "frp": frp,
        "daynight": "D",
        "bright_ti4": 330.0,
        "bright_ti5": 295.0,
        "province": "Bagmati",
        "district": "Kathmandu",
        "local_name": "Kathmandu",
        "local_type": "Metropolitan City",
    }


def test_single_nominal_10mw_remains_anomaly():
    result = classify_event([
        det("a", "2026-11-13T10:00:00+00:00", frp=10.0, confidence="nominal")
    ])
    assert result["evidence_score"] == 0
    assert result["confidence_class"] == "anomaly"


def test_two_detections_become_probable():
    result = classify_event([
        det("a", "2026-11-13T10:00:00+00:00"),
        det("b", "2026-11-13T10:15:00+00:00"),
    ])
    assert result["evidence_score"] == 2
    assert result["confidence_class"] == "probable"


def test_strong_persistent_multisat_event_is_high():
    result = classify_event([
        det("a", "2026-11-13T00:00:00+00:00", 60.0, "high", "N20"),
        det("b", "2026-11-13T02:00:00+00:00", 55.0, "high", "N21"),
        det("c", "2026-11-13T05:00:00+00:00", 35.0, "nominal", "N20"),
        det("d", "2026-11-13T07:00:00+00:00", 30.0, "nominal", "N21"),
    ])
    assert result["evidence_score"] >= 4
    assert result["confidence_class"] == "high"
    assert result["satellite_count"] == 2
    assert result["duration_hours"] == 7.0


def test_existing_v01_database_is_migrated_in_place():
    with TemporaryDirectory() as td:
        path = Path(td) / "legacy.sqlite"
        con = sqlite3.connect(path)
        con.execute("""
            CREATE TABLE events (
                event_id TEXT PRIMARY KEY,
                first_seen_utc TEXT NOT NULL,
                last_seen_utc TEXT NOT NULL,
                centroid_lat REAL NOT NULL,
                centroid_lon REAL NOT NULL,
                max_frp REAL,
                detection_count INTEGER NOT NULL DEFAULT 0,
                province TEXT,
                district TEXT,
                local_name TEXT,
                local_type TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                card_path TEXT
            )
        """)
        con.execute("""
            CREATE TABLE detections (
                detection_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                source TEXT,
                satellite TEXT,
                instrument TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                observed_utc TEXT NOT NULL,
                observed_npt TEXT NOT NULL,
                confidence TEXT,
                frp REAL,
                daynight TEXT,
                bright_ti4 REAL,
                bright_ti5 REAL,
                province TEXT,
                district TEXT,
                local_name TEXT,
                local_type TEXT,
                inserted_utc TEXT NOT NULL
            )
        """)
        con.commit()
        con.close()

        migrated = db.connect(path)
        try:
            cols = {r[1] for r in migrated.execute("PRAGMA table_info(events)")}
            assert "evidence_score" in cols
            assert "confidence_class" in cols
            assert "confidence_label" in cols
            assert "satellite_count" in cols
            assert "duration_hours" in cols
            assert "confidence_reasons" in cols
        finally:
            migrated.close()

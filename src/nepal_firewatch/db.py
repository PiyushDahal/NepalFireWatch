from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .confidence import classify_event
from .lifecycle import LifecycleThresholds, classify_lifecycle
from .utils import utcnow_iso


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS events (
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
    ward_no TEXT,
    ward_name TEXT,
    ward_id TEXT,
    ward_source TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    lifecycle_state TEXT NOT NULL DEFAULT 'NEW',
    lifecycle_reason TEXT NOT NULL DEFAULT '',
    lifecycle_updated_utc TEXT,
    inactive_hours REAL NOT NULL DEFAULT 0.0,
    closed_utc TEXT,
    sentinel2_status TEXT NOT NULL DEFAULT 'not_checked',
    sentinel2_path TEXT,
    sentinel2_scene_id TEXT,
    sentinel2_datetime_utc TEXT,
    sentinel2_cloud_cover REAL,
    sentinel2_source_url TEXT,
    sentinel2_checked_utc TEXT,
    sentinel2_error TEXT NOT NULL DEFAULT '',
    card_path TEXT,
    evidence_score INTEGER NOT NULL DEFAULT 0,
    confidence_class TEXT NOT NULL DEFAULT 'anomaly',
    confidence_label TEXT NOT NULL DEFAULT 'Satellite thermal anomaly',
    satellite_count INTEGER NOT NULL DEFAULT 0,
    overpass_count INTEGER NOT NULL DEFAULT 0,
    duration_hours REAL NOT NULL DEFAULT 0.0,
    confidence_reasons TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS detections (
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
    inserted_utc TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(event_id)
);
CREATE INDEX IF NOT EXISTS idx_detections_event ON detections(event_id);
CREATE INDEX IF NOT EXISTS idx_events_last_seen ON events(last_seen_utc);
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_utc TEXT NOT NULL,
    fetched INTEGER NOT NULL,
    new_detections INTEGER NOT NULL,
    new_events INTEGER NOT NULL,
    mode TEXT NOT NULL
);
"""


EVENT_CONFIDENCE_COLUMNS = {
    "evidence_score": "INTEGER NOT NULL DEFAULT 0",
    "confidence_class": "TEXT NOT NULL DEFAULT 'anomaly'",
    "confidence_label": "TEXT NOT NULL DEFAULT 'Satellite thermal anomaly'",
    "satellite_count": "INTEGER NOT NULL DEFAULT 0",
    "overpass_count": "INTEGER NOT NULL DEFAULT 0",
    "duration_hours": "REAL NOT NULL DEFAULT 0.0",
    "confidence_reasons": "TEXT NOT NULL DEFAULT '[]'",
}


EVENT_WARD_COLUMNS = {
    "ward_no": "TEXT",
    "ward_name": "TEXT",
    "ward_id": "TEXT",
    "ward_source": "TEXT",
}

EVENT_LIFECYCLE_COLUMNS = {
    "lifecycle_state": "TEXT NOT NULL DEFAULT 'NEW'",
    "lifecycle_reason": "TEXT NOT NULL DEFAULT ''",
    "lifecycle_updated_utc": "TEXT",
    "inactive_hours": "REAL NOT NULL DEFAULT 0.0",
    "closed_utc": "TEXT",
}

EVENT_SENTINEL2_COLUMNS = {
    "sentinel2_status": "TEXT NOT NULL DEFAULT 'not_checked'",
    "sentinel2_path": "TEXT",
    "sentinel2_scene_id": "TEXT",
    "sentinel2_datetime_utc": "TEXT",
    "sentinel2_cloud_cover": "REAL",
    "sentinel2_source_url": "TEXT",
    "sentinel2_checked_utc": "TEXT",
    "sentinel2_error": "TEXT NOT NULL DEFAULT ''",
}

def _event_columns(con: sqlite3.Connection) -> set[str]:
    return {row[1] for row in con.execute("PRAGMA table_info(events)").fetchall()}


def _migrate_event_confidence_columns(con: sqlite3.Connection) -> bool:
    """Add Checkpoint-2 columns to an existing v0.1 database in place."""
    existing = _event_columns(con)
    changed = False
    for name, sql_type in EVENT_CONFIDENCE_COLUMNS.items():
        if name not in existing:
            con.execute(f"ALTER TABLE events ADD COLUMN {name} {sql_type}")
            changed = True
    return changed


def _migrate_event_ward_columns(con: sqlite3.Connection) -> bool:
    existing = _event_columns(con)
    changed = False
    for name, sql_type in EVENT_WARD_COLUMNS.items():
        if name not in existing:
            con.execute(f"ALTER TABLE events ADD COLUMN {name} {sql_type}")
            changed = True
    return changed

def _migrate_event_lifecycle_columns(con: sqlite3.Connection) -> bool:
    existing = _event_columns(con)
    changed = False
    for name, sql_type in EVENT_LIFECYCLE_COLUMNS.items():
        if name not in existing:
            con.execute(f"ALTER TABLE events ADD COLUMN {name} {sql_type}")
            changed = True
    return changed

def _migrate_event_sentinel2_columns(con: sqlite3.Connection) -> bool:
    existing = _event_columns(con)
    changed = False
    for name, sql_type in EVENT_SENTINEL2_COLUMNS.items():
        if name not in existing:
            con.execute(f"ALTER TABLE events ADD COLUMN {name} {sql_type}")
            changed = True
    return changed

def _event_detections(con: sqlite3.Connection, event_id: str) -> list[dict]:
    return [
        dict(r)
        for r in con.execute(
            "SELECT * FROM detections WHERE event_id=? ORDER BY observed_utc",
            (event_id,),
        ).fetchall()
    ]


def _update_event_confidence(con: sqlite3.Connection, event_id: str) -> None:
    result = classify_event(_event_detections(con, event_id))
    con.execute(
        """
        UPDATE events
        SET evidence_score=?, confidence_class=?, confidence_label=?,
            satellite_count=?, overpass_count=?, duration_hours=?, confidence_reasons=?
        WHERE event_id=?
        """,
        (
            result["evidence_score"],
            result["confidence_class"],
            result["confidence_label"],
            result["satellite_count"],
            result["overpass_count"],
            result["duration_hours"],
            json.dumps(result["confidence_reasons"], ensure_ascii=False),
            event_id,
        ),
    )


def _backfill_confidence(con: sqlite3.Connection) -> None:
    event_ids = [r[0] for r in con.execute("SELECT event_id FROM events").fetchall()]
    for event_id in event_ids:
        _update_event_confidence(con, event_id)


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)

    migrated = _migrate_event_confidence_columns(con)
    _migrate_event_ward_columns(con)
    _migrate_event_lifecycle_columns(con)
    _migrate_event_sentinel2_columns(con)
    if migrated:
        # One-time classification of all events already stored in the v0.1 database.
        _backfill_confidence(con)
        con.commit()

    return con


def detection_exists(con: sqlite3.Connection, detection_id: str) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM detections WHERE detection_id=?", (detection_id,)
        ).fetchone()
        is not None
    )


def insert_event(con, event: dict) -> None:
    con.execute(
        """
        INSERT INTO events(event_id, first_seen_utc, last_seen_utc, centroid_lat, centroid_lon,
            max_frp, detection_count, province, district, local_name, local_type, status)
        VALUES(:event_id,:first_seen_utc,:last_seen_utc,:centroid_lat,:centroid_lon,
            :max_frp,0,:province,:district,:local_name,:local_type,'active')
        """,
        event,
    )


def insert_detection(con, d: dict, event_id: str) -> None:
    con.execute(
        """
        INSERT INTO detections(detection_id,event_id,source,satellite,instrument,latitude,longitude,
            observed_utc,observed_npt,confidence,frp,daynight,bright_ti4,bright_ti5,
            province,district,local_name,local_type,inserted_utc)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            d["detection_id"],
            event_id,
            d.get("source"),
            d.get("satellite"),
            d.get("instrument"),
            d["latitude"],
            d["longitude"],
            d["observed_utc"],
            d["observed_npt"],
            d.get("confidence"),
            d.get("frp"),
            d.get("daynight"),
            d.get("bright_ti4"),
            d.get("bright_ti5"),
            d.get("province"),
            d.get("district"),
            d.get("local_name"),
            d.get("local_type"),
            utcnow_iso(),
        ),
    )


def refresh_event(con, event_id: str) -> None:
    row = con.execute(
        """
        SELECT MIN(observed_utc) first_seen, MAX(observed_utc) last_seen,
               AVG(latitude) lat, AVG(longitude) lon, MAX(frp) max_frp, COUNT(*) n
        FROM detections WHERE event_id=?
        """,
        (event_id,),
    ).fetchone()

    con.execute(
        """
        UPDATE events SET first_seen_utc=?, last_seen_utc=?, centroid_lat=?, centroid_lon=?,
            max_frp=?, detection_count=? WHERE event_id=?
        """,
        (
            row["first_seen"],
            row["last_seen"],
            row["lat"],
            row["lon"],
            row["max_frp"],
            row["n"],
            event_id,
        ),
    )
    _update_event_confidence(con, event_id)


def set_event_ward(con, event_id: str, ward: dict | None) -> None:
    if not ward:
        return
    con.execute(
        "UPDATE events SET ward_no=?, ward_name=?, ward_id=?, ward_source=? WHERE event_id=?",
        (
            ward.get("ward_no"),
            ward.get("ward_name") or "",
            ward.get("ward_id") or "",
            ward.get("ward_source") or "BIPAD",
            event_id,
        ),
    )

def update_all_lifecycles(
    con,
    *,
    now_utc: str | None = None,
    quiet_hours: float = 8.0,
    closed_hours: float = 24.0,
    active_overpasses: int = 2,
    persistent_overpasses: int = 3,
    active_duration_hours: float = 1.0,
    persistent_duration_hours: float = 12.0,
) -> list[str]:
    """Re-evaluate every event and return IDs whose lifecycle state changed."""
    now_utc = now_utc or utcnow_iso()
    thresholds = LifecycleThresholds(
        quiet_hours=quiet_hours,
        closed_hours=closed_hours,
        active_overpasses=active_overpasses,
        persistent_overpasses=persistent_overpasses,
        active_duration_hours=active_duration_hours,
        persistent_duration_hours=persistent_duration_hours,
    )
    thresholds.validate()

    changed_ids: list[str] = []
    rows = con.execute("SELECT * FROM events").fetchall()

    for row in rows:
        event = dict(row)
        result = classify_lifecycle(event, now_utc=now_utc, thresholds=thresholds)

        old_state = str(event.get("lifecycle_state") or "NEW").upper()
        new_state = result["lifecycle_state"]
        state_changed = old_state != new_state

        updated_utc = event.get("lifecycle_updated_utc")
        if state_changed or not updated_utc:
            updated_utc = now_utc

        closed_utc = event.get("closed_utc")
        if new_state == "CLOSED":
            if not closed_utc:
                closed_utc = now_utc
        else:
            closed_utc = None

        con.execute(
            """
            UPDATE events
            SET status=?,
                lifecycle_state=?,
                lifecycle_reason=?,
                lifecycle_updated_utc=?,
                inactive_hours=?,
                closed_utc=?
            WHERE event_id=?
            """,
            (
                new_state.lower(),
                new_state,
                result["lifecycle_reason"],
                updated_utc,
                result["inactive_hours"],
                closed_utc,
                event["event_id"],
            ),
        )

        if state_changed:
            changed_ids.append(event["event_id"])

    return changed_ids


def set_event_sentinel2(con, event_id: str, result: dict) -> None:
    con.execute(
        """
        UPDATE events SET sentinel2_status=?, sentinel2_path=?,
        sentinel2_scene_id=?, sentinel2_datetime_utc=?, sentinel2_cloud_cover=?,
        sentinel2_source_url=?, sentinel2_checked_utc=?, sentinel2_error=?
        WHERE event_id=?
        """,
        (
            result.get("status") or "error",
            result.get("path"),
            result.get("scene_id"),
            result.get("datetime_utc"),
            result.get("cloud_cover"),
            result.get("source_url"),
            result.get("checked_utc"),
            result.get("error") or "",
            event_id,
        ),
    )


def set_card_path(con, event_id: str, card_path: str) -> None:
    con.execute(
        "UPDATE events SET card_path=? WHERE event_id=?", (card_path, event_id)
    )


def record_run(
    con, fetched: int, new_detections: int, new_events: int, mode: str
) -> None:
    con.execute(
        "INSERT INTO runs(run_utc,fetched,new_detections,new_events,mode) VALUES(?,?,?,?,?)",
        (utcnow_iso(), fetched, new_detections, new_events, mode),
    )

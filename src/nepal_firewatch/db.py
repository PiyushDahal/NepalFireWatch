from __future__ import annotations
import sqlite3
from pathlib import Path
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
    status TEXT NOT NULL DEFAULT 'active',
    card_path TEXT
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


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def detection_exists(con: sqlite3.Connection, detection_id: str) -> bool:
    return con.execute("SELECT 1 FROM detections WHERE detection_id=?", (detection_id,)).fetchone() is not None


def insert_event(con, event: dict) -> None:
    con.execute("""
        INSERT INTO events(event_id, first_seen_utc, last_seen_utc, centroid_lat, centroid_lon,
            max_frp, detection_count, province, district, local_name, local_type, status)
        VALUES(:event_id,:first_seen_utc,:last_seen_utc,:centroid_lat,:centroid_lon,
            :max_frp,0,:province,:district,:local_name,:local_type,'active')
    """, event)


def insert_detection(con, d: dict, event_id: str) -> None:
    con.execute("""
        INSERT INTO detections(detection_id,event_id,source,satellite,instrument,latitude,longitude,
            observed_utc,observed_npt,confidence,frp,daynight,bright_ti4,bright_ti5,
            province,district,local_name,local_type,inserted_utc)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d["detection_id"], event_id, d.get("source"), d.get("satellite"), d.get("instrument"),
        d["latitude"], d["longitude"], d["observed_utc"], d["observed_npt"], d.get("confidence"),
        d.get("frp"), d.get("daynight"), d.get("bright_ti4"), d.get("bright_ti5"),
        d.get("province"), d.get("district"), d.get("local_name"), d.get("local_type"), utcnow_iso()
    ))


def refresh_event(con, event_id: str) -> None:
    row = con.execute("""
        SELECT MIN(observed_utc) first_seen, MAX(observed_utc) last_seen,
               AVG(latitude) lat, AVG(longitude) lon, MAX(frp) max_frp, COUNT(*) n
        FROM detections WHERE event_id=?
    """, (event_id,)).fetchone()
    con.execute("""
        UPDATE events SET first_seen_utc=?, last_seen_utc=?, centroid_lat=?, centroid_lon=?,
            max_frp=?, detection_count=? WHERE event_id=?
    """, (row["first_seen"], row["last_seen"], row["lat"], row["lon"], row["max_frp"], row["n"], event_id))


def set_card_path(con, event_id: str, card_path: str) -> None:
    con.execute("UPDATE events SET card_path=? WHERE event_id=?", (card_path, event_id))


def record_run(con, fetched: int, new_detections: int, new_events: int, mode: str) -> None:
    con.execute("INSERT INTO runs(run_utc,fetched,new_detections,new_events,mode) VALUES(?,?,?,?,?)",
                (utcnow_iso(), fetched, new_detections, new_events, mode))

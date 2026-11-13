import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.nepal_firewatch import db
from src.nepal_firewatch.export import write_health


def test_write_health_file():
    with TemporaryDirectory() as td:
        td = Path(td)
        con = db.connect(td / "x.sqlite")
        try:
            health = write_health(
                con,
                td / "out",
                fetched=12,
                new_detections=3,
                new_events=2,
                mode="demo",
            )
            saved = json.loads(
                (td / "out" / "health.json").read_text(encoding="utf-8")
            )

            assert health["status"] == "success"
            assert saved["firms_records_fetched"] == 12
            assert saved["new_detections"] == 3
            assert saved["new_events"] == 2
            assert saved["database_detections"] == 0
            assert saved["database_events"] == 0
            assert saved["mode"] == "demo"
            assert saved["last_run_utc"]
        finally:
            con.close()

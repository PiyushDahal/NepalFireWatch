from pathlib import Path
from tempfile import TemporaryDirectory
from src.nepal_firewatch import db
from src.nepal_firewatch.events import ingest

def rec(i,lat,lon,t):
    return {"detection_id":i,"source":"x","satellite":"N20","instrument":"VIIRS","latitude":lat,"longitude":lon,"observed_utc":t,"observed_npt":t,"confidence":"nominal","frp":10.0,"daynight":"D","bright_ti4":330.0,"bright_ti5":295.0,"province":"Bagmati","district":"Kathmandu","local_name":"Kathmandu","local_type":"Metropolitan City"}

def test_nearby_detections_cluster():
    with TemporaryDirectory() as td:
        con = db.connect(Path(td) / "x.sqlite")
        try:
            a = rec("a", 27.70, 85.30, "2026-09-27T10:00:00+00:00")
            b = rec("b", 27.705, 85.305, "2026-09-27T10:15:00+00:00")

            nd, ne, _ = ingest(con, [a, b], 3.0, 12)

            assert (nd, ne) == (2, 1)
            assert con.execute(
                "select count(*) from events"
            ).fetchone()[0] == 1
        finally:
            con.close()

from pathlib import Path
import json

from PIL import Image

from src.nepal_firewatch.cards import _fmt_npt, make_card


def test_fmt_npt():
    assert _fmt_npt("2026-11-12T07:24:00+00:00") == "12 Nov 2026, 01:09 PM NPT"


def test_make_ward_text_local_level_map(tmp_path: Path):
    boundary = tmp_path / "boundary.geojson"
    boundary.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "province": 2,
                            "district": "Dhanusha",
                            "locallevel_name": "Kamala",
                            "locallevel_type": "Nagarpalika",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [86.08, 26.61],
                                [86.22, 26.61],
                                [86.22, 26.78],
                                [86.08, 26.78],
                                [86.08, 26.61],
                            ]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    event = {
        "event_id": "NFW-TEST-001",
        "first_seen_utc": "2026-11-12T07:24:00+00:00",
        "last_seen_utc": "2026-11-12T08:54:00+00:00",
        "centroid_lat": 26.657,
        "centroid_lon": 86.183,
        "max_frp": 21.2,
        "detection_count": 2,
        "province": "Madhesh",
        "district": "Dhanusha",
        "local_name": "Kamala",
        "local_type": "Nagarpalika",
        "ward_no": "4",
        "ward_name": "",
        "ward_source": "BIPAD",
        "confidence_class": "probable",
        "evidence_score": 3,
        "satellite_count": 2,
        "overpass_count": 2,
        "duration_hours": 1.5,
    }
    detections = [
        {"latitude": 26.65701, "longitude": 86.18273},
        {"latitude": 26.65764, "longitude": 86.18667},
    ]

    out = tmp_path / "card.png"
    result = make_card(
        event,
        detections,
        out,
        boundary_path=boundary,
    )

    assert result == out
    assert out.exists()
    with Image.open(out) as im:
        assert im.size == (1600, 900)
        assert im.mode == "RGB"

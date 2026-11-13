from pathlib import Path
from src.nepal_firewatch.boundaries import BoundaryResolver

def test_demo_boundary():
    p=Path(__file__).resolve().parents[1]/"samples/demo_boundaries.geojson"
    r=BoundaryResolver(p).resolve(27.7172,85.3240)
    assert r["district"]=="Kathmandu"
    assert r["province"]=="Bagmati"


def test_openknowledge_property_normalization():
    from src.nepal_firewatch.boundaries import _normalize_properties

    p = _normalize_properties(
        {
            "STATE_CODE": 2,
            "DISTRICT": "DHANUSHA",
            "GaPa_NaPa": "Kamala",
            "Type_GN": "Nagarpalika",
            "Province": "2",
        }
    )
    assert p["province"] == 2
    assert p["district"] == "Dhanusha"
    assert p["locallevel_name"] == "Kamala"
    assert p["locallevel_type"] == "Nagarpalika"

from pathlib import Path
from src.nepal_firewatch.boundaries import BoundaryResolver

def test_demo_boundary():
    p=Path(__file__).resolve().parents[1]/"samples/demo_boundaries.geojson"
    r=BoundaryResolver(p).resolve(27.7172,85.3240)
    assert r["district"]=="Kathmandu"
    assert r["province"]=="Bagmati"

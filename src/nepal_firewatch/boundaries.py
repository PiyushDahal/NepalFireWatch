from __future__ import annotations
import json
from pathlib import Path
import requests
from shapely.geometry import Point, shape

PROVINCES = {
    1: "Koshi", 2: "Madhesh", 3: "Bagmati", 4: "Gandaki",
    5: "Lumbini", 6: "Karnali", 7: "Sudurpashchim"
}
TYPE_LABELS = {
    "Mahanagarpalika": "Metropolitan City",
    "Upamahanagarpalika": "Sub-Metropolitan City",
    "Nagarpalika": "Municipality",
    "Gaunpalika": "Rural Municipality",
}


def download_boundaries(path: Path, url: str, timeout: int = 90) -> Path:
    if path.exists() and path.stat().st_size > 1000:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if data.get("type") != "FeatureCollection":
        raise RuntimeError("Boundary download was not a GeoJSON FeatureCollection")
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class BoundaryResolver:
    def __init__(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.features = []
        for feat in data.get("features", []):
            try:
                geom = shape(feat["geometry"])
                props = feat.get("properties", {})
                self.features.append((geom, props))
            except Exception:
                continue

    def resolve(self, lat: float, lon: float) -> dict | None:
        p = Point(lon, lat)
        matches = [(geom, props) for geom, props in self.features if geom.covers(p)]
        if not matches:
            return None
        # Prefer municipality/local government polygons over special regions if overlaps exist.
        municipal = [m for m in matches if m[1].get("locallevel_type") in TYPE_LABELS]
        _, props = (municipal or matches)[0]
        province_raw = props.get("province")
        try:
            province_num = int(province_raw)
        except (TypeError, ValueError):
            province_num = None
        local_type = str(props.get("locallevel_type", ""))
        return {
            "province": PROVINCES.get(province_num, str(province_raw or "")),
            "district": str(props.get("district", "")),
            "local_name": str(props.get("locallevel_name", "")),
            "local_name_nepali": str(props.get("locallevel_name_nepali", "")),
            "local_type": local_type,
            "local_type_label": TYPE_LABELS.get(local_type, local_type.replace("_", " ")),
        }

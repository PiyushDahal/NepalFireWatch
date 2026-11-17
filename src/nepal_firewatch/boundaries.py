from __future__ import annotations

import json
from pathlib import Path

import requests
from shapely.geometry import Point, shape

PROVINCES = {
    1: "Koshi",
    2: "Madhesh",
    3: "Bagmati",
    4: "Gandaki",
    5: "Lumbini",
    6: "Karnali",
    7: "Sudurpashchim",
}

TYPE_LABELS = {
    "Mahanagarpalika": "Metropolitan City",
    "Upamahanagarpalika": "Sub-Metropolitan City",
    "Nagarpalika": "Municipality",
    "Gaunpalika": "Rural Municipality",
}


def _pick(props: dict, *names):
    for name in names:
        if name in props and props[name] not in (None, ""):
            return props[name]
    return None


def _clean_name(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    # Current Open Knowledge Nepal source uses uppercase district names.
    if text and text.upper() == text and any(ch.isalpha() for ch in text):
        return text.title()
    return text


def _normalize_properties(props: dict) -> dict:
    """Normalize multiple Nepal local-level schemas to FireWatch's canonical keys."""
    province = _pick(
        props,
        "province",
        "Province",
        "STATE_CODE",
        "state_code",
        "province_code",
    )
    district = _pick(
        props,
        "district",
        "DISTRICT",
        "district_name",
        "District",
    )
    local_name = _pick(
        props,
        "locallevel_name",
        "local_level_name",
        "GaPa_NaPa",
        "municipality",
        "Municipality",
        "name",
        "NAME",
    )
    local_type = _pick(
        props,
        "locallevel_type",
        "local_level_type",
        "Type_GN",
        "local_type",
        "type",
        "TYPE",
    )
    local_name_nepali = _pick(
        props,
        "locallevel_name_nepali",
        "local_level_name_nepali",
        "name_nepali",
        "NAME_NEP",
    )

    # Keep province codes canonical across datasets: 2 and "2" both become int 2.
    try:
        province = int(province)
    except (TypeError, ValueError):
        pass

    return {
        "province": province,
        "district": _clean_name(district),
        "locallevel_name": _clean_name(local_name),
        "locallevel_name_nepali": str(local_name_nepali or ""),
        "locallevel_type": str(local_type or ""),
    }


def _normalize_feature_collection(data: dict) -> dict:
    if data.get("type") != "FeatureCollection":
        raise RuntimeError("Boundary download was not a GeoJSON FeatureCollection")

    features = []
    for feat in data.get("features", []):
        geom = feat.get("geometry")
        if not geom:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": _normalize_properties(feat.get("properties", {})),
                "geometry": geom,
            }
        )

    if len(features) < 700:
        raise RuntimeError(
            f"Boundary dataset unexpectedly contains only {len(features)} features"
        )

    return {
        "type": "FeatureCollection",
        "name": "nepal_local_levels_firewatch",
        "source": (
            "Open Knowledge Nepal localboundaries "
            "(CC BY 4.0; normalized for Nepal FireWatch)"
        ),
        "features": features,
    }


def download_boundaries(path: Path, url: str, timeout: int = 120) -> Path:
    if path.exists() and path.stat().st_size > 1000:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    data = _normalize_feature_collection(r.json())
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


class BoundaryResolver:
    def __init__(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.features = []
        for feat in data.get("features", []):
            try:
                geom = shape(feat["geometry"])
                props = _normalize_properties(feat.get("properties", {}))
                self.features.append((geom, props))
            except Exception:
                continue

    def resolve(self, lat: float, lon: float) -> dict | None:
        p = Point(lon, lat)
        matches = [
            (geom, props)
            for geom, props in self.features
            if geom.covers(p)
        ]
        if not matches:
            return None

        # Prefer municipality/local-government polygons over protected/special areas.
        municipal = [
            m
            for m in matches
            if m[1].get("locallevel_type") in TYPE_LABELS
        ]
        _, props = (municipal or matches)[0]

        province_raw = props.get("province")
        try:
            province_num = int(province_raw)
        except (TypeError, ValueError):
            province_num = None

        local_type = str(props.get("locallevel_type", ""))

        return {
            "province": PROVINCES.get(
                province_num,
                _clean_name(province_raw),
            ),
            "district": _clean_name(props.get("district", "")),
            "local_name": _clean_name(props.get("locallevel_name", "")),
            "local_name_nepali": str(
                props.get("locallevel_name_nepali", "")
            ),
            "local_type": local_type,
            "local_type_label": TYPE_LABELS.get(
                local_type,
                local_type.replace("_", " "),
            ),
        }

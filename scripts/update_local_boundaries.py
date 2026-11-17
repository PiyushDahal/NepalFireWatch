from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

SOURCE_URL = (
    "https://raw.githubusercontent.com/openknowledgenp/"
    "localboundaries/gh-pages/public/data/local-level/nepal.geojson"
)
OUTPUT = ROOT / "data" / "cache" / "nepal_local_levels_oknp.geojson"
META = ROOT / "data" / "cache" / "nepal_local_levels_oknp.metadata.json"


def _clean_name(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text and text.upper() == text and any(ch.isalpha() for ch in text):
        return text.title()
    return text


def _pick(props: dict, *names):
    for name in names:
        value = props.get(name)
        if value not in (None, ""):
            return value
    return None


def normalize_properties(props: dict) -> dict:
    return {
        "province": _pick(
            props,
            "province",
            "Province",
            "STATE_CODE",
            "state_code",
            "province_code",
        ),
        "district": _clean_name(
            _pick(
                props,
                "district",
                "DISTRICT",
                "district_name",
                "District",
            )
        ),
        "locallevel_name": _clean_name(
            _pick(
                props,
                "locallevel_name",
                "local_level_name",
                "GaPa_NaPa",
                "municipality",
                "Municipality",
                "name",
                "NAME",
            )
        ),
        "locallevel_name_nepali": str(
            _pick(
                props,
                "locallevel_name_nepali",
                "local_level_name_nepali",
                "name_nepali",
                "NAME_NEP",
            )
            or ""
        ),
        "locallevel_type": str(
            _pick(
                props,
                "locallevel_type",
                "local_level_type",
                "Type_GN",
                "local_type",
                "type",
                "TYPE",
            )
            or ""
        ),
    }


def main():
    print("Downloading current Nepal local-level boundaries...")
    print(SOURCE_URL)

    r = requests.get(SOURCE_URL, timeout=180)
    r.raise_for_status()
    source = r.json()

    if source.get("type") != "FeatureCollection":
        raise RuntimeError("Downloaded file is not a GeoJSON FeatureCollection")

    features = []
    for feat in source.get("features", []):
        if not feat.get("geometry"):
            continue
        features.append(
            {
                "type": "Feature",
                "properties": normalize_properties(
                    feat.get("properties", {})
                ),
                "geometry": feat["geometry"],
            }
        )

    if len(features) < 700:
        raise RuntimeError(
            f"Only {len(features)} features found; refusing to replace boundary dataset"
        )

    out = {
        "type": "FeatureCollection",
        "name": "nepal_local_levels_firewatch",
        "source": "Open Knowledge Nepal localboundaries",
        "license": "CC BY 4.0",
        "features": features,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    meta = {
        "source_name": "Open Knowledge Nepal localboundaries",
        "source_repository": (
            "https://github.com/openknowledgenp/localboundaries"
        ),
        "source_url": SOURCE_URL,
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "feature_count": len(features),
        "notes": (
            "Properties normalized for Nepal FireWatch. "
            "Geometry retained from source GeoJSON."
        ),
    }
    META.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    kamala = [
        f
        for f in features
        if str(f["properties"].get("locallevel_name", "")).casefold()
        == "kamala"
        and str(f["properties"].get("district", "")).casefold()
        == "dhanusha"
    ]

    print(f"Saved {len(features)} features to: {OUTPUT}")
    print(f"Metadata: {META}")
    print(f"Kamala Municipality features found: {len(kamala)}")
    if kamala:
        print("Kamala properties:", kamala[0]["properties"])


if __name__ == "__main__":
    main()

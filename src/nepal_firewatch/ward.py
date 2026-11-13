from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

BIPAD_BASE = "https://bipadportal.gov.np/api/v1"
GEOLOOKUP_URL = f"{BIPAD_BASE}/geolookup/"
CACHE_VERSION = 2


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def _get_ci(d: dict, *keys: str):
    wanted = {k.lower() for k in keys}
    for key, value in d.items():
        if str(key).lower() in wanted:
            return value
    return None


def _first_value(obj: Any, keys: tuple[str, ...]):
    for d in _walk(obj):
        value = _get_ci(d, *keys)
        if value not in (None, "", []):
            return value
    return None


def _as_id(value):
    if isinstance(value, dict):
        value = (
            value.get("id")
            or value.get("pk")
            or value.get("value")
        )
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        s = str(value).strip()
        return int(s) if s.isdigit() else None


def _clean_text(value):
    if value is None or isinstance(value, (dict, list)):
        return ""
    s = str(value).strip()
    return s


def _non_numeric_text(value):
    s = _clean_text(value)
    if not s:
        return ""
    if s.replace(".", "", 1).isdigit():
        return ""
    return s


def _ward_number_from_detail(detail: Any, ward_id: int | None):
    # Prefer explicit ward-number fields.
    value = _first_value(
        detail,
        (
            "ward_no",
            "ward_number",
            "wardnumber",
            "wardNumber",
            "number",
        ),
    )

    if value is None:
        # DRF serializers commonly expose a display field as title/name.
        value = _first_value(detail, ("title", "name", "name_en"))

    if isinstance(value, dict):
        value = value.get("title") or value.get("name") or value.get("number")

    if value is None:
        return None

    s = str(value).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return None

    # Never mistake the BIPAD row id for the ward number.
    if ward_id is not None and digits == str(ward_id):
        return None

    try:
        n = int(digits)
    except Exception:
        return None

    # Nepal wards are small positive integers; this also rejects IDs such as 6418.
    if 1 <= n <= 99:
        return str(n)
    return None


def _display_name(detail: Any):
    value = _first_value(
        detail,
        (
            "title",
            "name",
            "name_en",
            "nameEnglish",
            "english_name",
        ),
    )
    return _non_numeric_text(value)


def _extract_geometry(obj: Any):
    for d in _walk(obj):
        for key in ("geometry", "geojson", "geom"):
            value = d.get(key)
            if isinstance(value, dict) and value.get("type") in {
                "Polygon",
                "MultiPolygon",
            }:
                return value
            if isinstance(value, dict) and value.get("type") == "Feature":
                geom = value.get("geometry")
                if isinstance(geom, dict):
                    return geom
    return None


def _geolookup_ids(raw: Any) -> dict:
    """Extract BIPAD foreign-key IDs from the coordinate geolookup response."""
    result = {
        "ward_id": None,
        "municipality_id": None,
        "district_id": None,
        "province_id": None,
    }

    # Prefer top-level or shallow explicit fields before recursively searching.
    dicts = list(_walk(raw))
    for d in dicts:
        for out_key, candidates in (
            ("ward_id", ("ward_id", "ward")),
            ("municipality_id", ("municipality_id", "municipality")),
            ("district_id", ("district_id", "district")),
            ("province_id", ("province_id", "province")),
        ):
            if result[out_key] is None:
                value = _get_ci(d, *candidates)
                ident = _as_id(value)
                if ident is not None:
                    result[out_key] = ident

    return result


def _safe_get_json(session: requests.Session, url: str, timeout: int, params=None):
    r = session.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _detail_url(kind: str, ident: int | None):
    if ident is None:
        return None
    return f"{BIPAD_BASE}/{kind}/{ident}/"


def _resolve_from_raw(
    raw: Any,
    session: requests.Session,
    timeout: int,
) -> dict | None:
    ids = _geolookup_ids(raw)
    ward_id = ids["ward_id"]
    municipality_id = ids["municipality_id"]
    district_id = ids["district_id"]
    province_id = ids["province_id"]

    if ward_id is None and municipality_id is None:
        return None

    ward_detail = {}
    municipality_detail = {}
    district_detail = {}
    province_detail = {}

    if ward_id is not None:
        try:
            ward_detail = _safe_get_json(
                session, _detail_url("ward", ward_id), timeout
            )
        except Exception:
            ward_detail = {}

        # Ward detail may contain a more reliable municipality FK.
        maybe_mid = _as_id(
            _first_value(
                ward_detail,
                ("municipality_id", "municipality"),
            )
        )
        municipality_id = maybe_mid or municipality_id

    if municipality_id is not None:
        try:
            municipality_detail = _safe_get_json(
                session,
                _detail_url("municipality", municipality_id),
                timeout,
            )
        except Exception:
            municipality_detail = {}

        maybe_did = _as_id(
            _first_value(
                municipality_detail,
                ("district_id", "district"),
            )
        )
        district_id = maybe_did or district_id

        maybe_pid = _as_id(
            _first_value(
                municipality_detail,
                ("province_id", "province"),
            )
        )
        province_id = maybe_pid or province_id

    if district_id is not None:
        try:
            district_detail = _safe_get_json(
                session, _detail_url("district", district_id), timeout
            )
        except Exception:
            district_detail = {}

        maybe_pid = _as_id(
            _first_value(
                district_detail,
                ("province_id", "province"),
            )
        )
        province_id = maybe_pid or province_id

    if province_id is not None:
        try:
            province_detail = _safe_get_json(
                session, _detail_url("province", province_id), timeout
            )
        except Exception:
            province_detail = {}

    ward_no = _ward_number_from_detail(ward_detail, ward_id)
    municipality_name = _display_name(municipality_detail)
    district_name = _display_name(district_detail)
    province_name = _display_name(province_detail)

    # Only use geometry if it is explicitly provided by BIPAD.
    geometry = (
        _extract_geometry(ward_detail)
        or _extract_geometry(raw)
    )

    return {
        "ward_no": ward_no or "",
        "ward_name": "",
        "ward_id": "" if ward_id is None else str(ward_id),
        "bipad_municipality": municipality_name,
        "bipad_municipality_id": ""
        if municipality_id is None
        else str(municipality_id),
        "bipad_district": district_name,
        "bipad_district_id": ""
        if district_id is None
        else str(district_id),
        "bipad_province": province_name,
        "bipad_province_id": ""
        if province_id is None
        else str(province_id),
        "ward_source": "BIPAD",
        "_ward_geometry": geometry,
    }


class BipadWardResolver:
    """Coordinate -> BIPAD ward metadata, with persistent versioned caching."""

    def __init__(
        self,
        cache_path: Path,
        timeout: int = 20,
        session: requests.Session | None = None,
    ):
        self.cache_path = Path(cache_path)
        self.timeout = timeout
        self.session = session or requests.Session()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.cache = json.loads(
                self.cache_path.read_text(encoding="utf-8")
            )
        except Exception:
            self.cache = {}

    @staticmethod
    def _key(lat: float, lon: float) -> str:
        return f"{float(lat):.4f},{float(lon):.4f}"

    def _save(self):
        self.cache_path.write_text(
            json.dumps(
                self.cache,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def resolve(self, lat: float, lon: float) -> dict | None:
        key = self._key(lat, lon)
        cached = self.cache.get(key)

        # v1 cache entries contained raw FK IDs mislabeled as ward/name values.
        # Only trust v2+ entries.
        if (
            isinstance(cached, dict)
            and cached.get("cache_version") == CACHE_VERSION
        ):
            result = cached.get("result")
            return result if isinstance(result, dict) else None

        attempts = [
            {"lat": lat, "lng": lon},
            {"latitude": lat, "longitude": lon},
            {"lat": lat, "lon": lon},
            {"point": f"{lon},{lat}"},
        ]

        last_error = ""
        raw = None
        result = None

        for params in attempts:
            try:
                raw = _safe_get_json(
                    self.session,
                    GEOLOOKUP_URL,
                    self.timeout,
                    params=params,
                )
                result = _resolve_from_raw(
                    raw,
                    self.session,
                    self.timeout,
                )
                if result is not None:
                    break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"

        self.cache[key] = {
            "cache_version": CACHE_VERSION,
            "lat": float(lat),
            "lon": float(lon),
            "fetched_utc": _utcnow(),
            "result": result,
            "last_error": last_error,
        }
        self._save()
        return result


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="Test BIPAD ward lookup for one coordinate"
    )
    p.add_argument("--lat", required=True, type=float)
    p.add_argument("--lon", required=True, type=float)
    p.add_argument(
        "--cache",
        default="data/cache/bipad_ward_lookup.json",
    )
    args = p.parse_args()

    resolver = BipadWardResolver(Path(args.cache))
    print(
        json.dumps(
            resolver.resolve(args.lat, args.lon),
            ensure_ascii=False,
            indent=2,
        )
    )

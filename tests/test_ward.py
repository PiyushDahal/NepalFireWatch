from pathlib import Path

from src.nepal_firewatch.ward import (
    BipadWardResolver,
    _geolookup_ids,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if url.endswith("/geolookup/"):
            return FakeResponse(
                {
                    "ward": 6418,
                    "municipality": 17011,
                    "district": 17,
                    "province": 2,
                }
            )
        if url.endswith("/ward/6418/"):
            return FakeResponse(
                {
                    "id": 6418,
                    "title": "4",
                    "municipality": 17011,
                }
            )
        if url.endswith("/municipality/17011/"):
            return FakeResponse(
                {
                    "id": 17011,
                    "title": "Kamala Municipality",
                    "district": 17,
                    "province": 2,
                }
            )
        if url.endswith("/district/17/"):
            return FakeResponse(
                {
                    "id": 17,
                    "title": "Dhanusha",
                    "province": 2,
                }
            )
        if url.endswith("/province/2/"):
            return FakeResponse(
                {
                    "id": 2,
                    "title": "Madhesh",
                }
            )
        raise AssertionError(f"Unexpected URL: {url}")


def test_geolookup_values_are_ids_not_ward_numbers():
    ids = _geolookup_ids(
        {
            "ward": 6418,
            "municipality": 17011,
            "district": 17,
            "province": 2,
        }
    )
    assert ids["ward_id"] == 6418
    assert ids["municipality_id"] == 17011
    assert ids["district_id"] == 17
    assert ids["province_id"] == 2


def test_resolver_follows_detail_endpoints(tmp_path: Path):
    resolver = BipadWardResolver(
        tmp_path / "ward-cache.json",
        session=FakeSession(),
    )
    result = resolver.resolve(26.65701, 86.18273)

    assert result["ward_no"] == "4"
    assert result["ward_id"] == "6418"
    assert result["bipad_municipality"] == "Kamala Municipality"
    assert result["bipad_district"] == "Dhanusha"
    assert result["bipad_province"] == "Madhesh"
    assert result["_ward_geometry"] is None


def test_old_cache_is_invalidated(tmp_path: Path):
    cache = tmp_path / "ward-cache.json"
    cache.write_text(
        """{
          "26.6570,86.1827": {
            "result": {
              "ward_no": "6418",
              "bipad_municipality": "17011"
            }
          }
        }""",
        encoding="utf-8",
    )

    resolver = BipadWardResolver(
        cache,
        session=FakeSession(),
    )
    result = resolver.resolve(26.65701, 86.18273)

    assert result["ward_no"] == "4"
    assert result["bipad_municipality"] == "Kamala Municipality"

from src.nepal_firewatch.sentinel2 import select_scene, needs_check


def _item(i, dt, cloud, visual=True):
    return {
        "id": i,
        "properties": {"datetime": dt, "eo:cloud_cover": cloud},
        "assets": {"visual": {"href": "https://example.test/x.tif"}} if visual else {},
    }


def test_select_scene_prefers_nearest_usable():
    xs = [
        _item("cloudy", "2026-11-12T07:00:00Z", 90),
        _item("before", "2026-11-11T07:00:00Z", 10),
        _item("after", "2026-11-13T07:00:00Z", 20),
    ]
    assert select_scene(xs, "2026-11-12T07:00:00Z", 60)["id"] == "after"


def test_select_scene_requires_visual():
    assert select_scene([_item("x", "2026-11-12T07:00:00Z", 1, False)], "2026-11-12T07:00:00Z", 60) is None


def test_needs_check_initial():
    assert needs_check({"lifecycle_state":"NEW","sentinel2_path":None,"sentinel2_checked_utc":None}, now_utc="2026-11-16T12:00:00Z")


def test_closed_not_retried():
    assert not needs_check({"lifecycle_state":"CLOSED","sentinel2_path":None,"sentinel2_checked_utc":None}, now_utc="2026-11-16T12:00:00Z")


def test_existing_image_not_replaced():
    assert not needs_check({"lifecycle_state":"ACTIVE","sentinel2_path":"event_imagery/x.jpg","sentinel2_checked_utc":None}, now_utc="2026-11-16T12:00:00Z", force=True)

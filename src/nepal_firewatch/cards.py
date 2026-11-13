from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import box, shape

W, H = 1600, 900

BG = (18, 20, 24)
PANEL = (28, 31, 36)
MAP_BG = (20, 23, 27)
WHITE = (245, 247, 250)
MUTED = (170, 178, 190)
GRID = (64, 69, 78)
RED = (232, 67, 62)
ORANGE = (255, 159, 67)
YELLOW = (238, 194, 74)
DARK_TEXT = (22, 24, 28)
CYAN = (93, 188, 210)

NPT = timezone(timedelta(hours=5, minutes=45))

LOCAL_TYPE_LABELS = {
    "Mahanagarpalika": "Metropolitan City",
    "Upamahanagarpalika": "Sub-Metropolitan City",
    "Nagarpalika": "Municipality",
    "Gaunpalika": "Rural Municipality",
}


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fmt_npt(value: str) -> str:
    try:
        return _parse_dt(value).astimezone(NPT).strftime("%d %b %Y, %I:%M %p NPT")
    except Exception:
        return str(value)


def _confidence_style(event: dict):
    cls = str(event.get("confidence_class") or "anomaly").lower()
    if cls == "high":
        return "HIGH EVIDENCE", RED, WHITE
    if cls == "probable":
        return "PROBABLE FIRE SIGNAL", ORANGE, DARK_TEXT
    return "THERMAL ANOMALY", YELLOW, DARK_TEXT


def _local_label(event: dict) -> str:
    name = str(event.get("local_name") or "Local level").strip()
    raw_type = str(event.get("local_type") or "").strip()
    label_type = LOCAL_TYPE_LABELS.get(raw_type, raw_type)
    if label_type and label_type.lower() not in name.lower():
        return f"{name} {label_type}".strip()
    return name


@lru_cache(maxsize=4)
def _load_shapes_cached(path_str: str):
    path = Path(path_str)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    out = []
    for feat in data.get("features", []):
        try:
            geom = shape(feat["geometry"])
            if geom.is_empty:
                continue
            out.append(
                (
                    geom.simplify(0.0010, preserve_topology=True),
                    feat.get("properties", {}),
                )
            )
        except Exception:
            continue
    return out


def _iter_exteriors(geom):
    if geom.is_empty:
        return
    if geom.geom_type == "Polygon":
        yield list(geom.exterior.coords)
    elif geom.geom_type == "MultiPolygon":
        for poly in geom.geoms:
            yield list(poly.exterior.coords)
    elif geom.geom_type == "GeometryCollection":
        for part in geom.geoms:
            yield from _iter_exteriors(part)


def _project(lon: float, lat: float, bounds, draw_box):
    minx, miny, maxx, maxy = bounds
    x0, y0, x1, y1 = draw_box
    dx = max(maxx - minx, 1e-9)
    dy = max(maxy - miny, 1e-9)
    px = x0 + (lon - minx) / dx * (x1 - x0)
    py = y1 - (lat - miny) / dy * (y1 - y0)
    return px, py


def _local_bounds(event: dict, detections: list[dict]):
    lats = [float(event["centroid_lat"])]
    lons = [float(event["centroid_lon"])]

    for p in detections:
        try:
            lats.append(float(p["latitude"]))
            lons.append(float(p["longitude"]))
        except Exception:
            pass

    lat_span = max(lats) - min(lats)
    lon_span = max(lons) - min(lons)

    # Local context, roughly 10–20 km for small/single-pixel events.
    pad_lat = max(0.065, lat_span * 2.0 + 0.030)
    pad_lon = max(0.075, lon_span * 2.0 + 0.035)

    cy = sum(lats) / len(lats)
    cx = sum(lons) / len(lons)
    return (cx - pad_lon, cy - pad_lat, cx + pad_lon, cy + pad_lat)


def _draw_local_label(d, geom, bounds, draw_box, text: str, font):
    try:
        rp = geom.representative_point()
        px, py = _project(float(rp.x), float(rp.y), bounds, draw_box)
        bbox = d.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x0 = max(draw_box[0] + 4, min(px - tw / 2 - 8, draw_box[2] - tw - 20))
        y0 = max(draw_box[1] + 4, min(py - th / 2 - 6, draw_box[3] - th - 16))
        d.rounded_rectangle(
            (x0, y0, x0 + tw + 16, y0 + th + 12),
            radius=7,
            fill=(18, 20, 24),
            outline=CYAN,
            width=1,
        )
        d.text((x0 + 8, y0 + 4), text, font=font, fill=WHITE)
    except Exception:
        pass


def _draw_local_map(d, event, detections, boundary_path, panel_box, tiny, small):
    x0, y0, x1, y1 = panel_box
    d.rounded_rectangle(panel_box, radius=26, fill=MAP_BG, outline=GRID, width=2)
    d.text((x0 + 24, y0 + 18), "LOCAL AREA", font=small, fill=WHITE)

    draw_box = (x0 + 24, y0 + 64, x1 - 24, y1 - 60)
    bounds = _local_bounds(event, detections)
    view_geom = box(*bounds)

    shapes = _load_shapes_cached(str(boundary_path)) if boundary_path else []
    local_name = str(event.get("local_name") or "")
    district = str(event.get("district") or "")
    local_label = _local_label(event)

    nearby = []
    matched_local = []

    for geom, props in shapes:
        try:
            if geom.intersects(view_geom):
                nearby.append((geom, props))

            prop_name = str(props.get("locallevel_name") or "")
            prop_district = str(props.get("district") or "")
            if (
                local_name
                and prop_name.casefold() == local_name.casefold()
                and (
                    not district
                    or prop_district.casefold() == district.casefold()
                )
            ):
                matched_local.append(geom)
        except Exception:
            continue

    # Neighbouring local-level boundaries for context.
    for geom, _ in nearby:
        clipped = geom.intersection(view_geom)
        for ring in _iter_exteriors(clipped):
            pts = [
                _project(float(lon), float(lat), bounds, draw_box)
                for lon, lat in ring
            ]
            if len(pts) >= 2:
                d.line(pts, fill=(75, 83, 94), width=2)

    # Highlight only the actual local-level boundary.
    for geom in matched_local:
        clipped = geom.intersection(view_geom)
        for ring in _iter_exteriors(clipped):
            pts = [
                _project(float(lon), float(lat), bounds, draw_box)
                for lon, lat in ring
            ]
            if len(pts) >= 2:
                d.line(pts, fill=CYAN, width=5)

    # Label the highlighted local level directly on the local map.
    if matched_local:
        visible_parts = [g.intersection(view_geom) for g in matched_local]
        visible_parts = [g for g in visible_parts if not g.is_empty]
        if visible_parts:
            label_geom = max(visible_parts, key=lambda g: g.area)
            _draw_local_label(d, label_geom, bounds, draw_box, local_label, tiny)

    # VIIRS pixels.
    for p in detections:
        try:
            px, py = _project(
                float(p["longitude"]),
                float(p["latitude"]),
                bounds,
                draw_box,
            )
            d.ellipse(
                (px - 7, py - 7, px + 7, py + 7),
                fill=YELLOW,
                outline=RED,
                width=2,
            )
        except Exception:
            continue

    # Event centroid.
    try:
        cx, cy = _project(
            float(event["centroid_lon"]),
            float(event["centroid_lat"]),
            bounds,
            draw_box,
        )
        d.ellipse(
            (cx - 12, cy - 12, cx + 12, cy + 12),
            fill=RED,
            outline=WHITE,
            width=3,
        )
    except Exception:
        pass

    d.text(
        (x0 + 24, y1 - 44),
        f"Cyan outline: {local_label}",
        font=tiny,
        fill=MUTED,
    )


def _draw_badge(d, event: dict, small):
    label, fill, text_fill = _confidence_style(event)
    bbox = d.textbbox((0, 0), label, font=small)
    tw = bbox[2] - bbox[0]
    x1 = 1480
    x0 = x1 - tw - 48
    y0, y1 = 102, 158
    d.rounded_rectangle((x0, y0, x1, y1), radius=22, fill=fill)
    d.text((x0 + 24, y0 + 11), label, font=small, fill=text_fill)


def make_card(
    event: dict,
    detections: list[dict],
    out_path: Path,
    boundary_path: Path | None = None,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    title = _font(62, True)
    h2 = _font(34, True)
    body = _font(26)
    body_bold = _font(26, True)
    small = _font(23, True)
    tiny = _font(18)

    d.rounded_rectangle((55, 48, 1545, 850), radius=34, fill=PANEL)

    d.ellipse((95, 84, 175, 164), fill=RED)
    d.polygon(
        [(135, 96), (160, 132), (140, 125), (151, 160), (112, 132), (125, 139)],
        fill=ORANGE,
    )

    d.text((205, 78), "NEPAL FIREWATCH", font=title, fill=WHITE)
    d.text(
        (208, 148),
        "Near-real-time satellite thermal-anomaly monitoring",
        font=tiny,
        fill=MUTED,
    )
    _draw_badge(d, event, small)

    ward_no = str(event.get("ward_no") or "").strip()
    ward_name = str(event.get("ward_name") or "").strip()
    local_label = _local_label(event)
    district = str(event.get("district") or "")
    province = str(event.get("province") or "")

    if ward_no:
        ward_prefix = f"Ward {ward_no}"
        if (
            ward_name
            and ward_name.casefold()
            not in {ward_no.casefold(), f"ward {ward_no}".casefold()}
        ):
            ward_prefix += f" ({ward_name})"
        headline = f"{ward_prefix}, {local_label}"
    else:
        headline = local_label

    d.text((95, 225), headline, font=h2, fill=WHITE)
    d.text(
        (95, 274),
        ", ".join(x for x in [district, province, "Nepal"] if x),
        font=body,
        fill=MUTED,
    )

    _draw_local_map(
        d,
        event,
        detections,
        boundary_path,
        (925, 210, 1480, 700),
        tiny,
        small,
    )

    first_seen = _fmt_npt(str(event.get("first_seen_utc") or ""))
    last_seen = _fmt_npt(str(event.get("last_seen_utc") or ""))

    detection_count = int(event.get("detection_count") or len(detections))
    overpass_count = int(event.get("overpass_count") or 0)
    satellite_count = int(event.get("satellite_count") or 0)
    max_frp = event.get("max_frp")
    evidence_score = int(event.get("evidence_score") or 0)

    rows = [
        ("EVENT", str(event.get("event_id") or "—")),
        ("FIRST DETECTED", first_seen),
        ("LAST DETECTED", last_seen),
        ("DETECTIONS / OVERPASSES", f"{detection_count} / {overpass_count}"),
        ("SATELLITES", str(satellite_count)),
        ("MAX FRP", "—" if max_frp is None else f"{float(max_frp):.1f} MW"),
        ("EVIDENCE SCORE", str(evidence_score)),
    ]

    yy = 342
    for label, value in rows:
        d.text((100, yy), label, font=tiny, fill=MUTED)
        d.text(
            (400, yy - 4),
            value,
            font=body_bold if label == "EVIDENCE SCORE" else body,
            fill=WHITE,
        )
        yy += 51

    d.line((95, 755, 1480, 755), fill=GRID, width=2)
    d.text(
        (95, 778),
        "Source: NASA FIRMS VIIRS NOAA-20/NOAA-21 • Automated satellite-derived alert",
        font=tiny,
        fill=MUTED,
    )
    d.text(
        (95, 814),
        "Thermal anomaly is not ground confirmation of wildfire. Verify with local or official information.",
        font=tiny,
        fill=ORANGE,
    )

    im.save(out_path, quality=94)
    return out_path

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 900
BG = (18, 20, 24)
PANEL = (28, 31, 36)
RED = (232, 67, 62)
ORANGE = (255, 159, 67)
WHITE = (245, 247, 250)
MUTED = (170, 178, 190)
GRID = (64, 69, 78)


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for p in candidates:
        try: return ImageFont.truetype(p, size)
        except Exception: pass
    return ImageFont.load_default()


def _fmt_dt(s: str) -> str:
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return s


def make_card(event: dict, detections: list[dict], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    title = _font(66, True); h2 = _font(38, True); body = _font(31); small = _font(24); tiny = _font(20)

    d.rounded_rectangle((55, 48, 1545, 850), radius=34, fill=PANEL)
    d.ellipse((95, 84, 175, 164), fill=RED)
    d.polygon([(135,96),(160,132),(140,125),(151,160),(112,132),(125,139)], fill=ORANGE)
    d.text((205, 78), "NEPAL FIREWATCH", font=title, fill=WHITE)
    d.text((208, 151), "Near-real-time satellite thermal-anomaly alert", font=small, fill=MUTED)

    local = event.get("local_name") or "Unknown local level"
    local_type = event.get("local_type") or ""
    district = event.get("district") or ""
    province = event.get("province") or ""
    d.text((95, 235), f"{local} {local_type}".strip(), font=h2, fill=WHITE)
    d.text((95, 290), f"{district}, {province}, Nepal".replace(", ,", ","), font=body, fill=MUTED)

    # Mini-map panel: relative coordinates only, intentionally no external basemap dependency.
    x0, y0, x1, y1 = 930, 235, 1480, 690
    d.rounded_rectangle((x0, y0, x1, y1), radius=26, fill=(20,23,27), outline=GRID, width=2)
    for gx in range(x0+50, x1, 100): d.line((gx,y0+20,gx,y1-20), fill=GRID, width=1)
    for gy in range(y0+50, y1, 100): d.line((x0+20,gy,x1-20,gy), fill=GRID, width=1)
    lats = [x["latitude"] for x in detections] or [event["centroid_lat"]]
    lons = [x["longitude"] for x in detections] or [event["centroid_lon"]]
    lat0, lat1 = min(lats), max(lats); lon0, lon1 = min(lons), max(lons)
    pad_lat = max((lat1-lat0)*0.3, 0.01); pad_lon = max((lon1-lon0)*0.3, 0.01)
    lat0 -= pad_lat; lat1 += pad_lat; lon0 -= pad_lon; lon1 += pad_lon
    for p in detections:
        px = x0+35 + (p["longitude"]-lon0)/(lon1-lon0)*(x1-x0-70)
        py = y1-35 - (p["latitude"]-lat0)/(lat1-lat0)*(y1-y0-70)
        d.ellipse((px-13,py-13,px+13,py+13), fill=RED, outline=ORANGE, width=4)
    d.text((x0+24, y1-52), "VIIRS detections (relative view)", font=tiny, fill=MUTED)

    rows = [
        ("Event", event["event_id"]),
        ("First detected (UTC)", _fmt_dt(event["first_seen_utc"])),
        ("Detections", str(event["detection_count"])),
        ("Max FRP", "—" if event.get("max_frp") is None else f"{event['max_frp']:.1f} MW"),
        ("Centroid", f"{event['centroid_lat']:.4f}, {event['centroid_lon']:.4f}"),
    ]
    yy = 390
    for label, value in rows:
        d.text((100, yy), label.upper(), font=tiny, fill=MUTED)
        d.text((365, yy-4), value, font=body, fill=WHITE)
        yy += 63

    d.line((95, 760, 1480, 760), fill=GRID, width=2)
    d.text((95, 785), "Source: NASA FIRMS VIIRS NOAA-20/NOAA-21 • Automated alert", font=small, fill=MUTED)
    d.text((95, 822), "Satellite thermal anomaly ≠ confirmed wildfire. Verify with local/official information.", font=tiny, fill=ORANGE)
    im.save(out_path, quality=94)
    return out_path

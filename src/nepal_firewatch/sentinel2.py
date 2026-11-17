from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DEFAULT_STAC_URL = "https://earth-search.aws.element84.com/v1"
DEFAULT_COLLECTION = "sentinel-2-l2a"


def _parse_utc(value):
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _visual_href(item):
    return (((item.get("assets") or {}).get("visual") or {}).get("href"))


def _cloud(item):
    try:
        return float((item.get("properties") or {}).get("eo:cloud_cover"))
    except (TypeError, ValueError):
        return 999.0


def _scene_dt(item):
    props = item.get("properties") or {}
    value = props.get("datetime") or props.get("start_datetime")
    if not value:
        raise ValueError("STAC item has no datetime")
    return _parse_utc(value)


def select_scene(features, target_utc, max_cloud_cover=60.0):
    target = _parse_utc(target_utc)
    candidates = []
    for item in features:
        if not _visual_href(item):
            continue
        cloud = _cloud(item)
        if cloud > float(max_cloud_cover):
            continue
        try:
            dt = _scene_dt(item)
        except Exception:
            continue
        delta = abs((dt - target).total_seconds())
        before_penalty = 1 if dt < target else 0
        candidates.append((delta, before_penalty, cloud, str(item.get("id") or ""), item))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    return candidates[0][4]


def search_best_scene(
    lat,
    lon,
    event_utc,
    *,
    stac_url=DEFAULT_STAC_URL,
    collection=DEFAULT_COLLECTION,
    days_before=7,
    days_after=7,
    max_cloud_cover=60.0,
    now_utc=None,
    session=None,
    timeout=30,
):
    event_dt = _parse_utc(event_utc)
    now = _parse_utc(now_utc or datetime.now(timezone.utc))
    start = event_dt - timedelta(days=int(days_before))
    end = min(event_dt + timedelta(days=int(days_after)), now)
    payload = {
        "collections": [collection],
        "intersects": {"type": "Point", "coordinates": [float(lon), float(lat)]},
        "datetime": f"{_iso_z(start)}/{_iso_z(end)}",
        "limit": 30,
    }
    s = session or requests.Session()
    s.headers.setdefault("User-Agent", "NepalFireWatch/0.2 Sentinel-2")
    r = s.post(f"{stac_url.rstrip('/')}/search", json=payload, timeout=timeout)
    r.raise_for_status()
    return select_scene(r.json().get("features") or [], event_dt, max_cloud_cover)


def render_context_image(item, *, lat, lon, out_path, context_km=8.0, image_size=720):
    import numpy as np
    import rasterio
    from PIL import Image, ImageDraw, ImageFont
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds
    from rasterio.warp import transform

    href = _visual_href(item)
    if not href:
        raise ValueError("Selected STAC item has no visual asset")

    size = int(image_size)
    half_m = float(context_km) * 500.0

    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        GDAL_HTTP_MULTIRANGE="YES",
        VSI_CACHE="TRUE",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF",
    ):
        with rasterio.open(href) as src:
            if src.crs is None:
                raise ValueError("Sentinel-2 asset has no CRS")
            xs, ys = transform("EPSG:4326", src.crs, [float(lon)], [float(lat)])
            cx, cy = float(xs[0]), float(ys[0])
            window = from_bounds(
                cx-half_m, cy-half_m, cx+half_m, cy+half_m,
                transform=src.transform,
            )
            data = src.read(
                [1, 2, 3],
                window=window,
                out_shape=(3, size, size),
                boundless=True,
                fill_value=0,
                resampling=Resampling.bilinear,
            )

    if not np.any(data):
        raise ValueError("Sentinel-2 crop contained no valid pixels")

    if data.dtype != np.uint8:
        rgb = np.empty(data.shape, dtype=np.uint8)
        for i in range(3):
            band = data[i].astype("float32")
            good = np.isfinite(band) & (band > 0)
            if not np.any(good):
                rgb[i] = 0
            else:
                lo, hi = np.percentile(band[good], [2, 98])
                if hi <= lo:
                    rgb[i] = 0
                else:
                    rgb[i] = np.clip((band-lo) * 255.0 / (hi-lo), 0, 255).astype(np.uint8)
        data = rgb

    image = Image.fromarray(np.transpose(data, (1, 2, 0)), mode="RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    c = size // 2
    draw.ellipse((c-12, c-12, c+12, c+12), fill=(232,67,62,220), outline=(255,255,255,255), width=3)

    props = item.get("properties") or {}
    scene_time = str(props.get("datetime") or "")
    try:
        cloud_text = f"{float(props.get('eo:cloud_cover')):.0f}% scene cloud"
    except (TypeError, ValueError):
        cloud_text = "cloud unknown"

    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    draw.rectangle((0, 0, size, 42), fill=(0,0,0,150))
    draw.text((12, 11), f"Sentinel-2 L2A • {scene_time[:10]} • {cloud_text}", font=font, fill=(255,255,255,255))
    draw.rectangle((0, size-38, size, size), fill=(0,0,0,150))
    draw.text((12, size-28), "Context only — not fire confirmation.", font=font, fill=(255,255,255,255))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, "JPEG", quality=90, optimize=True)
    return out_path


def build_context(event, out_path, **kwargs):
    checked = _iso_z(datetime.now(timezone.utc))
    try:
        item = search_best_scene(
            event["centroid_lat"],
            event["centroid_lon"],
            event["first_seen_utc"],
            stac_url=kwargs.get("stac_url", DEFAULT_STAC_URL),
            collection=kwargs.get("collection", DEFAULT_COLLECTION),
            days_before=kwargs.get("days_before", 7),
            days_after=kwargs.get("days_after", 7),
            max_cloud_cover=kwargs.get("max_cloud_cover", 60.0),
        )
        if item is None:
            return {"status": "unavailable", "checked_utc": checked, "error": "No qualifying Sentinel-2 scene found."}

        render_context_image(
            item,
            lat=event["centroid_lat"],
            lon=event["centroid_lon"],
            out_path=out_path,
            context_km=kwargs.get("context_km", 8.0),
            image_size=kwargs.get("image_size", 720),
        )
        props = item.get("properties") or {}
        source_url = ""
        for link in item.get("links") or []:
            if link.get("rel") in {"self", "canonical"} and link.get("href"):
                source_url = link["href"]
                break
        return {
            "status": "available",
            "path": str(out_path),
            "scene_id": str(item.get("id") or ""),
            "datetime_utc": str(props.get("datetime") or ""),
            "cloud_cover": props.get("eo:cloud_cover"),
            "source_url": source_url,
            "checked_utc": checked,
            "error": "",
        }
    except Exception as exc:
        return {"status": "error", "checked_utc": checked, "error": f"{type(exc).__name__}: {exc}"[:500]}


def needs_check(event, *, now_utc=None, retry_hours=12.0, force=False):
    if event.get("sentinel2_path"):
        return False
    if force:
        return True
    if str(event.get("lifecycle_state") or "").upper() == "CLOSED":
        return False
    checked = event.get("sentinel2_checked_utc")
    if not checked:
        return True
    now = _parse_utc(now_utc or datetime.now(timezone.utc))
    previous = _parse_utc(checked)
    return (now-previous).total_seconds()/3600.0 >= float(retry_hours)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lat", required=True, type=float)
    p.add_argument("--lon", required=True, type=float)
    p.add_argument("--time", required=True)
    p.add_argument("--out", default="sentinel2_context_test.jpg")
    p.add_argument("--cloud", type=float, default=60.0)
    p.add_argument("--context-km", type=float, default=8.0)
    args = p.parse_args()
    event = {
        "event_id": "manual-test",
        "centroid_lat": args.lat,
        "centroid_lon": args.lon,
        "first_seen_utc": args.time,
    }
    result = build_context(event, Path(args.out), max_cloud_cover=args.cloud, context_km=args.context_km)
    if result.get("status") == "available":
        result["path"] = args.out
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

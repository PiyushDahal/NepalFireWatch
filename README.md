# Nepal FireWatch v0.1

An open-source-style pipeline for near-real-time satellite thermal-anomaly monitoring in Nepal using NASA FIRMS VIIRS data.

## What it does

1. Queries NASA FIRMS Area API for **VIIRS NOAA-20 NRT** and **VIIRS NOAA-21 NRT**.
2. Filters low-confidence detections (default: keep nominal + high).
3. Keeps only points that fall inside Nepal local-level polygons.
4. Assigns province, district and municipality/rural municipality/special-area names.
5. Deduplicates detections in SQLite.
6. Groups nearby detections into fire events using configurable distance/time thresholds.
7. Creates a 1600×900 social-media alert card for each updated event.
8. Saves all history to SQLite.
9. Exports `events.geojson`, `detections.geojson`, and `summary.json` for a Leaflet web map.
10. Includes a GitHub Actions workflow that can run every 30 minutes.



## Data sources

- NASA FIRMS Area API: `https://firms.modaps.eosdis.nasa.gov/api/area`
- Nepal local-level boundaries: Young Innovations `nepal-locallevel-map` repository (MIT-licensed)

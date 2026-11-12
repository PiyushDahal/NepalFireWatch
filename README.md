# Nepal FireWatch v0.1

A first working, open-source-style pipeline for near-real-time satellite thermal-anomaly monitoring in Nepal using NASA FIRMS VIIRS data.

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

> **Important:** A VIIRS active-fire/thermal-anomaly detection is not by itself proof of an uncontrolled wildfire. Public alerts should retain this distinction.

## Project structure

```text
NepalFireWatch/
├── run.py
├── requirements.txt
├── .env.example
├── README.md
├── src/nepal_firewatch/
│   ├── config.py
│   ├── firms.py
│   ├── normalize.py
│   ├── boundaries.py
│   ├── db.py
│   ├── events.py
│   ├── cards.py
│   ├── export.py
│   ├── pipeline.py
│   └── utils.py
├── samples/
│   ├── demo_firms.csv
│   └── demo_boundaries.geojson
├── data/
│   └── cache/
├── docs/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   ├── cards/
│   └── data/
├── tests/
└── .github/workflows/firewatch.yml
```

## 1. Install

Python 3.11 is recommended.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
```

## 2. Test immediately with the bundled demo

```bash
python run.py --demo
```

Expected first-run pattern:

```text
Nepal FireWatch complete | fetched=4 | new_detections=3 | new_events=2
```

A second run should report zero new detections because the SQLite database remembers them.

To reset the demo:

```bash
# Windows
 del data\firewatch_demo.sqlite

# macOS/Linux
rm -f data/firewatch_demo.sqlite
```

## 3. View the web map

From the project root:

```bash
python -m http.server 8000 --directory docs
```

Open `http://localhost:8000`.

## 4. Activate live NASA FIRMS data

Request a free FIRMS MAP_KEY:

https://firms.modaps.eosdis.nasa.gov/api/map_key/

Copy `.env.example` to `.env` and set:

```env
FIRMS_MAP_KEY=YOUR_KEY_HERE
```

Run:

```bash
python run.py
```

The live run automatically downloads/caches the Nepal local-level GeoJSON from the Young Innovations public repository.

## 5. Configuration

`.env` supports:

```env
NFW_DB_PATH=data/firewatch.sqlite
NFW_LOOKBACK_DAYS=1
NFW_CLUSTER_KM=3.0
NFW_CLUSTER_HOURS=12
NFW_MIN_CONFIDENCE=nominal
```

`NFW_LOOKBACK_DAYS` must remain between 1 and 5 for the FIRMS Area API.

## 6. GitHub Actions automation

1. Push this project to GitHub.
2. Repository → **Settings → Secrets and variables → Actions**.
3. Add repository secret `FIRMS_MAP_KEY`.
4. Enable GitHub Actions.
5. The bundled workflow runs at minutes 07 and 37 of every hour and commits updated SQLite/map/card outputs.
6. Enable GitHub Pages using the `docs/` folder if you want a public live map.

For production, consider moving long-term history from the Git repository to an external database/object store once the data volume grows.

## 7. Run tests

```bash
pytest -q
```

## Data sources

- NASA FIRMS Area API: `https://firms.modaps.eosdis.nasa.gov/api/area`
- Nepal local-level boundaries: Young Innovations `nepal-locallevel-map` repository (MIT-licensed)

## Recommended v0.2 upgrades

- Sentinel-2 before/current image retrieval around each VIIRS event.
- Persistent-hotspot masks and snow/water/industrial false-positive filters.
- Protected-area overlays.
- Weather/wind context.
- Facebook Page and X publishing adapters.
- Web push notifications.
- Event lifecycle logic (active, cooling, closed, reactivated).
- Burned-area and growth estimation.

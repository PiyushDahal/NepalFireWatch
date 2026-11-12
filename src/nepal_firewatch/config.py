from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Settings:
    firms_map_key: str = os.getenv("FIRMS_MAP_KEY", "").strip()
    bbox: str = "79.9,26.2,88.4,30.6"  # west,south,east,north
    sources: tuple[str, ...] = ("VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")
    lookback_days: int = int(os.getenv("NFW_LOOKBACK_DAYS", "1"))
    cluster_km: float = float(os.getenv("NFW_CLUSTER_KM", "3.0"))
    cluster_hours: float = float(os.getenv("NFW_CLUSTER_HOURS", "12"))
    min_confidence: str = os.getenv("NFW_MIN_CONFIDENCE", "nominal").lower()
    db_path: Path = ROOT / os.getenv("NFW_DB_PATH", "data/firewatch.sqlite")
    boundary_path: Path = ROOT / "data/cache/nepal_local_levels.geojson"
    boundary_url: str = "https://raw.githubusercontent.com/younginnovations/nepal-locallevel-map/master/out/municipalities.simplified.geojson"
    docs_dir: Path = ROOT / "docs"
    cards_dir: Path = ROOT / "docs/cards"
    map_data_dir: Path = ROOT / "docs/data"
    demo_csv: Path = ROOT / "samples/demo_firms.csv"
    demo_boundary_path: Path = ROOT / "samples/demo_boundaries.geojson"

SETTINGS = Settings()

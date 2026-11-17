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
    lifecycle_quiet_hours: float = float(os.getenv("NFW_LIFECYCLE_QUIET_HOURS", "8"))
    lifecycle_closed_hours: float = float(os.getenv("NFW_LIFECYCLE_CLOSED_HOURS", "24"))
    lifecycle_active_overpasses: int = int(os.getenv("NFW_LIFECYCLE_ACTIVE_OVERPASSES", "2"))
    lifecycle_persistent_overpasses: int = int(os.getenv("NFW_LIFECYCLE_PERSISTENT_OVERPASSES", "3"))
    lifecycle_active_duration_hours: float = float(os.getenv("NFW_LIFECYCLE_ACTIVE_DURATION_HOURS", "1"))
    lifecycle_persistent_duration_hours: float = float(os.getenv("NFW_LIFECYCLE_PERSISTENT_DURATION_HOURS", "12"))
    sentinel2_enabled: bool = os.getenv("NFW_S2_ENABLED", "1").lower() not in {"0","false","no","off"}
    sentinel2_stac_url: str = os.getenv("NFW_S2_STAC_URL", "https://earth-search.aws.element84.com/v1").rstrip("/")
    sentinel2_collection: str = os.getenv("NFW_S2_COLLECTION", "sentinel-2-l2a")
    sentinel2_days_before: int = int(os.getenv("NFW_S2_DAYS_BEFORE", "7"))
    sentinel2_days_after: int = int(os.getenv("NFW_S2_DAYS_AFTER", "7"))
    sentinel2_max_cloud: float = float(os.getenv("NFW_S2_MAX_CLOUD", "60"))
    sentinel2_context_km: float = float(os.getenv("NFW_S2_CONTEXT_KM", "8"))
    sentinel2_image_size: int = int(os.getenv("NFW_S2_IMAGE_SIZE", "720"))
    sentinel2_retry_hours: float = float(os.getenv("NFW_S2_RETRY_HOURS", "12"))
    sentinel2_max_events_per_run: int = int(os.getenv("NFW_S2_MAX_EVENTS_PER_RUN", "3"))
    db_path: Path = ROOT / os.getenv("NFW_DB_PATH", "data/firewatch.sqlite")
    boundary_path: Path = ROOT / "data/cache/nepal_local_levels_oknp.geojson"
    boundary_url: str = "https://raw.githubusercontent.com/openknowledgenp/localboundaries/gh-pages/public/data/local-level/nepal.geojson"
    docs_dir: Path = ROOT / "docs"
    cards_dir: Path = ROOT / "docs/cards"
    map_data_dir: Path = ROOT / "docs/data"
    sentinel2_dir: Path = ROOT / "docs/event_imagery"
    demo_csv: Path = ROOT / "samples/demo_firms.csv"
    demo_boundary_path: Path = ROOT / "samples/demo_boundaries.geojson"

SETTINGS = Settings()

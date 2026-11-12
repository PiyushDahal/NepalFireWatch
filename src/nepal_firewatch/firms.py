from __future__ import annotations
from io import StringIO
from pathlib import Path
import pandas as pd
import requests

BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def fetch_source(map_key: str, source: str, bbox: str, day_range: int = 1, timeout: int = 60) -> pd.DataFrame:
    if not map_key:
        raise ValueError("FIRMS_MAP_KEY is missing. Copy .env.example to .env and add your free NASA FIRMS MAP_KEY.")
    if not 1 <= int(day_range) <= 5:
        raise ValueError("NASA FIRMS Area API day_range must be between 1 and 5.")
    url = f"{BASE}/{map_key}/{source}/{bbox}/{int(day_range)}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    text = response.text.strip()
    if not text:
        return pd.DataFrame()
    # FIRMS errors can occasionally arrive as plain text.
    if text.lower().startswith("error"):
        raise RuntimeError(text)
    df = pd.read_csv(StringIO(text))
    if not df.empty:
        df["source"] = source
    return df


def fetch_all(map_key: str, sources: tuple[str, ...], bbox: str, day_range: int = 1) -> pd.DataFrame:
    frames = [fetch_source(map_key, s, bbox, day_range) for s in sources]
    nonempty = [f for f in frames if not f.empty]
    return pd.concat(nonempty, ignore_index=True) if nonempty else pd.DataFrame()


def load_demo(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

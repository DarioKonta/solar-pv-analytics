"""Open-Meteo Historical Weather API: hourly irradiance, cloud cover, temperature.

Docs: https://open-meteo.com/en/docs/historical-weather-api
"""
from __future__ import annotations

import logging

import pandas as pd

from src.config import RAW_DIR, date_range, settings
from src.extract.chunks import is_recent, years
from src.extract.pvgis import _slug
from src.http_client import ApiClient

log = logging.getLogger(__name__)

URL = "https://archive-api.open-meteo.com/v1/archive"
OUT = RAW_DIR / "open_meteo"


def download(refresh: bool = False) -> None:
    client = ApiClient()
    start, end = date_range()
    variables = ",".join(settings()["weather_variables"])
    for loc in settings()["locations"]:
        for y_start, y_end in years(start, end):
            client.cached(
                OUT / _slug(loc["name"]) / f"{y_start.year}.json",
                URL,
                {"latitude": loc["lat"], "longitude": loc["lon"],
                 "start_date": y_start.isoformat(), "end_date": y_end.isoformat(),
                 "hourly": variables, "timezone": "UTC"},
                refresh=refresh or is_recent(y_end),
            )
        log.info("open-meteo: %s done", loc["name"])


def parse_hourly(raw: dict, location: str) -> pd.DataFrame:
    """ts_utc + one column per weather variable."""
    hourly = dict(raw["hourly"])
    df = pd.DataFrame(hourly)
    df["ts_utc"] = pd.to_datetime(df.pop("time"), utc=True)
    df["location"] = location
    return df[["ts_utc", "location", *[c for c in hourly if c != "time"]]]

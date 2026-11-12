"""Energy-Charts API (Fraunhofer ISE): generation, prices, installed capacity.

Docs: https://api.energy-charts.info/
"""
from __future__ import annotations

import logging

import pandas as pd

from src.config import RAW_DIR, date_range, settings
from src.extract.chunks import is_recent, quarters
from src.http_client import ApiClient

log = logging.getLogger(__name__)

BASE = "https://api.energy-charts.info"
OUT = RAW_DIR / "energy_charts"


def _client() -> ApiClient:
    return ApiClient(delay_s=settings()["http"]["energy_charts_delay_s"])


def download(refresh: bool = False) -> None:
    client = _client()
    start, end = date_range()
    for c in settings()["countries"]:
        code, bzn = c["code"], c["bzn"]
        for q_start, q_end in quarters(start, end):
            tag = f"{q_start:%Y%m%d}_{q_end:%Y%m%d}"
            fresh = refresh or is_recent(q_end)
            client.cached(
                OUT / "public_power" / code / f"{tag}.json",
                f"{BASE}/public_power",
                {"country": code, "start": q_start.isoformat(), "end": q_end.isoformat()},
                refresh=fresh,
            )
            client.cached(
                OUT / "price" / bzn / f"{tag}.json",
                f"{BASE}/price",
                {"bzn": bzn, "start": q_start.isoformat(), "end": q_end.isoformat()},
                refresh=fresh,
            )
        client.cached(
            OUT / "installed_power" / f"{code}.json",
            f"{BASE}/installed_power",
            {"country": code, "time_step": "yearly"},
            refresh=True,
        )
        log.info("energy-charts: %s done", code)


# ---------- parsers: raw JSON -> tidy DataFrames ----------

def parse_public_power(raw: dict, country: str) -> pd.DataFrame:
    """Long format: ts_utc, country, production_type, mw."""
    ts = pd.to_datetime(raw["unix_seconds"], unit="s", utc=True)
    frames = [
        pd.DataFrame({"ts_utc": ts, "production_type": p["name"], "mw": p["data"]})
        for p in raw.get("production_types", [])
    ]
    if not frames:
        return pd.DataFrame(columns=["ts_utc", "country", "production_type", "mw"])
    df = pd.concat(frames, ignore_index=True)
    df["country"] = country
    df["mw"] = pd.to_numeric(df["mw"], errors="coerce")
    return df[["ts_utc", "country", "production_type", "mw"]]


def parse_price(raw: dict, bzn: str) -> pd.DataFrame:
    """ts_utc, bzn, price_eur_mwh."""
    df = pd.DataFrame({
        "ts_utc": pd.to_datetime(raw["unix_seconds"], unit="s", utc=True),
        "price_eur_mwh": pd.to_numeric(pd.Series(raw["price"]), errors="coerce"),
    })
    df["bzn"] = bzn
    return df[["ts_utc", "bzn", "price_eur_mwh"]]


def parse_installed_power(raw: dict, country: str) -> pd.DataFrame:
    """year, country, production_type, gw."""
    years = [int(str(t)[:4]) for t in raw["time"]]
    frames = [
        pd.DataFrame({"year": years, "production_type": p["name"], "gw": p["data"]})
        for p in raw.get("production_types", [])
    ]
    df = pd.concat(frames, ignore_index=True)
    df["country"] = country
    df["gw"] = pd.to_numeric(df["gw"], errors="coerce")
    return df[["year", "country", "production_type", "gw"]]

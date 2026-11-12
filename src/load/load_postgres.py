"""Load cached raw JSON into the PostgreSQL `raw` schema.

Full reload: each table is truncated and refilled with COPY (fast, idempotent).
Usage:  python -m src.load.load_postgres
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from src.config import RAW_DIR, ROOT, settings
from src.db import connect, run_sql_file
from src.extract import energy_charts as ec
from src.extract import open_meteo as om
from src.extract import pvgis
from src.extract.pvgis import _slug

log = logging.getLogger(__name__)
SQL_DIR = ROOT / "sql"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_df(table: str, df: pd.DataFrame, key: list[str], truncate: bool = True) -> None:
    """Truncate `table` and COPY the DataFrame into it (duplicates on `key` dropped first)."""
    df = df.drop_duplicates(subset=key, keep="last")
    df = df.astype(object).where(pd.notna(df), None)
    cols = ", ".join(df.columns)
    with connect() as conn, conn.cursor() as cur:
        if truncate:
            cur.execute(f"TRUNCATE {table}")
        with cur.copy(f"COPY {table} ({cols}) FROM STDIN") as cp:
            for row in df.itertuples(index=False, name=None):
                cp.write_row(row)
    log.info("%-22s %10s rows", table, f"{len(df):,}")


def load_dimensions() -> None:
    countries = pd.DataFrame([
        {"country_code": c["code"], "bzn": c["bzn"], "country_name": c["name"], "is_focus": c.get("focus", False)}
        for c in settings()["countries"]
    ])
    locations = pd.DataFrame([
        {"location": l["name"], "country_code": l["country"], "lat": l["lat"], "lon": l["lon"]}
        for l in settings()["locations"]
    ])
    with connect() as conn:
        conn.execute("TRUNCATE raw.location, raw.country")
    copy_df("raw.country", countries, ["country_code"], truncate=False)
    copy_df("raw.location", locations, ["location"], truncate=False)


def load_energy_charts() -> None:
    base = RAW_DIR / "energy_charts"
    power, price, cap = [], [], []
    for c in settings()["countries"]:
        power += [ec.parse_public_power(_read(f), c["code"])
                  for f in sorted((base / "public_power" / c["code"]).glob("*.json"))]
        price += [ec.parse_price(_read(f), c["bzn"])
                  for f in sorted((base / "price" / c["bzn"]).glob("*.json"))]
        cap.append(ec.parse_installed_power(_read(base / "installed_power" / f"{c['code']}.json"), c["code"]))
    power_df = pd.concat(power).rename(columns={"country": "country_code"})
    copy_df("raw.public_power", power_df.dropna(subset=["mw"]), ["country_code", "production_type", "ts_utc"])
    copy_df("raw.price", pd.concat(price).dropna(subset=["price_eur_mwh"]), ["bzn", "ts_utc"])
    copy_df("raw.installed_power", pd.concat(cap).rename(columns={"country": "country_code"}),
            ["country_code", "production_type", "year"])


def load_pvgis() -> None:
    rows, monthly = [], []
    for loc in settings()["locations"]:
        for f in sorted((RAW_DIR / "pvgis" / _slug(loc["name"])).glob("*.json")):
            raw = _read(f)
            rows.append(pvgis.parse_pvcalc(raw, loc["name"], f.stem))
            if f.stem == "optimal":
                monthly.append(pvgis.parse_monthly(raw, loc["name"]))
    copy_df("raw.pvgis_yield", pd.DataFrame(rows), ["location", "scenario"])
    copy_df("raw.pvgis_monthly", pd.concat(monthly), ["location", "month"])


def load_weather() -> None:
    frames = [om.parse_hourly(_read(f), loc["name"])
              for loc in settings()["locations"]
              for f in sorted((RAW_DIR / "open_meteo" / _slug(loc["name"])).glob("*.json"))]
    copy_df("raw.weather_hourly", pd.concat(frames), ["location", "ts_utc"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_sql_file(SQL_DIR / "01_schema.sql")
    load_dimensions()
    load_pvgis()
    load_weather()
    load_energy_charts()
    log.info("raw layer loaded")


if __name__ == "__main__":
    main()

"""PVGIS (EU Joint Research Centre): expected PV yield for a location and panel orientation.

Docs: https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/api-non-interactive-service_en
"""
from __future__ import annotations

import logging

import pandas as pd

from src.config import RAW_DIR, settings
from src.http_client import ApiClient

log = logging.getLogger(__name__)

URL = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
OUT = RAW_DIR / "pvgis"


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def download(refresh: bool = False) -> None:
    cfg = settings()["pvgis"]
    client = ApiClient()
    for loc in settings()["locations"]:
        base = {"lat": loc["lat"], "lon": loc["lon"], "peakpower": 1,
                "loss": cfg["loss_pct"], "outputformat": "json"}
        folder = OUT / _slug(loc["name"])
        # 1) optimal tilt + azimuth chosen by PVGIS
        client.cached(folder / "optimal.json", URL, {**base, "optimalangles": 1}, refresh)
        # 2) only Serbian cities get the full orientation grid (used for Q1)
        if loc["country"] != "rs":
            continue
        for az_name, az in cfg["azimuths"].items():
            for tilt in cfg["tilts"]:
                client.cached(folder / f"tilt{tilt}_{az_name}.json", URL,
                              {**base, "angle": tilt, "aspect": az}, refresh)
        log.info("pvgis: %s done", loc["name"])


# ---------- parsers ----------

def parse_pvcalc(raw: dict, location: str, scenario: str) -> dict:
    """One row per (location, scenario) with annual yield."""
    fixed = raw["inputs"]["mounting_system"]["fixed"]
    totals = raw["outputs"]["totals"]["fixed"]
    return {
        "location": location,
        "scenario": scenario,
        "tilt_deg": fixed["slope"]["value"],
        "azimuth_deg": fixed["azimuth"]["value"],
        "yield_kwh_per_kwp": totals["E_y"],
        "irradiation_kwh_m2": totals["H(i)_y"],
        "year_to_year_sd_kwh": totals["SD_y"],
        "total_loss_pct": totals["l_total"],
    }


def parse_monthly(raw: dict, location: str) -> pd.DataFrame:
    rows = raw["outputs"]["monthly"]["fixed"]
    return pd.DataFrame({
        "location": location,
        "month": [r["month"] for r in rows],
        "yield_kwh_per_kwp": [r["E_m"] for r in rows],
        "irradiation_kwh_m2": [r["H(i)_m"] for r in rows],
    })

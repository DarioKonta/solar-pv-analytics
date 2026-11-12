"""Load project settings and define common paths."""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "settings.yaml"
RAW_DIR = ROOT / "data" / "raw"


@lru_cache
def settings() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def date_range() -> tuple[date, date]:
    dr = settings()["date_range"]
    start = date.fromisoformat(dr["start"])
    end = date.fromisoformat(dr["end"]) if dr.get("end") else date.today()
    return start, end

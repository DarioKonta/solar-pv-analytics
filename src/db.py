"""Database connection helpers (credentials from .env)."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine

from src.config import ROOT

load_dotenv(ROOT / ".env")


def _params() -> dict:
    return {
        "host": os.getenv("PG_HOST", "localhost"),
        "port": int(os.getenv("PG_PORT", "5432")),
        "dbname": os.getenv("PG_DB", "solar_pv"),
        "user": os.getenv("PG_USER", "postgres"),
        "password": os.environ["PG_PASSWORD"],
    }


def connect() -> psycopg.Connection:
    return psycopg.connect(**_params())


def engine() -> Engine:
    p = _params()
    return create_engine(URL.create("postgresql+psycopg", username=p["user"], password=p["password"],
                                    host=p["host"], port=p["port"], database=p["dbname"]))


def run_sql_file(path: Path) -> None:
    with connect() as conn:
        conn.execute(path.read_text(encoding="utf-8"))

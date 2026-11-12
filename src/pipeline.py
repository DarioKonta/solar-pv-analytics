"""Run the whole pipeline: extract -> load raw -> staging -> marts.

Usage:
    python -m src.pipeline              # uses cached raw data where possible
    python -m src.pipeline --skip-extract
"""
from __future__ import annotations

import argparse
import logging
import time

from src.config import ROOT
from src.db import run_sql_file
from src.extract import run as extract
from src.load import load_postgres

log = logging.getLogger("pipeline")
SQL_STEPS = ["02_staging.sql", "03_marts.sql"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-extract", action="store_true", help="only rebuild the database from data/raw")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    t0 = time.monotonic()
    if not args.skip_extract:
        for name, module in extract.SOURCES.items():
            log.info("extract: %s", name)
            module.download()
    load_postgres.main()
    for f in SQL_STEPS:
        log.info("sql: %s", f)
        run_sql_file(ROOT / "sql" / f)
    log.info("pipeline finished in %.0f s", time.monotonic() - t0)


if __name__ == "__main__":
    main()

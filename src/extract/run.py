"""Download all raw data.

Usage:
    python -m src.extract.run                 # all sources
    python -m src.extract.run pvgis open_meteo
    python -m src.extract.run --refresh       # ignore cache
"""
from __future__ import annotations

import argparse
import logging

from src.extract import energy_charts, open_meteo, pvgis

SOURCES = {"pvgis": pvgis, "open_meteo": open_meteo, "energy_charts": energy_charts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("sources", nargs="*", help=f"any of: {', '.join(SOURCES)} (default: all)")
    parser.add_argument("--refresh", action="store_true", help="re-download even if cached")
    args = parser.parse_args()
    unknown = set(args.sources) - set(SOURCES)
    if unknown:
        parser.error(f"unknown source(s): {', '.join(sorted(unknown))}")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for name in args.sources or SOURCES:
        logging.info("=== %s ===", name)
        SOURCES[name].download(refresh=args.refresh)


if __name__ == "__main__":
    main()

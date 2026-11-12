"""Polite HTTP client: fixed delay between calls, retry with backoff, raw JSON cache.

Every API response is saved under data/raw/ so the pipeline can be re-run
without downloading everything again (and without hitting rate limits).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

from src.config import settings

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}


class ApiClient:
    def __init__(self, delay_s: float | None = None):
        cfg = settings()["http"]
        self.delay_s = cfg["default_delay_s"] if delay_s is None else delay_s
        self.max_retries = cfg["max_retries"]
        self.timeout_s = cfg["timeout_s"]
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "solar-pv-analytics (portfolio project)"
        self._last_call = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.delay_s:
            time.sleep(self.delay_s - elapsed)

    def get_json(self, url: str, params: dict) -> dict | list:
        for attempt in range(self.max_retries + 1):
            self._wait()
            self._last_call = time.monotonic()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout_s)
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise
                wait = 2 ** attempt * 5
                log.warning("Network error %s, retrying in %ss", exc, wait)
                time.sleep(wait)
                continue
            if resp.status_code in RETRY_STATUS and attempt < self.max_retries:
                retry_after = resp.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt * 10
                log.warning("HTTP %s from %s, retrying in %ss", resp.status_code, url, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("unreachable")

    def cached(self, path: Path, url: str, params: dict, refresh: bool = False) -> dict | list:
        """Return cached JSON if present (and not refresh), else download and save it."""
        if path.exists() and not refresh:
            return json.loads(path.read_text(encoding="utf-8"))
        data = self.get_json(url, params)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)
        log.info("saved %s/%s", path.parent.name, path.name)
        return data

"""Split a date range into calendar chunks (quarters or years)."""
from __future__ import annotations

from datetime import date, timedelta


def quarters(start: date, end: date) -> list[tuple[date, date]]:
    """Inclusive (first_day, last_day) per calendar quarter, clipped to [start, end]."""
    out = []
    q_start = date(start.year, 3 * ((start.month - 1) // 3) + 1, 1)
    while q_start <= end:
        next_month = q_start.month + 3
        q_next = date(q_start.year + (next_month > 12), (next_month - 1) % 12 + 1, 1)
        out.append((max(q_start, start), min(q_next - timedelta(days=1), end)))
        q_start = q_next
    return out


def years(start: date, end: date) -> list[tuple[date, date]]:
    return [
        (max(date(y, 1, 1), start), min(date(y, 12, 31), end))
        for y in range(start.year, end.year + 1)
    ]


def is_recent(chunk_end: date, today: date | None = None, days: int = 7) -> bool:
    """Chunks touching the last few days may still change, so they get re-downloaded."""
    today = today or date.today()
    return chunk_end >= today - timedelta(days=days)

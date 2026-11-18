"""Optional high-impact news blackout. No calendar ships with the repo."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path


def load_calendar(path: Path | None) -> list[dict] | None:
    if path is None or not Path(path).exists():
        return None
    events = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            stamp = datetime.fromisoformat(row["time_utc"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            events.append({
                "time": stamp.astimezone(timezone.utc),
                "currency": row["currency"].upper().strip(),
                "impact": row["impact"].lower().strip(),
                "title": row.get("title", ""),
            })
    return events


def in_blackout(currencies: set[str], now: datetime, events: list[dict] | None, minutes: int) -> bool:
    if not events:
        return False
    window = timedelta(minutes=minutes)
    for event in events:
        if event["impact"] != "high":
            continue
        if event["currency"] not in currencies:
            continue
        if abs(event["time"] - now) <= window:
            return True
    return False

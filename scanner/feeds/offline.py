"""Cached hourly bars for the offline feed. No network here."""

from __future__ import annotations

import csv
import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scanner.models import Bar, SymbolMeta


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def read_bars(path: Path, drop_partial: bool = True) -> list[Bar]:
    bars: list[Bar] = []
    seen: set[datetime] = set()
    with _open_text(path) as handle:
        for row in csv.DictReader(handle):
            if not row.get("close") or row["close"] in {"", "null", "None"}:
                continue
            try:
                opened = datetime.fromisoformat(row["time"].replace("Z", "+00:00"))
                prices = [float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])]
                volume = float(row["volume"] or 0)
            except (TypeError, ValueError):
                continue
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            else:
                opened = opened.astimezone(timezone.utc)
            if any(price != price or price <= 0 for price in prices):
                continue
            if opened in seen:
                continue
            seen.add(opened)
            bars.append(Bar(opened, prices[0], prices[1], prices[2], prices[3], volume, None))
    bars.sort(key=lambda bar: bar.time)
    if drop_partial and bars:
        # The last hour from a vendor is often still forming. Drop it.
        bars.pop()
    return bars


def load_symbol(directory: Path, symbol: str) -> tuple[SymbolMeta, list[Bar]] | None:
    meta_path = directory / f"{symbol}.meta.json"
    data_path = directory / f"{symbol}.csv.gz"
    if not data_path.exists():
        plain = directory / f"{symbol}.csv"
        data_path = plain if plain.exists() else data_path
    if not meta_path.exists() or not data_path.exists():
        return None
    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    meta = SymbolMeta(
        name=raw["symbol"],
        path=raw.get("path", "offline"),
        asset_class=raw.get("asset_class", "unknown"),
        contract_size=float(raw.get("contract_size", 1)),
        volume_min=float(raw.get("volume_min", 0.01)),
        volume_step=float(raw.get("volume_step", 0.01)),
        currency_base=raw.get("base", ""),
        currency_profit=raw.get("quote", "USD"),
        trade_mode="full",
        fx_pair=bool(raw.get("fx_pair", False)),
    )
    return meta, read_bars(data_path)


def load_cache(directory: Path, max_bars: int | None = None) -> list[tuple[SymbolMeta, list[Bar]]]:
    """Load cached symbols. `max_bars` keeps only the tail, for a live-style scan on a small machine."""
    loaded = []
    if not directory.exists():
        return loaded
    for meta_path in sorted(directory.glob("*.meta.json")):
        symbol = meta_path.name[: -len(".meta.json")]
        item = load_symbol(directory, symbol)
        if item is None or not item[1]:
            continue
        meta, bars = item
        if max_bars is not None and len(bars) > max_bars:
            bars = bars[-max_bars:]
        loaded.append((meta, bars))
    return loaded


def cache_age(directory: Path) -> timedelta | None:
    files = list(directory.glob("*.meta.json"))
    if not files:
        return None
    newest = max(path.stat().st_mtime for path in files)
    return datetime.now(timezone.utc) - datetime.fromtimestamp(newest, tz=timezone.utc)

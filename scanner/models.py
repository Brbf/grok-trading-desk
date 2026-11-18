"""Shared records. All timestamps are timezone-aware UTC."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime


def iso(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    return ts.isoformat()


@dataclass(slots=True)
class Bar:
    time: datetime  # bar open, UTC
    open: float
    high: float
    low: float
    close: float
    volume: float
    spread: float | None = None


@dataclass(slots=True)
class SymbolMeta:
    name: str
    path: str = ""
    asset_class: str = "unknown"
    point: float = 0.00001
    digits: int = 5
    contract_size: float = 1.0
    volume_min: float = 0.01
    volume_step: float = 0.01
    currency_base: str = ""
    currency_profit: str = "USD"
    trade_mode: str = "full"  # full|longonly|shortonly|closeonly|disabled
    visible: bool = False
    spread_points: int = 0
    session_deals: int = 0
    session_volume: float = 0.0
    last_quote_time: datetime | None = None
    bid: float = 0.0
    ask: float = 0.0
    fx_pair: bool = False


@dataclass(slots=True)
class QuoteSnapshot:
    symbol: str
    time: datetime | None
    bid: float
    ask: float
    spread: float
    session_deals: int
    session_volume: float
    last: float


@dataclass(slots=True)
class Candidate:
    symbol: str
    time: datetime
    direction: int  # +1 long, -1 short
    origin: str
    price_confirmed: bool
    entry_ref: float
    stop_distance: float
    atr: float
    atr_ratio: float
    volume_ratio: float
    range_atr: float
    spread: float
    spread_atr: float
    htf_agree: bool
    asset_class: str
    quote_currency: str
    contract_size: float
    volume_min: float
    volume_step: float
    news_blackout: bool = False
    bar_index: int = 0

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "time": iso(self.time),
            "direction": self.direction,
            "origin": self.origin,
            "price_confirmed": self.price_confirmed,
            "entry_ref": self.entry_ref,
            "stop_distance": self.stop_distance,
            "atr": self.atr,
            "atr_ratio": self.atr_ratio,
            "volume_ratio": self.volume_ratio,
            "range_atr": self.range_atr,
            "spread": self.spread,
            "spread_atr": self.spread_atr,
            "htf_agree": self.htf_agree,
            "asset_class": self.asset_class,
            "quote_currency": self.quote_currency,
            "contract_size": self.contract_size,
            "volume_min": self.volume_min,
            "volume_step": self.volume_step,
            "news_blackout": self.news_blackout,
            "bar_index": self.bar_index,
        }


@dataclass
class RejectionLog:
    """Counts every rejection and keeps a few examples. The hot path only increments."""

    example_cap: int = 6
    counts: Counter = field(default_factory=Counter)
    examples: dict[str, list[dict]] = field(default_factory=lambda: defaultdict(list))

    def add(self, stage: str, reason: str, symbol: str, time: datetime | None = None, detail: str = "") -> None:
        key = f"{stage}:{reason}"
        self.counts[key] += 1
        bucket = self.examples[key]
        if len(bucket) < self.example_cap:
            bucket.append({"symbol": symbol, "time": iso(time), "detail": detail})

    def as_dict(self) -> dict:
        return {
            "counts": dict(self.counts),
            "examples": {k: list(v) for k, v in self.examples.items()},
        }

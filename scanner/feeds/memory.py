"""In-memory feed used by tests and by the offline scanner."""

from __future__ import annotations

from datetime import datetime, timedelta

from scanner.models import Bar, QuoteSnapshot, SymbolMeta


class MemoryFeed:
    def __init__(self, symbols: list[SymbolMeta], bars: dict[str, list[Bar]] | None = None):
        self.symbols = list(symbols)
        self.bars = bars or {}
        self.cursor = 0
        self.quote_batches: list[list[str]] = []
        self.rate_calls: list[str] = []
        self.released: list[str] = []

    def discover(self) -> list[SymbolMeta]:
        return list(self.symbols)

    def quote_batch(self, symbols: list[SymbolMeta], now: datetime) -> list[QuoteSnapshot]:
        self.quote_batches.append([symbol.name for symbol in symbols])
        snapshots = []
        for symbol in symbols:
            closed = _closed(self.bars.get(symbol.name, []), now)
            if not closed:
                snapshots.append(QuoteSnapshot(symbol.name, None, 0.0, 0.0, 0.0, 0, 0.0, 0.0))
                continue
            bar = closed[-1]
            spread = bar.spread if bar.spread and bar.spread > 0 else max(bar.close * 1e-4, 1e-8)
            snapshots.append(
                QuoteSnapshot(
                    symbol=symbol.name,
                    time=bar.time + timedelta(hours=1),
                    bid=bar.close - spread / 2.0,
                    ask=bar.close + spread / 2.0,
                    spread=spread,
                    session_deals=1 if bar.volume and bar.volume > 0 else 0,
                    session_volume=bar.volume or 0.0,
                    last=bar.close,
                )
            )
        return snapshots

    def rates(self, symbol: str, count: int, now: datetime) -> list[Bar]:
        self.rate_calls.append(symbol)
        closed = _closed(self.bars.get(symbol, []), now)
        return closed[-count:]

    def release(self, names: list[str]) -> None:
        self.released.extend(names)


def _closed(bars: list[Bar], now: datetime, bar_seconds: int = 3600) -> list[Bar]:
    limit = timedelta(seconds=bar_seconds)
    return [bar for bar in bars if bar.time + limit <= now]

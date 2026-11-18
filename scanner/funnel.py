"""Cheap multi-stage funnel over the whole discovered universe.

Stage 1 uses the cached symbol list and the session clock only.
Stage 2 asks for quotes, in rotating batches, and drops wide or dead markets.
Stage 3 pulls history only for the names that passed, and only while the
per-cycle request budget lasts. Nothing here caps how many symbols are discovered.
"""

from __future__ import annotations

from datetime import datetime

from scanner.classify import classify
from scanner.indicators import wilder_atr
from scanner.models import Bar, QuoteSnapshot, RejectionLog, SymbolMeta
from scanner.quality import _median, bar_problems
from scanner.sessions import resolve_schedule, session_state


def take_batch(symbols: list[SymbolMeta], cursor: int, limit: int) -> tuple[list[SymbolMeta], int]:
    if not symbols or limit <= 0:
        return [], cursor
    count = min(limit, len(symbols))
    start = cursor % len(symbols)
    batch = [symbols[(start + offset) % len(symbols)] for offset in range(count)]
    return batch, (start + count) % len(symbols)


def stage1(symbols: list[SymbolMeta], now: datetime, cfg: dict, log: RejectionLog) -> list[SymbolMeta]:
    kept: list[SymbolMeta] = []
    for symbol in symbols:
        if symbol.trade_mode not in ("full", "longonly", "shortonly"):
            log.add("funnel", "not_tradable", symbol.name, now, symbol.trade_mode)
            continue
        asset = symbol.asset_class if symbol.asset_class != "unknown" else classify(symbol.name, symbol.path)
        asset, schedule = resolve_schedule(symbol.name, asset, cfg)
        symbol.asset_class = asset
        state = session_state(now, asset, schedule)
        if not state.open:
            log.add("funnel", state.reason, symbol.name, now)
            continue
        kept.append(symbol)
    return kept


def stage2(
    symbols: list[SymbolMeta],
    quotes: list[QuoteSnapshot],
    now: datetime,
    cfg: dict,
    log: RejectionLog,
) -> list[tuple[SymbolMeta, QuoteSnapshot]]:
    funnel = cfg["funnel"]
    by_class: dict[str, list[float]] = {}
    for symbol, quote in zip(symbols, quotes):
        if quote.spread > 0:
            by_class.setdefault(symbol.asset_class, []).append(quote.spread)
    medians = {key: _median(values) for key, values in by_class.items()}
    kept = []
    stale_after = float(funnel["stale_seconds"])
    multiple = float(funnel["spread_to_class_median_max"])
    min_deals = int(funnel["min_session_deals"])
    for symbol, quote in zip(symbols, quotes):
        if quote.time is None or (now - quote.time).total_seconds() > stale_after:
            log.add("funnel", "stale_quote", symbol.name, now)
            continue
        if quote.spread <= 0:
            log.add("funnel", "abnormal_spread", symbol.name, now, "non_positive")
            continue
        median = medians.get(symbol.asset_class, quote.spread)
        if median > 0 and quote.spread > median * multiple:
            log.add("funnel", "abnormal_spread", symbol.name, now, f"{quote.spread:.6g}>{multiple}x{median:.6g}")
            continue
        if quote.session_deals < min_deals and quote.session_volume <= 0:
            log.add("funnel", "illiquid", symbol.name, now)
            continue
        kept.append((symbol, quote))
    return kept


def _recent_volume_ratio(bars: list[Bar], lookback: int = 20) -> float | None:
    if len(bars) < lookback + 3:
        return None
    history = [bar.volume for bar in bars[-(lookback + 3):-3]]
    if not history or _median(history) <= 0:
        return None
    recent = sum(bar.volume for bar in bars[-3:]) / 3.0
    return recent / _median(history)


def stage3_activity(bars: list[Bar], cfg: dict) -> tuple[bool, str, float, float]:
    """Return aligned, reason, atr_ratio, volume_ratio. Uses only the closed bars given."""
    strategy = cfg["strategy"]
    funnel = cfg["funnel"]
    period = int(strategy["atr_period"])
    lookback = int(strategy["atr_median_lookback"])
    if len(bars) < period + lookback:
        return False, "insufficient_history", 0.0, 0.0
    atr = wilder_atr(bars, period)
    defined = [value for value in atr[:-1] if value]
    if len(defined) < lookback or not atr[-1]:
        return False, "insufficient_history", 0.0, 0.0
    basis = _median(defined[-lookback:])
    if basis <= 0:
        return False, "insufficient_history", 0.0, 0.0
    atr_ratio = atr[-1] / basis
    if not float(funnel["activity_atr_ratio_min"]) <= atr_ratio <= float(funnel["activity_atr_ratio_max"]):
        return False, "volatility_not_aligned", atr_ratio, 0.0
    volume_ratio = _recent_volume_ratio(bars, int(strategy["volume_lookback"]))
    if volume_ratio is None:
        return False, "volume_missing", atr_ratio, 0.0
    if not float(funnel["activity_volume_ratio_min"]) <= volume_ratio <= float(funnel["activity_volume_ratio_max"]):
        return False, "volume_not_aligned", atr_ratio, volume_ratio
    return True, "ok", atr_ratio, volume_ratio


def apply_quote_spread(bars: list[Bar], spread: float) -> list[Bar]:
    if not bars:
        return bars
    last = bars[-1]
    bars[-1] = Bar(last.time, last.open, last.high, last.low, last.close, last.volume, spread)
    return bars


def last_bar_quality(symbol: SymbolMeta, bars: list[Bar], now: datetime, cfg: dict) -> list[str]:
    if len(bars) < 3:
        return ["insufficient_history"]
    index = len(bars) - 1
    atr = wilder_atr(bars, int(cfg["strategy"]["atr_period"]))
    previous = atr[index - 1] if index else None

    def session_open_at(ts: datetime) -> bool:
        asset, schedule = resolve_schedule(symbol.name, symbol.asset_class, cfg)
        return session_state(ts, asset, schedule).open

    return bar_problems(
        bars,
        index,
        now=now,
        bar_seconds=3600,
        atr_prev=previous,
        outlier_multiple=float(cfg["strategy"]["outlier_range_atr"]),
        session_open_at=session_open_at,
    )

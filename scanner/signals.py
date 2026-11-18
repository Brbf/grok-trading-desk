"""Higher-timeframe trend plus a closed-bar breakout. No lookahead."""

from __future__ import annotations

from dataclasses import dataclass

from .indicators import ema, prior_max, prior_median, prior_min, wilder_atr
from .models import Bar, Candidate, SymbolMeta


@dataclass(slots=True)
class Prepared:
    bars: list[Bar]
    atr: list[float | None]
    atr_basis: list[float | None]
    prior_high: list[float | None]
    prior_low: list[float | None]
    prior_volume: list[float | None]
    htf_fast: list[float | None]
    htf_slow: list[float | None]
    htf_close: list[float | None]


def _htf_closes(bars: list[Bar], width: int, gap_seconds: int) -> list[tuple[int, float]]:
    blocks: list[tuple[int, float]] = []
    bucket: list[int] = []
    previous = None
    for index, bar in enumerate(bars):
        if previous is not None and bucket:
            if (bar.time - previous).total_seconds() > gap_seconds:
                bucket = []
        bucket.append(index)
        previous = bar.time
        if len(bucket) == width:
            end = bucket[-1]
            blocks.append((end, bars[end].close))
            bucket = []
    return blocks


def prepare(bars: list[Bar], strategy: dict) -> Prepared:
    atr = wilder_atr(bars, int(strategy["atr_period"]))
    basis = _median_of_defined(atr, int(strategy["atr_median_lookback"]))
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    volumes = [bar.volume for bar in bars]
    blocks = _htf_closes(bars, int(strategy["htf_bars"]), int(strategy["htf_gap_seconds"]))
    closes = [close for _, close in blocks]
    fast = ema(closes, int(strategy["ema_fast"]))
    slow = ema(closes, int(strategy["ema_slow"]))
    htf_fast: list[float | None] = [None] * len(bars)
    htf_slow: list[float | None] = [None] * len(bars)
    htf_close: list[float | None] = [None] * len(bars)
    cursor = 0
    current = (None, None, None)
    for index in range(len(bars)):
        while cursor < len(blocks) and blocks[cursor][0] <= index:
            current = (fast[cursor], slow[cursor], closes[cursor])
            cursor += 1
        htf_fast[index], htf_slow[index], htf_close[index] = current
    return Prepared(
        bars=bars,
        atr=atr,
        atr_basis=basis,
        prior_high=prior_max(highs, int(strategy["donchian"])),
        prior_low=prior_min(lows, int(strategy["donchian"])),
        prior_volume=prior_median(volumes, int(strategy["volume_lookback"])),
        htf_fast=htf_fast,
        htf_slow=htf_slow,
        htf_close=htf_close,
    )


def _median_of_defined(values: list[float | None], lookback: int) -> list[float | None]:
    """Median of the previous `lookback` defined values. Skips Nones instead of treating them as 0."""
    out: list[float | None] = [None] * len(values)
    window: list[float] = []
    for index, value in enumerate(values):
        if len(window) >= lookback:
            sample = sorted(window[-lookback:])
            mid = lookback // 2
            if lookback % 2:
                out[index] = sample[mid]
            else:
                out[index] = 0.5 * (sample[mid - 1] + sample[mid])
        if value is not None and value > 0:
            window.append(value)
            if len(window) > lookback:
                window.pop(0)
    return out


def signal_at(prep: Prepared, index: int, meta: SymbolMeta, strategy: dict) -> tuple[Candidate | None, str]:
    """Setup at the close of `index`. Uses no bar after `index`."""
    bar = prep.bars[index]
    atr = prep.atr[index]
    basis = prep.atr_basis[index]
    fast = prep.htf_fast[index]
    slow = prep.htf_slow[index]
    htf_close = prep.htf_close[index]
    if atr is None or basis is None or basis <= 0 or fast is None or slow is None or htf_close is None:
        return None, "warmup"
    if prep.prior_high[index] is None or prep.prior_low[index] is None or prep.prior_volume[index] is None:
        return None, "warmup"
    atr_ratio = atr / basis
    lo = float(strategy["atr_ratio_min"])
    hi = float(strategy["atr_ratio_max"])
    if not lo <= atr_ratio <= hi:
        return None, "volatility_not_aligned"
    prior_volume = prep.prior_volume[index]
    if prior_volume is None or prior_volume <= 0:
        return None, "volume_missing"
    volume_ratio = bar.volume / prior_volume
    range_atr = (bar.high - bar.low) / atr if atr else 0.0
    long_trend = fast > slow and htf_close > fast
    short_trend = fast < slow and htf_close < fast
    long_break = bar.close > prep.prior_high[index]
    short_break = bar.close < prep.prior_low[index]
    direction = 0
    if long_trend and long_break and not short_break:
        direction = 1
    elif short_trend and short_break and not long_break:
        direction = -1
    else:
        return None, "no_setup"
    stop = float(strategy["stop_atr"]) * atr
    if stop <= 0:
        return None, "bad_levels"
    return Candidate(
        symbol=meta.name,
        time=bar.time,
        direction=direction,
        origin="price",
        price_confirmed=True,
        entry_ref=bar.close,
        stop_distance=stop,
        atr=atr,
        atr_ratio=atr_ratio,
        volume_ratio=volume_ratio,
        range_atr=range_atr,
        spread=bar.spread or 0.0,
        spread_atr=(bar.spread or 0.0) / atr,
        htf_agree=True,
        asset_class=meta.asset_class,
        quote_currency=meta.currency_profit,
        contract_size=meta.contract_size,
        volume_min=meta.volume_min,
        volume_step=meta.volume_step,
        bar_index=index,
    ), "setup"

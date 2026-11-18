"""Causal indicators. Value at index i uses only bars[0..i]."""

from __future__ import annotations

from collections import deque

from .models import Bar


def true_ranges(bars: list[Bar]) -> list[float]:
    ranges: list[float] = []
    previous_close = None
    for bar in bars:
        if previous_close is None:
            tr = bar.high - bar.low
        else:
            tr = max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close))
        ranges.append(tr)
        previous_close = bar.close
    return ranges


def wilder_atr(bars: list[Bar], period: int) -> list[float | None]:
    trs = true_ranges(bars)
    atr: list[float | None] = [None] * len(bars)
    if period <= 0 or len(bars) < period:
        return atr
    acc = sum(trs[:period]) / period
    atr[period - 1] = acc
    for i in range(period, len(bars)):
        acc = (acc * (period - 1) + trs[i]) / period
        atr[i] = acc
    return atr


def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    acc = sum(values[:period]) / period
    out[period - 1] = acc
    k = 2.0 / (period + 1)
    for i in range(period, len(values)):
        acc = values[i] * k + acc * (1.0 - k)
        out[i] = acc
    return out


def rolling_median(values: list[float | None], lookback: int) -> list[float | None]:
    """Median of the previous `lookback` values, excluding the current index."""
    out: list[float | None] = [None] * len(values)
    window: deque[float] = deque()
    for i, value in enumerate(values):
        if len(window) >= lookback:
            sample = sorted(window)
            mid = len(sample) // 2
            if len(sample) % 2:
                out[i] = sample[mid]
            else:
                out[i] = 0.5 * (sample[mid - 1] + sample[mid])
        if value is not None:
            window.append(value)
        if len(window) > lookback:
            window.popleft()
    return out


def prior_max(values: list[float], lookback: int) -> list[float | None]:
    """Max of values[i-lookback:i], excluding i."""
    out: list[float | None] = [None] * len(values)
    window: deque[tuple[int, float]] = deque()
    for i, value in enumerate(values):
        while window and window[0][0] < i - lookback:
            window.popleft()
        if i >= lookback and window:
            out[i] = window[0][1]
        while window and window[-1][1] <= value:
            window.pop()
        window.append((i, value))
    return out


def prior_min(values: list[float], lookback: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    window: deque[tuple[int, float]] = deque()
    for i, value in enumerate(values):
        while window and window[0][0] < i - lookback:
            window.popleft()
        if i >= lookback and window:
            out[i] = window[0][1]
        while window and window[-1][1] >= value:
            window.pop()
        window.append((i, value))
    return out


def prior_median(values: list[float], lookback: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    window: deque[float] = deque()
    for i, value in enumerate(values):
        if len(window) >= lookback:
            sample = sorted(window)
            mid = len(sample) // 2
            if len(sample) % 2:
                out[i] = sample[mid]
            else:
                out[i] = 0.5 * (sample[mid - 1] + sample[mid])
        window.append(value)
        if len(window) > lookback:
            window.popleft()
    return out

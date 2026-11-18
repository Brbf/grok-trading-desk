"""Data and signal quality gate.

A candidate is dropped, with a logged reason, when the prices are stale, gapped,
duplicated, economically absurd, or when the signal did not come from price.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .models import Bar, Candidate, RejectionLog


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def series_problems(bars: list[Bar]) -> list[str]:
    """Structural problems that reject a whole series. Does not look ahead."""
    reasons: list[str] = []
    if len(bars) < 3:
        return ["insufficient_history"]
    previous = None
    seen: set[datetime] = set()
    positive_volume = 0
    for bar in bars:
        if bar.time in seen:
            reasons.append("duplicate_timestamp")
            break
        seen.add(bar.time)
        if previous is not None and bar.time <= previous:
            reasons.append("non_monotonic_time")
            break
        previous = bar.time
        for price in (bar.open, bar.high, bar.low, bar.close):
            if price != price or price in (float("inf"), float("-inf")):  # NaN / inf
                reasons.append("nonfinite_price")
                return reasons
            if price <= 0:
                reasons.append("nonpositive_price")
                return reasons
        if bar.high < bar.low or bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
            reasons.append("inconsistent_ohlc")
            return reasons
        if bar.volume and bar.volume > 0:
            positive_volume += 1
    if volume_is_missing(bars, positive_volume):
        # Zero volume cannot confirm a volume anomaly. Do not invent volume.
        reasons.append("volume_missing")
    return reasons


def volume_is_missing(bars: list[Bar], positive_volume: int | None = None) -> bool:
    """True when there is not enough real volume to confirm an anomaly.

    Yahoo spot FX is the usual case: every bar has volume 0. A series passes when
    at least 20% of bars (and at least 100 bars) have positive volume.
    """
    if not bars:
        return True
    if positive_volume is None:
        positive_volume = sum(1 for bar in bars if bar.volume and bar.volume > 0)
    needed = max(100, int(0.20 * len(bars)))
    return positive_volume < needed


def _bridge_is_session(start: datetime, end: datetime, session_open_at) -> bool:
    """True when a missing stretch still contains timestamps that should have been open."""
    cursor = start + timedelta(minutes=30)
    while cursor < end:
        if session_open_at(cursor):
            return True
        cursor += timedelta(minutes=30)
    return False


def bar_problems(
    bars: list[Bar],
    index: int,
    *,
    now: datetime,
    bar_seconds: int,
    atr_prev: float | None,
    outlier_multiple: float,
    session_open_at,
) -> list[str]:
    """Problems visible at `index` using only bars up to that index."""
    reasons: list[str] = []
    bar = bars[index]
    close_time = bar.time + timedelta(seconds=bar_seconds)
    if now.tzinfo is None or bar.time.tzinfo is None:
        reasons.append("naive_timestamp")
        return reasons
    if now - close_time > timedelta(seconds=bar_seconds * 2):
        reasons.append("stale_data")
    if index > 0:
        gap = (bar.time - bars[index - 1].time).total_seconds()
        if gap > bar_seconds * 3 and _bridge_is_session(bars[index - 1].time, bar.time, session_open_at):
            reasons.append("gap")
    if atr_prev and atr_prev > 0 and (bar.high - bar.low) > outlier_multiple * atr_prev:
        reasons.append("outlier_bar")
    if bar.spread is not None:
        if bar.spread <= 0:
            reasons.append("abnormal_spread")
        elif atr_prev and atr_prev > 0 and bar.spread > 0.35 * atr_prev:
            reasons.append("abnormal_spread")
    return reasons


def gate_candidate(candidate: Candidate, log: RejectionLog | None = None) -> list[str]:
    reasons: list[str] = []
    if candidate.origin != "price" or not candidate.price_confirmed:
        reasons.append("external_unconfirmed")
    if candidate.direction not in (1, -1):
        reasons.append("bad_direction")
    if candidate.stop_distance <= 0 or candidate.atr <= 0 or candidate.entry_ref <= 0:
        reasons.append("bad_levels")
    if log is not None:
        for reason in reasons:
            log.add("quality", reason, candidate.symbol, candidate.time)
    return reasons


def resolve_conflicts(candidates: list[Candidate], log: RejectionLog) -> list[Candidate]:
    """Drop duplicates and both sides when the same symbol disagrees on one bar."""
    groups: dict[tuple[str, datetime], list[Candidate]] = {}
    for candidate in candidates:
        groups.setdefault((candidate.symbol, candidate.time), []).append(candidate)
    kept: list[Candidate] = []
    for (symbol, when), group in groups.items():
        directions = {item.direction for item in group}
        if len(group) > 1 and len(directions) > 1:
            log.add("quality", "conflicting_signal", symbol, when, detail=str(sorted(directions)))
            continue
        if len(group) > 1:
            log.add("quality", "duplicate_signal", symbol, when)
            continue
        kept.append(group[0])
    return kept


def class_spread_median(spreads: list[float]) -> float:
    positive = [value for value in spreads if value > 0]
    if not positive:
        return 0.0
    return _median(positive)

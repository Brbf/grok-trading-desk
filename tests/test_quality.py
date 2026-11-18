from datetime import datetime, timedelta, timezone

from scanner.models import Bar, Candidate, RejectionLog
from scanner.quality import (
    bar_problems,
    gate_candidate,
    resolve_conflicts,
    series_problems,
    volume_is_missing,
)


def _bar(index: int, price: float = 100.0, volume: float = 1000.0, spread=None) -> Bar:
    start = datetime(2026, 1, 14, 15, tzinfo=timezone.utc)
    return Bar(
        time=start + timedelta(hours=index),
        open=price,
        high=price + 0.4,
        low=price - 0.4,
        close=price + 0.1,
        volume=volume,
        spread=spread,
    )


def test_series_rejects_duplicates_gaps_and_bad_prices():
    bars = [_bar(0), _bar(1), _bar(2)]
    bars.append(bars[-1])
    assert "duplicate_timestamp" in series_problems(bars)

    backwards = [_bar(2), _bar(1), _bar(0)]
    # same timestamps are unique here but out of order
    assert "non_monotonic_time" in series_problems(backwards)

    broken = [_bar(0), _bar(1), _bar(2)]
    broken[1] = Bar(broken[1].time, 0.0, 1.0, 0.5, 0.8, 10, None)
    assert "nonpositive_price" in series_problems(broken)


def test_volume_missing_does_not_invent_volume():
    quiet = [_bar(i, volume=0) for i in range(120)]
    assert volume_is_missing(quiet)
    assert "volume_missing" in series_problems(quiet)
    loud = [_bar(i, volume=50) for i in range(120)]
    assert not volume_is_missing(loud)


def test_bar_problems_stale_outlier_spread_and_gap():
    bars = [_bar(i) for i in range(30)]
    now = bars[-1].time + timedelta(hours=1)
    assert bar_problems(
        bars, len(bars) - 1, now=now, bar_seconds=3600, atr_prev=1.0,
        outlier_multiple=10, session_open_at=lambda _ts: True,
    ) == []

    stale_now = now + timedelta(hours=5)
    assert "stale_data" in bar_problems(
        bars, len(bars) - 1, now=stale_now, bar_seconds=3600, atr_prev=1.0,
        outlier_multiple=10, session_open_at=lambda _ts: True,
    )

    wild = list(bars)
    wild[-1] = Bar(wild[-1].time, 100, 130, 90, 120, 1000, None)
    assert "outlier_bar" in bar_problems(
        wild, len(wild) - 1, now=now, bar_seconds=3600, atr_prev=1.0,
        outlier_multiple=10, session_open_at=lambda _ts: True,
    )

    wide = list(bars)
    wide[-1] = Bar(wide[-1].time, 100, 100.4, 99.6, 100.1, 1000, spread=5)
    assert "abnormal_spread" in bar_problems(
        wide, len(wide) - 1, now=now, bar_seconds=3600, atr_prev=1.0,
        outlier_multiple=10, session_open_at=lambda _ts: True,
    )

    gapped = [_bar(0), _bar(1)]
    gapped[1] = Bar(gapped[0].time + timedelta(hours=6), 100, 100.4, 99.6, 100.1, 1000, None)
    assert "gap" in bar_problems(
        gapped, 1, now=gapped[1].time + timedelta(hours=1), bar_seconds=3600, atr_prev=1.0,
        outlier_multiple=10, session_open_at=lambda _ts: True,
    )
    # A hole that falls outside the session (the bridge is closed) is not a data gap.
    assert "gap" not in bar_problems(
        gapped, 1, now=gapped[1].time + timedelta(hours=1), bar_seconds=3600, atr_prev=1.0,
        outlier_multiple=10, session_open_at=lambda _ts: False,
    )


def test_external_and_conflicting_signals_are_logged():
    log = RejectionLog()
    external = Candidate(
        symbol="EURUSD", time=datetime(2026, 1, 14, tzinfo=timezone.utc), direction=1,
        origin="twitter", price_confirmed=False, entry_ref=1.1, stop_distance=0.01,
        atr=0.002, atr_ratio=1, volume_ratio=2, range_atr=1, spread=0.0001, spread_atr=0.05,
        htf_agree=True, asset_class="fx_major", quote_currency="USD",
        contract_size=1, volume_min=1000, volume_step=1000,
    )
    assert "external_unconfirmed" in gate_candidate(external, log)
    assert log.counts["quality:external_unconfirmed"] == 1

    left = Candidate(
        symbol="AAPL", time=external.time, direction=1, origin="price", price_confirmed=True,
        entry_ref=100, stop_distance=1, atr=1, atr_ratio=1, volume_ratio=2, range_atr=1,
        spread=0.05, spread_atr=0.05, htf_agree=True, asset_class="stock_us",
        quote_currency="USD", contract_size=1, volume_min=0.01, volume_step=0.01,
    )
    right = Candidate(
        symbol="AAPL", time=external.time, direction=-1, origin="price", price_confirmed=True,
        entry_ref=100, stop_distance=1, atr=1, atr_ratio=1, volume_ratio=2, range_atr=1,
        spread=0.05, spread_atr=0.05, htf_agree=True, asset_class="stock_us",
        quote_currency="USD", contract_size=1, volume_min=0.01, volume_step=0.01,
    )
    assert resolve_conflicts([left, right], log) == []
    assert log.counts["quality:conflicting_signal"] == 1

    dup_log = RejectionLog()
    assert resolve_conflicts([left, left], dup_log) == []
    assert dup_log.counts["quality:duplicate_signal"] == 1

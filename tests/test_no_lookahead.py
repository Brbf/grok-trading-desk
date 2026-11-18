from datetime import datetime, timedelta, timezone

from scanner.config import load_config
from scanner.models import Bar, SymbolMeta
from scanner.signals import prepare, signal_at

CFG = load_config()


def _series(n: int = 420):
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)
    bars = []
    price = 100.0
    for index in range(n):
        price += 0.08
        bars.append(Bar(
            time=start + timedelta(hours=index),
            open=price - 0.05,
            high=price + 0.02,
            low=price - 0.12,
            close=price,
            volume=1000,
            spread=None,
        ))
    last = bars[-1]
    bars[-1] = Bar(last.time, last.open, last.high, last.low, last.close, 5000, None)
    return bars


def test_signal_ignores_future_bars():
    bars = _series()
    meta = SymbolMeta(name="TEST", asset_class="stock_us", currency_profit="EUR", contract_size=1, volume_min=0.01, volume_step=0.01)
    prep = prepare(bars, CFG["strategy"])
    index = len(bars) - 1
    candidate, reason = signal_at(prep, index, meta, CFG["strategy"])
    assert reason == "setup"
    assert candidate is not None and candidate.direction == 1

    mutated = list(bars)
    future = mutated[index]  # replaced below; the bar AFTER the signal does not exist, so edit a copy of history past index by extending
    # Changing a bar after `index` is impossible at the tail. Insert the check on an earlier signal.
    earlier = index - 5
    before, before_reason = signal_at(prep, earlier, meta, CFG["strategy"])
    mutated[earlier + 2] = Bar(
        mutated[earlier + 2].time, 1, 500, 0.5, 400, 1, None,
    )
    # The mutated bar is internally inconsistent for a real feed, but it must not leak backwards.
    prep_after = prepare(mutated, CFG["strategy"])
    after, after_reason = signal_at(prep_after, earlier, meta, CFG["strategy"])
    assert before_reason == after_reason
    assert (before.direction if before else None) == (after.direction if after else None)
    assert prep.atr[earlier] == prep_after.atr[earlier]
    assert prep.prior_high[earlier] == prep_after.prior_high[earlier]
    assert prep.htf_fast[earlier] == prep_after.htf_fast[earlier]
    assert future.close != mutated[earlier + 2].close


def test_same_bar_close_is_not_the_fill_price():
    """The candidate records the signal close. The broker fills the next open, tested in the paper tests."""
    bars = _series()
    meta = SymbolMeta(name="TEST", asset_class="stock_us", currency_profit="EUR")
    prep = prepare(bars, CFG["strategy"])
    candidate, _reason = signal_at(prep, len(bars) - 1, meta, CFG["strategy"])
    assert candidate.entry_ref == bars[-1].close
    assert candidate.bar_index == len(bars) - 1

from datetime import datetime, timedelta, timezone

from scanner.config import load_config
from scanner.models import Bar, RejectionLog, SymbolMeta
from scanner.simulate import build_series, run_walk


def _bars(start: datetime, n: int, price: float, step: float) -> list[Bar]:
    bars = []
    for index in range(n):
        price += step
        bars.append(Bar(
            time=start + timedelta(hours=index),
            open=price - step,
            high=price + abs(step),
            low=price - abs(step) * 1.2,
            close=price,
            volume=1000 + (5000 if index % 17 == 0 else 0),
            spread=None,
        ))
    return bars


def test_walk_stays_finite_and_flat_at_the_end():
    cfg = load_config()
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)
    eurusd = SymbolMeta(
        name="EURUSD", asset_class="fx_major", currency_base="EUR", currency_profit="USD",
        fx_pair=True, contract_size=1, volume_min=1000, volume_step=1000, trade_mode="full",
    )
    stock = SymbolMeta(
        name="AAA", path=r"Stocks\US", asset_class="stock_us", currency_base="AAA",
        currency_profit="USD", contract_size=1, volume_min=0.01, volume_step=0.01, trade_mode="full",
    )
    loaded = [
        (eurusd, _bars(start, 240, 1.08, 0.0001)),
        (stock, _bars(start, 240, 100, 0.05)),
    ]
    # EURUSD volume is real in this fixture, so the gate may allow it. That is fine.
    series = build_series(loaded, cfg, RejectionLog())
    result = run_walk(series, cfg, label="smoke")
    assert result.final_equity == result.final_equity  # not NaN
    assert result.final_equity > 0
    assert result.broker.positions == {}
    assert result.broker.pending == {}
    if result.broker.trades:
        booked = sum(trade.pnl_eur for trade in result.broker.trades)
        assert abs((result.broker.balance - 500) - booked) < 1e-4

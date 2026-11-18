from datetime import datetime, timedelta, timezone

from scanner.config import load_config
from scanner.feeds.memory import MemoryFeed
from scanner.funnel import take_batch
from scanner.models import Bar, SymbolMeta
from scanner.offline_universe import offline_instruments
from scanner.pipeline import scan_once


def _symbol(index: int) -> SymbolMeta:
    return SymbolMeta(
        name=f"S{index:04d}",
        path=r"Stocks\US",
        asset_class="stock_us",
        trade_mode="full",
        currency_profit="EUR",
        contract_size=1,
        volume_min=0.01,
        volume_step=0.01,
    )


def _bar(now: datetime) -> Bar:
    return Bar(
        time=now - timedelta(hours=1),
        open=100,
        high=101,
        low=99,
        close=100.5,
        volume=1000,
        spread=0.05,
    )


def test_rotation_covers_the_whole_list_without_a_thirty_name_cap():
    cfg = load_config()
    cfg["funnel"]["pause_ms"] = 0
    cfg["funnel"]["max_history_requests_per_cycle"] = 400
    cfg["funnel"]["batch_size"] = 50
    now = datetime(2026, 1, 14, 15, tzinfo=timezone.utc)
    symbols = [_symbol(i) for i in range(3000)]
    bars = {symbol.name: [_bar(now)] for symbol in symbols}
    feed = MemoryFeed(symbols, bars)

    first = scan_once(feed, cfg, now)
    assert first["discovered"] == 3000
    assert first["stage1_open"] == 3000
    assert first["quoted"] == 400
    assert first["stage1_deferred"] == 2600
    assert len(feed.rate_calls) == 400
    assert feed.quote_batches[0][0] == "S0000"

    second = scan_once(feed, cfg, now)
    assert second["quoted"] == 400
    assert feed.quote_batches[len(feed.quote_batches) // 2][0] == "S0400" or feed.rate_calls[400] == "S0400"
    assert len(set(feed.rate_calls)) == 800


def test_weekend_scan_is_idle_and_does_not_fetch():
    cfg = load_config()
    cfg["funnel"]["pause_ms"] = 0
    now = datetime(2026, 1, 17, 15, tzinfo=timezone.utc)  # Saturday
    symbols = [_symbol(i) for i in range(25)]
    feed = MemoryFeed(symbols, {symbol.name: [_bar(now)] for symbol in symbols})
    result = scan_once(feed, cfg, now)
    assert result["idle"] is True
    assert result["stage1_open"] == 0
    assert feed.quote_batches == []
    assert feed.rate_calls == []
    assert result["paper_orders"] == 0


def test_take_batch_wraps_and_the_offline_list_is_broad():
    symbols = [_symbol(i) for i in range(10)]
    batch, cursor = take_batch(symbols, 8, 4)
    assert [item.name for item in batch] == ["S0008", "S0009", "S0000", "S0001"]
    assert cursor == 2
    assert len(offline_instruments()) > 100


def test_disabled_symbols_never_enter_the_session_stage():
    cfg = load_config()
    cfg["funnel"]["pause_ms"] = 0
    now = datetime(2026, 1, 14, 15, tzinfo=timezone.utc)
    dead = _symbol(1)
    dead.trade_mode = "disabled"
    feed = MemoryFeed([dead], {dead.name: [_bar(now)]})
    result = scan_once(feed, cfg, now)
    assert result["stage1_open"] == 0
    assert result["rejections"]["counts"].get("funnel:not_tradable") == 1

import json
from datetime import datetime, timedelta, timezone

import agents.base as base
from agents.orchestrator import run_trading_desk
from scanner.config import load_config
from scanner.feeds.memory import MemoryFeed
from scanner.models import Bar, SymbolMeta


def _symbol() -> SymbolMeta:
    return SymbolMeta(
        name="AAA",
        path=r"Stocks\US\AAA",
        asset_class="stock_us",
        trade_mode="full",
        currency_profit="EUR",
        currency_base="AAA",
        contract_size=1,
        volume_min=0.01,
        volume_step=0.01,
    )


def _feed(now: datetime) -> MemoryFeed:
    start = now - timedelta(hours=80)
    bars = []
    price = 100.0
    for index in range(60):
        price += 0.05
        bars.append(Bar(
            time=start + timedelta(hours=index),
            open=price - 0.04,
            high=price + 0.08,
            low=price - 0.08,
            close=price,
            volume=1000,
            spread=0.02,
        ))
    symbol = _symbol()
    return MemoryFeed([symbol], {symbol.name: bars})


def test_model_comes_from_the_environment(monkeypatch):
    monkeypatch.delenv("XAI_MODEL", raising=False)
    assert base.model_name() == "grok-4"
    assert "grok-beta" not in base.model_name()
    monkeypatch.setenv("XAI_MODEL", "grok-4-fast")
    assert base.model_name() == "grok-4-fast"


def test_placeholder_key_is_not_a_credential(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "your_xai_api_key_here")
    assert base.llm_available() is False
    monkeypatch.setenv("XAI_API_KEY", "")
    assert base.llm_available() is False


def test_desk_uses_real_prices_and_skips_the_model(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    calls = []

    def _boom(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("language model was called")

    monkeypatch.setattr(base, "call_agent", _boom)
    monkeypatch.setattr("agents.orchestrator.call_agent", _boom)
    now = datetime(2026, 1, 14, 16, tzinfo=timezone.utc)
    feed = _feed(now)
    # The last bar opens at now-20h. Scan at its close so the quote is fresh.
    last_open = feed.bars["AAA"][-1].time
    result = run_trading_desk(feed=feed, now=last_open + timedelta(hours=1), use_llm=True)
    assert calls == []
    assert result["mode"] == "PAPER_ONLY"
    assert result["live_order"] is False
    assert result["llm"]["enabled"] is False
    assert result["llm"]["advisory"] is None
    assert result["scan"]["discovered"] == 1
    assert result["tape"]
    assert result["tape"][0]["symbol"] == "AAA"
    assert result["tape"][0]["close"] > 0
    blob = json.dumps(result)
    assert "65000" not in blob
    assert "fear greed" not in blob
    assert "Partner announcement" not in blob
    for decision in result["decisions"] or []:
        assert decision["decision"]["decision"] in {"paper_buy", "paper_sell"}
        assert decision["decision"]["live_order"] is False
        assert decision["sentiment"]["ignored"] is True
        assert decision["news"]["bullish"] is None
        assert decision["charts"]["source"] == "price"


def test_advisory_prompt_is_the_tape_not_a_mock(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-test-key")
    prompts = []

    def _record(system, user):
        prompts.append(user)
        return "advisory-only"

    monkeypatch.setattr("agents.orchestrator.call_agent", _record)
    now = datetime(2026, 1, 14, 16, tzinfo=timezone.utc)
    feed = _feed(now)
    last_open = feed.bars["AAA"][-1].time
    result = run_trading_desk(feed=feed, now=last_open + timedelta(hours=1), use_llm=True)
    assert result["llm"]["enabled"] is True
    assert result["llm"]["model"] == base.model_name()
    assert prompts, "expected an advisory call"
    assert "AAA" in prompts[0]
    assert "65000" not in prompts[0]
    assert "fear greed" not in prompts[0]
    # The model text must not become the order.
    assert result["llm"]["advisory"]["scout"] == "advisory-only"
    assert result["live_order"] is False


def test_config_still_has_no_live_switch():
    assert "live_trading" not in load_config()

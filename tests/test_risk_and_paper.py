from copy import deepcopy
from datetime import datetime, timedelta, timezone

from agents.chief import coordinate
from agents.risk import evaluate_risk, floor_step
from agents.scout import evaluate_volume_anomaly
from agents.skeptic import review_candidate
from scanner.config import load_config
from scanner.models import Bar
from scanner.paper import PaperBroker

CFG = load_config()
NOW = datetime(2026, 1, 14, 15, tzinfo=timezone.utc)


def _account(**overrides):
    state = {
        "equity": 500.0,
        "day_start_equity": 500.0,
        "open_positions": 0,
        "open_risk_eur": 0.0,
        "kill_switch": False,
        "day_halted": False,
    }
    state.update(overrides)
    return state


def _candidate(**overrides):
    payload = {
        "entry_ref": 100.0,
        "spread": 0.1,
        "stop_distance": 2.0,
        "contract_size": 1.0,
        "direction": 1,
        "volume_min": 0.01,
        "volume_step": 0.01,
        "trade_mode": "full",
        "symbol": "TEST",
        "origin": "price",
        "price_confirmed": True,
        "htf_agree": True,
        "atr_ratio": 1.0,
        "spread_atr": 0.05,
        "range_atr": 1.0,
        "volume_ratio": 2.0,
        "news_blackout": False,
    }
    payload.update(overrides)
    return payload


def test_floor_step_and_budget():
    assert floor_step(1.239, 0.01) == 1.23
    sized = evaluate_risk(_candidate(), _account(), CFG["risk"], CFG["costs"], 1.0)
    assert sized["approve"] is True
    assert sized["action"] == "paper"
    assert 0 < sized["risk_eur"] <= 500 * CFG["risk"]["risk_per_trade"] * 1.01


def test_kill_switch_daily_loss_and_min_lot():
    assert evaluate_risk(_candidate(), _account(kill_switch=True), CFG["risk"], CFG["costs"], 1.0)["reason"] == "kill_switch"
    halted = evaluate_risk(_candidate(), _account(equity=480, day_start_equity=500), CFG["risk"], CFG["costs"], 1.0)
    assert halted["reason"] == "daily_loss_halt"
    too_big = evaluate_risk(_candidate(volume_min=1000, volume_step=1000), _account(), CFG["risk"], CFG["costs"], 1.0)
    assert too_big["approve"] is False
    assert too_big["reason"] == "min_lot_exceeds_risk"
    assert evaluate_risk(_candidate(), _account(), CFG["risk"], CFG["costs"], None)["reason"] == "fx_conversion_missing"


def test_wider_spread_costs_more_on_the_same_path():
    def run(spread_bps: float) -> float:
        costs = deepcopy(CFG["costs"])
        costs["spread_bps"]["stock_us"] = spread_bps
        strategy = deepcopy(CFG["strategy"])
        strategy["max_hold_bars"] = 1
        broker = PaperBroker(CFG["risk"], costs, strategy)
        broker.queue({
            "symbol": "TEST",
            "direction": 1,
            "units": 1,
            "stop_distance": 50,
            "risk_eur": 3,
            "signal_time": NOW - timedelta(hours=1),
            "asset_class": "stock_us",
            "contract_size": 1,
            "quote_currency": "EUR",
            "explicit_spread": None,
            "signal_index": 0,
        })
        first = Bar(NOW, 100, 101, 99, 100.2, 1000, None)
        second = Bar(NOW + timedelta(hours=1), 110, 111, 109, 110.4, 1000, None)
        broker.on_bar("TEST", first, 0, 1.0)
        broker.on_bar("TEST", second, 1, 1.0)
        assert len(broker.trades) == 1
        assert broker.trades[0].reason == "time"
        return broker.trades[0].pnl_eur

    cheap = run(1.5)
    assert cheap > run(80)
    # Re-run once to confirm the closed-trade P&L is the whole change in cash.
    costs = deepcopy(CFG["costs"])
    costs["spread_bps"]["stock_us"] = 1.5
    strategy = deepcopy(CFG["strategy"])
    strategy["max_hold_bars"] = 1
    broker = PaperBroker(CFG["risk"], costs, strategy)
    broker.queue({
        "symbol": "TEST", "direction": 1, "units": 1, "stop_distance": 50, "risk_eur": 3,
        "signal_time": NOW - timedelta(hours=1), "asset_class": "stock_us", "contract_size": 1,
        "quote_currency": "EUR", "explicit_spread": None, "signal_index": 0,
    })
    broker.on_bar("TEST", Bar(NOW, 100, 101, 99, 100.2, 1000, None), 0, 1.0)
    broker.on_bar("TEST", Bar(NOW + timedelta(hours=1), 110, 111, 109, 110.4, 1000, None), 1, 1.0)
    assert abs((broker.balance - 500) - broker.trades[0].pnl_eur) < 1e-6
    assert broker.trades[0].pnl_eur == cheap


def test_gap_through_stop_fills_at_the_open():
    strategy = deepcopy(CFG["strategy"])
    strategy["max_hold_bars"] = 36
    broker = PaperBroker(CFG["risk"], CFG["costs"], strategy)
    broker.queue({
        "symbol": "TEST",
        "direction": 1,
        "units": 1,
        "stop_distance": 5,
        "risk_eur": 3,
        "signal_time": NOW - timedelta(hours=1),
        "asset_class": "stock_us",
        "contract_size": 1,
        "quote_currency": "EUR",
        "explicit_spread": None,
        "signal_index": 0,
    })
    broker.on_bar("TEST", Bar(NOW, 100, 101, 99, 100, 1000, None), 0, 1.0)
    broker.on_bar("TEST", Bar(NOW + timedelta(hours=1), 90, 91, 89, 90.5, 1000, None), 1, 1.0)
    assert broker.trades[0].reason == "stop"
    assert broker.trades[0].exit_fill < 90


def test_daily_and_account_kill_switch_flatten():
    broker = PaperBroker(CFG["risk"], CFG["costs"], CFG["strategy"])
    broker.roll_day(NOW)
    broker.last_equity = 480
    broker.enforce_limits(NOW)
    assert broker.day_halted is True
    assert any(event["kind"] == "daily_loss_halt" for event in broker.kill_events)

    busted = PaperBroker(CFG["risk"], CFG["costs"], CFG["strategy"])
    busted.balance = 400
    busted.last_equity = 400
    busted.enforce_limits(NOW)
    assert busted.permanent_halt is True


def test_agents_require_agreement_and_stay_on_paper():
    scout = evaluate_volume_anomaly("AAPL", 2.0, 1.0)
    assert scout["anomaly"] is True
    assert evaluate_volume_anomaly("AAPL", 1.0, 1.0)["anomaly"] is False
    skeptic = review_candidate(_candidate(), CFG["strategy"])
    assert skeptic["approve"] is True
    assert review_candidate(_candidate(origin="chat", price_confirmed=False), CFG["strategy"])["action"] == "skip"
    risk = evaluate_risk(_candidate(), _account(), CFG["risk"], CFG["costs"], 1.0)
    decision = coordinate(_candidate(), scout, skeptic, risk)
    assert decision["decision"] == "paper_buy"
    assert decision["live_order"] is False
    assert decision["mode"] == "PAPER_ONLY"
    veto = coordinate(_candidate(), {"anomaly": False, "reason": "volume_below_threshold"}, skeptic, risk)
    assert veto["decision"] == "hold"
    short = coordinate(_candidate(direction=-1), scout, skeptic, risk)
    assert short["decision"] == "paper_sell"

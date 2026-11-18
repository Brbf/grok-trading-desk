from datetime import datetime, timezone

from scanner.classify import classify
from scanner.config import load_config
from scanner.sessions import resolve_schedule, session_state

CFG = load_config()


def at(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def decision(symbol: str, asset: str, stamp: str) -> str:
    cls, schedule = resolve_schedule(symbol, asset, CFG)
    state = session_state(at(stamp), cls, schedule)
    return "open" if state.open else state.reason


def test_london_fx_winter_and_summer_dst():
    # Wednesday 14 Jan 2026 is winter (London = UTC). 10:00 is inside 08:00–17:00.
    assert decision("EURUSD", "fx_major", "2026-01-14T10:00:00") == "open"
    # 01:00 UTC is Tokyo morning, not London, so a major stays shut.
    assert decision("EURUSD", "fx_major", "2026-01-14T01:00:00") == "outside_session"
    # USDJPY is allowed in Tokyo cash hours.
    assert decision("USDJPY", "fx_jpy", "2026-01-14T01:00:00") == "open"
    # Wednesday 15 Jul 2026 is summer (London = UTC+1). 07:30 UTC = 08:30 London.
    assert decision("EURUSD", "fx_major", "2026-07-15T07:30:00") == "open"
    # 06:30 UTC = 07:30 London, before the 08:00 open.
    assert decision("EURUSD", "fx_major", "2026-07-15T06:30:00") == "outside_session"


def test_us_cash_session_shifts_with_dst():
    # Winter: 13:45 UTC = 08:45 New York, before 09:35.
    assert decision("US500", "index_us", "2026-01-14T13:45:00") == "outside_session"
    # Winter: 15:00 UTC = 10:00 New York.
    assert decision("US500", "index_us", "2026-01-14T15:00:00") == "open"
    # Summer: 13:45 UTC = 09:45 New York.
    assert decision("US500", "index_us", "2026-07-15T13:45:00") == "open"
    # Summer: 13:00 UTC = 09:00 New York, still before the cash window.
    assert decision("US500", "index_us", "2026-07-15T13:00:00") == "outside_session"


def test_weekend_rollover_and_crypto():
    assert decision("EURUSD", "fx_major", "2026-01-17T15:00:00") == "weekend_closed"
    assert decision("EURUSD", "fx_major", "2026-01-18T21:00:00") == "weekend_closed"
    # Sunday 23:00 UTC is 18:00 New York: the FX week is open, but London is shut.
    assert decision("EURUSD", "fx_major", "2026-01-18T23:00:00") == "outside_session"
    # Friday 22:30 UTC = 17:30 New York.
    assert decision("EURUSD", "fx_major", "2026-01-16T22:30:00") == "weekend_closed"
    # Crypto is allowed on Saturday afternoon UTC and shut in the thin UTC night.
    assert decision("BTCUSD", "crypto", "2026-01-17T15:00:00") == "open"
    assert decision("BTCUSD", "crypto", "2026-01-17T23:30:00") == "outside_session"


def test_rollover_blocks_an_otherwise_open_override(tmp_path):
    cfg = load_config()
    cfg["sessions"]["symbol_overrides"] = {
        "WIDE": {
            "asset_class": "fx_major",
            "clock": "utc",
            "weekend": "none",
            "rollover": True,
            "windows": [{"dow": [0, 1, 2, 3, 4, 5, 6], "start": "00:00", "end": "23:59"}],
        }
    }
    # 22:05 UTC on 14 Jan 2026 = 17:05 New York, inside the daily roll.
    cls, schedule = resolve_schedule("WIDE", "fx_major", cfg)
    state = session_state(at("2026-01-14T22:05:00"), cls, schedule)
    assert state.reason == "rollover"
    # 15:00 UTC is 10:00 New York, not the roll, and the override window is open.
    state = session_state(at("2026-01-14T15:00:00"), cls, schedule)
    assert state.open


def test_symbol_override_and_unknown_are_fail_closed():
    cfg = load_config()
    cfg["sessions"]["symbol_overrides"]["NARROW"] = {
        "clock": "utc",
        "weekend": "none",
        "rollover": False,
        "windows": [{"dow": [2], "start": "09:00", "end": "09:30"}],
    }
    cls, schedule = resolve_schedule("NARROW", "fx_major", cfg)
    assert session_state(at("2026-01-14T09:15:00"), cls, schedule).open
    assert session_state(at("2026-01-14T10:00:00"), cls, schedule).reason == "outside_session"
    assert decision("NOTASYMBOL", "unknown", "2026-01-14T15:00:00") == "unknown_asset_class"


def test_classify_mt5_paths():
    assert classify("EURUSD", r"Forex\Majors\EURUSD") == "fx_major"
    assert classify("USDJPY", r"Forex\Majors\USDJPY") == "fx_jpy"
    assert classify("EURJPY", r"Forex\Minors\EURJPY") == "fx_jpy"
    assert classify("USDZAR", r"Forex\Exotics\USDZAR") == "fx_exotic"
    assert classify("XAUUSD", r"Metals\XAUUSD") == "metal"
    assert classify("US500", r"Indices\US500") == "index_us"
    assert classify("NAS100", r"Indices\NAS100") == "index_us"
    assert classify("GER40", r"Indices\GER40") == "index_eu"
    assert classify("JP225", r"Indices\JP225") == "index_asia"
    assert classify("XTIUSD", r"Energies\XTIUSD") == "energy"
    assert classify("BTCUSD", r"Crypto\BTCUSD") == "crypto"
    assert classify("AAPL", r"Stocks\US\AAPL") == "stock_us"
    assert classify("SAP", r"Stocks\EU\SAP") == "stock_eu"
    assert classify("FOO", r"Custom\FOO") == "unknown"
    # Broker suffix must not change the class.
    assert classify("EURUSD.pro", r"Forex\EURUSD.pro") == "fx_major"


def test_shipped_config_is_paper_500_eur():
    risk = CFG["risk"]
    assert risk["paper_equity_eur"] == 500
    assert 0.005 <= risk["risk_per_trade"] <= 0.01
    assert risk["max_daily_loss"] == 0.03
    assert "live_trading" not in CFG

"""Session windows by asset class, with DST and per-symbol overrides.

The scanner is idle outside these windows: weekends, the daily FX rollover,
and hours that are not the active session for that market.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone


@dataclass(frozen=True, slots=True)
class SessionDecision:
    open: bool
    reason: str


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """weekday: Monday=0 .. Sunday=6. n=1 is the first, n=-1 the last."""
    if n > 0:
        cursor = date(year, month, 1)
        shift = (weekday - cursor.weekday()) % 7
        return cursor + timedelta(days=shift + (n - 1) * 7)
    if month == 12:
        cursor = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        cursor = date(year, month + 1, 1) - timedelta(days=1)
    shift = (cursor.weekday() - weekday) % 7
    return cursor - timedelta(days=shift)


def eu_dst(day: date) -> bool:
    """EU/UK civil DST: last Sunday of March through the day before the last Sunday of October."""
    start = nth_weekday(day.year, 3, 6, -1)
    end = nth_weekday(day.year, 10, 6, -1)
    return start <= day < end


def us_dst(day: date) -> bool:
    """US civil DST: second Sunday of March through the day before the first Sunday of November."""
    start = nth_weekday(day.year, 3, 6, 2)
    end = nth_weekday(day.year, 11, 6, 1)
    return start <= day < end


def au_dst(day: date) -> bool:
    """Sydney DST: first Sunday of October through the day before the first Sunday of April."""
    start = nth_weekday(day.year, 10, 6, 1)
    end = nth_weekday(day.year, 4, 6, 1)
    return day >= start or day < end


def utc_offset_hours(exchange: str, day: date) -> int:
    if exchange == "utc":
        return 0
    if exchange == "london":
        return 1 if eu_dst(day) else 0
    if exchange == "europe":
        return 2 if eu_dst(day) else 1
    if exchange == "new_york":
        return -4 if us_dst(day) else -5
    if exchange == "tokyo":
        return 9
    if exchange == "hong_kong":
        return 8
    if exchange == "sydney":
        return 11 if au_dst(day) else 10
    raise ValueError(f"Unknown exchange clock: {exchange}")


def to_local(ts_utc: datetime, exchange: str) -> datetime:
    if ts_utc.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware UTC")
    ts_utc = ts_utc.astimezone(timezone.utc)
    offset = utc_offset_hours(exchange, ts_utc.date())
    local = ts_utc + timedelta(hours=offset)
    # The offset depends on the local date. One correction covers the midnight cross.
    offset2 = utc_offset_hours(exchange, local.date())
    if offset2 != offset:
        local = ts_utc + timedelta(hours=offset2)
    return local.replace(tzinfo=timezone.utc)  # wall-clock stored as aware UTC for comparisons only


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _in_clock_window(ts_utc: datetime, window: dict, default_clock: str) -> bool:
    clock = window.get("clock") or default_clock
    local = to_local(ts_utc, clock)
    if local.weekday() not in window["dow"]:
        return False
    start = _parse_hhmm(window["start"])
    end = _parse_hhmm(window["end"])
    current = local.time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def fx_market_closed(ts_utc: datetime) -> bool:
    """FX weekend in New York: Friday 17:00 through Sunday 17:00."""
    local = to_local(ts_utc, "new_york")
    wd = local.weekday()
    current = local.time()
    if wd == 5:
        return True
    if wd == 6 and current < time(17, 0):
        return True
    if wd == 4 and current >= time(17, 0):
        return True
    return False


def in_rollover(ts_utc: datetime) -> bool:
    """Daily interbank roll, 16:55–17:15 New York."""
    local = to_local(ts_utc, "new_york")
    current = local.time()
    return time(16, 55) <= current < time(17, 15)


def _weekend_closed(ts_utc: datetime, mode: str, clock: str) -> bool:
    if mode in (None, "none"):
        return False
    if mode == "new_york_fx":
        return fx_market_closed(ts_utc)
    if mode == "sat_sun":
        return to_local(ts_utc, clock).weekday() >= 5
    raise ValueError(f"Unknown weekend mode: {mode}")


def resolve_schedule(symbol: str, asset_class: str, cfg: dict) -> tuple[str, dict]:
    classes = cfg["sessions"]["classes"]
    overrides = cfg["sessions"].get("symbol_overrides") or {}
    override = overrides.get(symbol) or overrides.get(symbol.upper()) or {}
    cls = override.get("asset_class", asset_class)
    if cls not in classes:
        cls = "unknown"
    schedule = deepcopy(classes[cls])
    for key in ("clock", "weekend", "rollover", "windows"):
        if key in override and key != "asset_class":
            schedule[key] = override[key]
    # asset_class on the override already applied. A windows key of [] is meaningful.
    if "asset_class" in override and "windows" in override:
        schedule["windows"] = override["windows"]
    return cls, schedule


def session_state(ts_utc: datetime, asset_class: str, schedule: dict) -> SessionDecision:
    if asset_class == "unknown":
        return SessionDecision(False, "unknown_asset_class")
    clock = schedule.get("clock") or "utc"
    if _weekend_closed(ts_utc, schedule.get("weekend"), clock):
        return SessionDecision(False, "weekend_closed")
    if schedule.get("rollover") and in_rollover(ts_utc):
        return SessionDecision(False, "rollover")
    windows = schedule.get("windows") or []
    if not windows:
        return SessionDecision(False, "outside_session")
    for window in windows:
        if _in_clock_window(ts_utc, window, clock):
            return SessionDecision(True, "open")
    return SessionDecision(False, "outside_session")


def session_open(symbol: str, asset_class: str, ts_utc: datetime, cfg: dict) -> SessionDecision:
    cls, schedule = resolve_schedule(symbol, asset_class, cfg)
    state = session_state(ts_utc, cls, schedule)
    return state

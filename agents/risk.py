"""Deterministic risk agent: size, daily loss, kill switch. Paper only."""

from __future__ import annotations

import math


def _reject(reason: str) -> dict:
    return {"approve": False, "units": 0.0, "reason": reason, "risk_eur": 0.0, "notional_eur": 0.0, "action": "skip"}


def floor_step(units: float, step: float) -> float:
    if step <= 0:
        return units
    steps = math.floor(units / step + 1e-8)
    return round(steps * step, 10)


def evaluate_risk(candidate: dict, account: dict, risk_cfg: dict, cost_cfg: dict, quote_to_eur: float | None) -> dict:
    """Size one paper trade. Rejects when the kill switch, the daily loss or the budget says no."""
    if account.get("kill_switch"):
        return _reject("kill_switch")
    if account.get("day_halted"):
        return _reject("daily_loss_halt")
    equity = float(account.get("equity") or 0.0)
    if equity <= 0:
        return _reject("no_equity")
    day_start = float(account.get("day_start_equity") or equity)
    if day_start > 0 and (day_start - equity) / day_start >= float(risk_cfg["max_daily_loss"]) - 1e-12:
        return _reject("daily_loss_halt")
    if int(account.get("open_positions") or 0) >= int(risk_cfg["max_open_positions"]):
        return _reject("max_positions")
    trade_mode = candidate.get("trade_mode") or "full"
    direction = int(candidate["direction"])
    if trade_mode == "longonly" and direction < 0:
        return _reject("short_not_allowed")
    if trade_mode == "shortonly" and direction > 0:
        return _reject("long_not_allowed")
    if quote_to_eur is None or quote_to_eur <= 0:
        return _reject("fx_conversion_missing")

    budget = equity * float(risk_cfg["risk_per_trade"])
    open_risk = float(account.get("open_risk_eur") or 0.0)
    if open_risk + budget > equity * float(risk_cfg["max_open_risk"]) + 1e-9:
        return _reject("max_open_risk")

    mid = float(candidate["entry_ref"])
    spread = float(candidate["spread"])
    stop = float(candidate["stop_distance"])
    contract = float(candidate["contract_size"])
    if mid <= 0 or spread <= 0 or stop <= 0 or contract <= 0:
        return _reject("bad_levels")

    slip = float(cost_cfg["slippage_fraction_of_spread"])
    friction = spread / 2.0 + spread * slip
    comm_rate = 2.0 * float(cost_cfg["commission_bps_per_side"]) / 10_000.0
    price_risk = stop + 2.0 * friction
    denom = contract * (price_risk + mid * comm_rate)
    if denom <= 0:
        return _reject("bad_levels")

    min_vol = float(candidate["volume_min"])
    min_loss = min_vol * denom * quote_to_eur
    if min_loss > budget * float(risk_cfg["min_lot_risk_multiple"]):
        return _reject("min_lot_exceeds_risk")

    units = (budget / quote_to_eur) / denom
    notional = units * mid * contract * quote_to_eur
    cap = equity * float(risk_cfg["max_gross_leverage"])
    capped = False
    if notional > cap:
        units = cap / (mid * contract * quote_to_eur)
        capped = True
    units = floor_step(units, float(candidate["volume_step"]))
    if units < min_vol - 1e-12:
        return _reject("below_min_size")

    actual_risk = units * denom * quote_to_eur
    return {
        "approve": True,
        "units": units,
        "reason": "size_capped" if capped else "ok",
        "risk_eur": actual_risk,
        "notional_eur": units * mid * contract * quote_to_eur,
        "action": "paper",
    }

"""Spread, slippage and commission used by the paper broker."""

from __future__ import annotations


def spread_price(mid: float, asset_class: str, cost_cfg: dict, explicit: float | None = None) -> float:
    if explicit is not None and explicit > 0:
        return explicit
    table = cost_cfg["spread_bps"]
    bps = float(table.get(asset_class, table.get("unknown", 10.0)))
    return abs(mid) * bps / 10_000.0


def buy_fill(mid: float, spread: float, slip_fraction: float) -> float:
    return mid + spread / 2.0 + spread * slip_fraction


def sell_fill(mid: float, spread: float, slip_fraction: float) -> float:
    return mid - spread / 2.0 - spread * slip_fraction


def commission_quote(units: float, price: float, contract: float, commission_bps_per_side: float) -> float:
    notional = abs(units) * abs(price) * contract
    return notional * commission_bps_per_side / 10_000.0

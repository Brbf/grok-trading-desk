"""Hard stop on live trading.

The MT5 package can send orders. This module replaces those entry points
before any scan runs, and refuses any account that is not a demo server.
"""

from __future__ import annotations

from types import SimpleNamespace

DEMO_TRADE_MODE = 0  # MetaTrader5.ACCOUNT_TRADE_MODE_DEMO
GUARDED_ATTRS = ("order_send", "login")


class LiveOrderRefused(RuntimeError):
    """Raised for every live-order attempt and for non-demo accounts."""


def _blocked(name: str):
    def _refuse(*_args, **_kwargs):
        raise LiveOrderRefused(
            f"{name} is disabled. This scanner never sends orders and never logs into an account. "
            "Use the paper broker."
        )

    return _refuse


def install_order_guard(mt5_module) -> None:
    """Replace order and login entry points on a MetaTrader5 module (or a fake)."""
    for name in GUARDED_ATTRS:
        setattr(mt5_module, name, _blocked(name))


def assert_demo_account(account) -> None:
    """Require a demo trade mode and a server name that says demo."""
    if account is None:
        raise LiveOrderRefused("No MT5 account info. Refusing to continue.")
    mode = getattr(account, "trade_mode", None)
    try:
        mode_int = int(mode)
    except (TypeError, ValueError) as exc:
        raise LiveOrderRefused(f"Unreadable account trade_mode {mode!r}.") from exc
    if mode_int != DEMO_TRADE_MODE:
        raise LiveOrderRefused(
            f"Account trade_mode {mode_int} is not DEMO ({DEMO_TRADE_MODE}). "
            "Real and contest accounts are refused."
        )
    server = str(getattr(account, "server", "") or "")
    if "demo" not in server.lower():
        raise LiveOrderRefused(
            f"Server {server!r} is not a demo server. Refusing to attach."
        )


def guarded_account(trade_mode: int, server: str, **extra) -> SimpleNamespace:
    """Small helper for tests and for normalising MT5 account objects."""
    payload = {"trade_mode": trade_mode, "server": server}
    payload.update(extra)
    return SimpleNamespace(**payload)

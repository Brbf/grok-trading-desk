"""Read-only MetaTrader 5 adapter.

The official MetaTrader5 package talks to a Windows terminal. On the owner's Mac
that terminal runs under Wine, so this module must be executed by a Windows
Python inside the same Wine prefix. See docs/MT5_WINE_MACOS.md.

This adapter never sends an order. After a demo check it replaces order_send and
login on the MT5 module with functions that raise.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scanner.guards import LiveOrderRefused, assert_demo_account, install_order_guard
from scanner.models import Bar, QuoteSnapshot, SymbolMeta

_TRADE_MODE = {0: "disabled", 1: "longonly", 2: "shortonly", 3: "closeonly", 4: "full"}
_BAR_SECONDS = 3600


class MT5ReadOnlyFeed:
    def __init__(self, cache_path: Path | None = None):
        self.cache_path = cache_path
        self._mt5 = None
        self.cursor = 0
        self.account = None

    def order_send(self, *_args, **_kwargs):
        raise LiveOrderRefused("MT5ReadOnlyFeed refuses order_send. Paper broker only.")

    def connect(self, module=None, terminal_path: str | None = None):
        mt5 = module
        if mt5 is None:
            try:
                import MetaTrader5 as mt5  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "The MetaTrader5 package is not available in this Python. "
                    "On macOS, run a Windows Python inside the MT5 Wine prefix. "
                    "Steps: docs/MT5_WINE_MACOS.md."
                ) from exc
        kwargs = {}
        if terminal_path:
            kwargs["path"] = terminal_path
        # Attach to the terminal that is already logged in. No login, no password.
        ok = mt5.initialize(**kwargs) if kwargs else mt5.initialize()
        if not ok:
            err = mt5.last_error() if hasattr(mt5, "last_error") else "unknown"
            if hasattr(mt5, "shutdown"):
                mt5.shutdown()
            raise RuntimeError(f"mt5.initialize failed: {err}")
        account = mt5.account_info()
        try:
            assert_demo_account(account)
        except LiveOrderRefused:
            if hasattr(mt5, "shutdown"):
                mt5.shutdown()
            raise
        install_order_guard(mt5)
        self._mt5 = mt5
        self.account = {
            "login": getattr(account, "login", None),
            "server": str(getattr(account, "server", "")),
            "currency": str(getattr(account, "currency", "")),
            "trade_mode": "demo",
        }
        return dict(self.account)

    def discover(self, refresh: bool = False) -> list[SymbolMeta]:
        if self._mt5 is None:
            raise RuntimeError("Call connect() before discover().")
        if self.cache_path and self.cache_path.exists() and not refresh:
            cached = _read_cache(self.cache_path)
            if cached is not None:
                return cached
        raw = self._mt5.symbols_get()
        if not raw:
            err = self._mt5.last_error() if hasattr(self._mt5, "last_error") else "empty"
            raise RuntimeError(f"symbols_get returned nothing: {err}")
        metas = [_slim(symbol) for symbol in raw]
        del raw
        if self.cache_path:
            _write_cache(self.cache_path, metas)
        return metas

    def quote_batch(self, symbols: list[SymbolMeta], now: datetime) -> list[QuoteSnapshot]:
        if self._mt5 is None:
            raise RuntimeError("Call connect() before quotes.")
        mt5 = self._mt5
        snapshots = []
        for meta in symbols:
            try:
                mt5.symbol_select(meta.name, True)
            except Exception:
                snapshots.append(_empty_quote(meta.name))
                continue
            tick = mt5.symbol_info_tick(meta.name)
            info = mt5.symbol_info(meta.name)
            snapshots.append(_snapshot(meta, tick, info, now))
        return snapshots

    def rates(self, symbol: str, count: int, now: datetime) -> list[Bar]:
        if self._mt5 is None:
            raise RuntimeError("Call connect() before rates.")
        mt5 = self._mt5
        mt5.symbol_select(symbol, True)
        raw = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, int(count) + 1)
        if raw is None:
            return []
        bars = []
        for row in raw:
            opened = datetime.fromtimestamp(int(row["time"]), tz=timezone.utc)
            # Drop the forming hour. Signals use closed bars only.
            if opened + timedelta(seconds=_BAR_SECONDS) > now:
                continue
            bars.append(
                Bar(
                    time=opened,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["tick_volume"]),
                    spread=None,
                )
            )
        return bars[-count:]

    def release(self, names: list[str]) -> None:
        if self._mt5 is None:
            return
        for name in names:
            try:
                self._mt5.symbol_select(name, False)
            except Exception:
                continue


def _empty_quote(name: str) -> QuoteSnapshot:
    return QuoteSnapshot(name, None, 0.0, 0.0, 0.0, 0, 0.0, 0.0)


def _snapshot(meta: SymbolMeta, tick, info, now: datetime) -> QuoteSnapshot:
    if tick is None:
        return _empty_quote(meta.name)
    bid = float(getattr(tick, "bid", 0.0) or 0.0)
    ask = float(getattr(tick, "ask", 0.0) or 0.0)
    when_raw = int(getattr(tick, "time", 0) or 0)
    when = datetime.fromtimestamp(when_raw, tz=timezone.utc) if when_raw else None
    deals = int(getattr(info, "session_deals", 0) or 0) if info is not None else meta.session_deals
    volume = float(getattr(info, "session_volume", 0) or 0) if info is not None else meta.session_volume
    last = float(getattr(tick, "last", 0.0) or 0.0) or (bid + ask) / 2.0
    spread = ask - bid if ask > 0 and bid > 0 else 0.0
    return QuoteSnapshot(meta.name, when, bid, ask, spread, deals, volume, last)


def _slim(symbol) -> SymbolMeta:
    mode = _TRADE_MODE.get(int(getattr(symbol, "trade_mode", 0) or 0), "disabled")
    raw_time = int(getattr(symbol, "time", 0) or 0)
    last = datetime.fromtimestamp(raw_time, tz=timezone.utc) if raw_time else None
    point = float(getattr(symbol, "point", 0.0) or 0.0) or 0.00001
    return SymbolMeta(
        name=str(symbol.name),
        path=str(getattr(symbol, "path", "") or ""),
        point=point,
        digits=int(getattr(symbol, "digits", 5) or 5),
        contract_size=float(getattr(symbol, "trade_contract_size", 1.0) or 1.0),
        volume_min=float(getattr(symbol, "volume_min", 0.01) or 0.01),
        volume_step=float(getattr(symbol, "volume_step", 0.01) or 0.01),
        currency_base=str(getattr(symbol, "currency_base", "") or ""),
        currency_profit=str(getattr(symbol, "currency_profit", "") or ""),
        trade_mode=mode,
        visible=bool(getattr(symbol, "visible", False)),
        spread_points=int(getattr(symbol, "spread", 0) or 0),
        session_deals=int(getattr(symbol, "session_deals", 0) or 0),
        session_volume=float(getattr(symbol, "session_volume", 0) or 0),
        last_quote_time=last,
        bid=float(getattr(symbol, "bid", 0.0) or 0.0),
        ask=float(getattr(symbol, "ask", 0.0) or 0.0),
    )


def _write_cache(path: Path, metas: list[SymbolMeta]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(metas),
        "symbols": [
            {
                "name": m.name,
                "path": m.path,
                "point": m.point,
                "digits": m.digits,
                "contract_size": m.contract_size,
                "volume_min": m.volume_min,
                "volume_step": m.volume_step,
                "currency_base": m.currency_base,
                "currency_profit": m.currency_profit,
                "trade_mode": m.trade_mode,
                "visible": m.visible,
            }
            for m in metas
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_cache(path: Path, max_age_hours: float = 24.0) -> list[SymbolMeta] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(payload["fetched_at"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - fetched > timedelta(hours=max_age_hours):
        return None
    metas = []
    for row in payload.get("symbols", []):
        metas.append(
            SymbolMeta(
                name=row["name"],
                path=row.get("path", ""),
                point=float(row.get("point", 0.00001)),
                digits=int(row.get("digits", 5)),
                contract_size=float(row.get("contract_size", 1)),
                volume_min=float(row.get("volume_min", 0.01)),
                volume_step=float(row.get("volume_step", 0.01)),
                currency_base=row.get("currency_base", ""),
                currency_profit=row.get("currency_profit", ""),
                trade_mode=row.get("trade_mode", "disabled"),
                visible=bool(row.get("visible", False)),
            )
        )
    return metas

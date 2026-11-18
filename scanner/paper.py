"""Paper broker. Tracks a 500 EUR simulated account and refuses order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from scanner.costs import buy_fill, commission_quote, sell_fill, spread_price
from scanner.guards import LiveOrderRefused


@dataclass(slots=True)
class _Order:
    symbol: str
    direction: int
    units: float
    stop_distance: float
    risk_eur: float
    signal_time: datetime
    latest_open: datetime
    asset_class: str
    contract_size: float
    quote_currency: str
    explicit_spread: float | None
    signal_index: int


@dataclass(slots=True)
class _Position:
    symbol: str
    direction: int
    units: float
    entry_fill: float
    entry_mid: float
    stop_mid: float
    entry_time: datetime
    entry_index: int
    risk_eur: float
    asset_class: str
    contract_size: float
    quote_currency: str
    explicit_spread: float | None
    max_hold: int
    last_mid: float
    last_q2e: float
    entry_comm_eur: float = 0.0
    signal_time: datetime | None = None


@dataclass(slots=True)
class PaperTrade:
    symbol: str
    direction: int
    units: float
    entry_time: datetime
    exit_time: datetime
    entry_fill: float
    exit_fill: float
    pnl_eur: float
    reason: str
    asset_class: str
    quote_currency: str
    signal_time: datetime | None = None

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": "long" if self.direction > 0 else "short",
            "units": self.units,
            "signal_time": self.signal_time.isoformat() if self.signal_time else None,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "entry_fill": self.entry_fill,
            "exit_fill": self.exit_fill,
            "pnl_eur": self.pnl_eur,
            "reason": self.reason,
            "asset_class": self.asset_class,
            "quote_currency": self.quote_currency,
        }


@dataclass
class PaperBroker:
    risk_cfg: dict
    cost_cfg: dict
    strategy_cfg: dict
    balance: float = field(init=False)
    initial_equity: float = field(init=False)
    last_equity: float = field(init=False)
    day_start_equity: float = field(init=False)
    day: object = None
    day_halted: bool = False
    permanent_halt: bool = False
    pending: dict[str, _Order] = field(default_factory=dict)
    positions: dict[str, _Position] = field(default_factory=dict)
    trades: list[PaperTrade] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    kill_events: list[dict] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        equity = float(self.risk_cfg["paper_equity_eur"])
        self.balance = equity
        self.initial_equity = equity
        self.last_equity = equity
        self.day_start_equity = equity

    def order_send(self, *_args, **_kwargs):
        raise LiveOrderRefused("PaperBroker has no live order path. order_send is refused.")

    def account_state(self) -> dict:
        return {
            "equity": self.last_equity,
            "day_start_equity": self.day_start_equity,
            "open_positions": len(self.positions) + len(self.pending),
            "open_risk_eur": (
                sum(p.risk_eur for p in self.positions.values())
                + sum(o.risk_eur for o in self.pending.values())
            ),
            "kill_switch": self.permanent_halt,
            "day_halted": self.day_halted,
        }

    def allows_entries(self) -> bool:
        return not self.permanent_halt and not self.day_halted

    def roll_day(self, ts: datetime) -> None:
        if self.day is None:
            self.day = ts.date()
            self.day_start_equity = self.last_equity
            return
        if ts.date() != self.day:
            self.day = ts.date()
            self.day_start_equity = self.last_equity
            self.day_halted = False

    def queue(self, order: dict) -> None:
        if not self.allows_entries():
            self.notes.append({"symbol": order["symbol"], "reason": "halted"})
            return
        symbol = order["symbol"]
        if symbol in self.positions or symbol in self.pending:
            self.notes.append({"symbol": symbol, "reason": "already_open"})
            return
        self.pending[symbol] = _Order(
            symbol=symbol,
            direction=int(order["direction"]),
            units=float(order["units"]),
            stop_distance=float(order["stop_distance"]),
            risk_eur=float(order["risk_eur"]),
            signal_time=order["signal_time"],
            latest_open=order["signal_time"] + timedelta(seconds=int(self.strategy_cfg["max_fill_delay_seconds"])),
            asset_class=order["asset_class"],
            contract_size=float(order["contract_size"]),
            quote_currency=order["quote_currency"],
            explicit_spread=order.get("explicit_spread"),
            signal_index=int(order["signal_index"]),
        )

    def on_bar(self, symbol: str, bar, index: int, quote_to_eur: float | None) -> list[str]:
        """Fill a queued entry at the open, then apply stop and time-exit on this bar."""
        events: list[str] = []
        if quote_to_eur is None or quote_to_eur <= 0:
            if symbol in self.pending:
                self._drop_pending(symbol, "fx_conversion_missing")
                events.append("fx_conversion_missing")
            return events
        order = self.pending.get(symbol)
        if order is not None:
            if bar.time > order.latest_open:
                self._drop_pending(symbol, "stale_fill")
                events.append("stale_fill")
            elif not self.allows_entries():
                self._drop_pending(symbol, "halted")
                events.append("halted")
            else:
                self._fill(order, bar, index, quote_to_eur)
                events.append("fill")
        position = self.positions.get(symbol)
        if position is not None:
            reason = self._maybe_exit(position, bar, index, quote_to_eur)
            if reason:
                events.append(reason)
        elif symbol in self.positions:
            pass
        position = self.positions.get(symbol)
        if position is not None:
            position.last_mid = bar.close
            position.last_q2e = quote_to_eur
        return events

    def _fill(self, order: _Order, bar, index: int, quote_to_eur: float) -> None:
        self.pending.pop(order.symbol, None)
        spr = spread_price(bar.open, order.asset_class, self.cost_cfg, bar.spread or order.explicit_spread)
        slip = float(self.cost_cfg["slippage_fraction_of_spread"])
        fill = buy_fill(bar.open, spr, slip) if order.direction > 0 else sell_fill(bar.open, spr, slip)
        comm = commission_quote(order.units, fill, order.contract_size, float(self.cost_cfg["commission_bps_per_side"]))
        entry_comm_eur = comm * quote_to_eur
        self.balance -= entry_comm_eur
        self.positions[order.symbol] = _Position(
            symbol=order.symbol,
            direction=order.direction,
            units=order.units,
            entry_fill=fill,
            entry_mid=bar.open,
            stop_mid=bar.open - order.direction * order.stop_distance,
            entry_time=bar.time,
            entry_index=index,
            risk_eur=order.risk_eur,
            asset_class=order.asset_class,
            contract_size=order.contract_size,
            quote_currency=order.quote_currency,
            explicit_spread=bar.spread or order.explicit_spread,
            max_hold=int(self.strategy_cfg["max_hold_bars"]),
            last_mid=bar.close,
            last_q2e=quote_to_eur,
            entry_comm_eur=entry_comm_eur,
            signal_time=order.signal_time,
        )

    def _maybe_exit(self, position: _Position, bar, index: int, quote_to_eur: float) -> str | None:
        slip = float(self.cost_cfg["slippage_fraction_of_spread"])
        decision = None
        raw = None
        if position.direction > 0 and bar.open <= position.stop_mid:
            decision, raw = "stop", bar.open
        elif position.direction < 0 and bar.open >= position.stop_mid:
            decision, raw = "stop", bar.open
        elif index - position.entry_index >= position.max_hold:
            decision, raw = "time", bar.open
        elif position.direction > 0 and bar.low <= position.stop_mid:
            decision, raw = "stop", position.stop_mid
        elif position.direction < 0 and bar.high >= position.stop_mid:
            decision, raw = "stop", position.stop_mid
        if decision is None or raw is None:
            return None
        spr = spread_price(raw, position.asset_class, self.cost_cfg, bar.spread or position.explicit_spread)
        fill = sell_fill(raw, spr, slip) if position.direction > 0 else buy_fill(raw, spr, slip)
        self._close(position, fill, bar.time, decision, quote_to_eur)
        return decision

    def _close(self, position: _Position, exit_fill: float, when: datetime, reason: str, quote_to_eur: float) -> None:
        gross_quote = position.direction * position.units * position.contract_size * (exit_fill - position.entry_fill)
        comm = commission_quote(
            position.units, exit_fill, position.contract_size, float(self.cost_cfg["commission_bps_per_side"])
        )
        pnl = (gross_quote - comm) * quote_to_eur - position.entry_comm_eur
        # Entry commission already left the balance when the position opened.
        self.balance += (gross_quote - comm) * quote_to_eur
        self.positions.pop(position.symbol, None)
        self.trades.append(
            PaperTrade(
                symbol=position.symbol,
                direction=position.direction,
                units=position.units,
                entry_time=position.entry_time,
                exit_time=when,
                entry_fill=position.entry_fill,
                exit_fill=exit_fill,
                pnl_eur=pnl,
                reason=reason,
                asset_class=position.asset_class,
                quote_currency=position.quote_currency,
                signal_time=position.signal_time,
            )
        )

    def _drop_pending(self, symbol: str, reason: str) -> None:
        self.pending.pop(symbol, None)
        self.notes.append({"symbol": symbol, "reason": reason})

    def mark_equity(self, ts: datetime) -> float:
        unrealized = 0.0
        slip = float(self.cost_cfg["slippage_fraction_of_spread"])
        bps = float(self.cost_cfg["commission_bps_per_side"])
        for position in self.positions.values():
            spr = spread_price(position.last_mid, position.asset_class, self.cost_cfg, position.explicit_spread)
            if position.direction > 0:
                exit_px = sell_fill(position.last_mid, spr, slip)
            else:
                exit_px = buy_fill(position.last_mid, spr, slip)
            gross = position.direction * position.units * position.contract_size * (exit_px - position.entry_fill)
            comm = commission_quote(position.units, exit_px, position.contract_size, bps)
            unrealized += (gross - comm) * position.last_q2e
        equity = self.balance + unrealized
        self.last_equity = equity
        self.equity_curve.append((ts, equity))
        return equity

    def enforce_limits(self, ts: datetime) -> None:
        equity = self.last_equity
        day_loss = self.day_start_equity - equity
        daily_limit = self.day_start_equity * float(self.risk_cfg["max_daily_loss"])
        if not self.day_halted and self.day_start_equity > 0 and day_loss >= daily_limit:
            self._flatten(ts, "daily_loss_halt")
            self.day_halted = True
            self.kill_events.append({"time": ts.isoformat(), "kind": "daily_loss_halt", "equity": self.balance})
        floor = self.initial_equity * (1.0 - float(self.risk_cfg["kill_switch_drawdown"]))
        if not self.permanent_halt and (self.balance <= floor or self.last_equity <= floor):
            self._flatten(ts, "kill_switch")
            self.permanent_halt = True
            self.kill_events.append({"time": ts.isoformat(), "kind": "kill_switch", "equity": self.balance})

    def _flatten(self, ts: datetime, reason: str) -> None:
        for symbol in list(self.pending):
            self._drop_pending(symbol, reason)
        for symbol in list(self.positions):
            position = self.positions[symbol]
            spr = spread_price(position.last_mid, position.asset_class, self.cost_cfg, position.explicit_spread)
            slip = float(self.cost_cfg["slippage_fraction_of_spread"])
            if position.direction > 0:
                fill = sell_fill(position.last_mid, spr, slip)
            else:
                fill = buy_fill(position.last_mid, spr, slip)
            self._close(position, fill, ts, reason, position.last_q2e)
        self.last_equity = self.balance

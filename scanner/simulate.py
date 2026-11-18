"""Bar-close simulation. Signals use only closed bars; fills are the next open."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from scanner.models import Bar, RejectionLog, SymbolMeta
from scanner.paper import PaperBroker
from scanner.pipeline import vet_candidate
from scanner.quality import bar_problems, series_problems
from scanner.sessions import resolve_schedule, session_state
from scanner.signals import Prepared, prepare, signal_at
from scanner.fx import FxBook


@dataclass
class Series:
    meta: SymbolMeta
    bars: list[Bar]
    prep: Prepared | None = None
    tradable: bool = False
    exclude_reason: str | None = None
    asset_class: str = "unknown"
    schedule: dict = field(default_factory=dict)


@dataclass
class SimResult:
    label: str
    broker: PaperBroker
    rejections: RejectionLog
    final_equity: float
    trade_from: datetime | None
    trade_until: datetime | None


def build_series(loaded: list[tuple[SymbolMeta, list[Bar]]], cfg: dict, log: RejectionLog) -> list[Series]:
    series_list: list[Series] = []
    for meta, bars in loaded:
        asset, schedule = resolve_schedule(meta.name, meta.asset_class, cfg)
        meta.asset_class = asset
        item = Series(meta=meta, bars=bars, asset_class=asset, schedule=schedule)
        problems = series_problems(bars)
        structural = [reason for reason in problems if reason != "volume_missing"]
        if structural:
            item.exclude_reason = structural[0]
            log.add("data", structural[0], meta.name, bars[0].time if bars else None)
            series_list.append(item)
            continue
        if "volume_missing" in problems:
            item.exclude_reason = "volume_missing"
            if not meta.fx_pair:
                log.add("data", "volume_missing", meta.name, bars[0].time if bars else None)
            else:
                # Kept as a conversion series. Trading it would invent volume.
                log.add("data", "volume_missing_fx_conversion_only", meta.name, bars[0].time if bars else None)
            series_list.append(item)
            continue
        item.tradable = True
        item.prep = prepare(bars, cfg["strategy"])
        series_list.append(item)
    return series_list


def _usd_leg(series: Series) -> int:
    base = series.meta.currency_base.upper()
    quote = series.meta.currency_profit.upper()
    return 0 if "USD" in (base, quote) else 1


def run_walk(
    series_list: list[Series],
    cfg: dict,
    *,
    label: str,
    trade_from: datetime | None = None,
    trade_until: datetime | None = None,
) -> SimResult:
    """Walk every bar. `trade_from` / `trade_until` filter decision time (bar close), not indicator history."""
    log = RejectionLog()
    broker = PaperBroker(cfg["risk"], cfg["costs"], cfg["strategy"])
    book = FxBook()
    events: dict[datetime, list[tuple[Series, int]]] = defaultdict(list)
    for series in series_list:
        if series.exclude_reason and series.exclude_reason != "volume_missing":
            continue
        if not series.tradable and not series.meta.fx_pair:
            continue
        for index, bar in enumerate(series.bars):
            events[bar.time].append((series, index))

    strategy = cfg["strategy"]
    outlier = float(strategy["outlier_range_atr"])
    ordered = sorted(events)
    for step, ts in enumerate(ordered):
        bundle = events[ts]
        broker.roll_day(ts)
        fx_events = sorted((item for item in bundle if item[0].meta.fx_pair), key=lambda item: _usd_leg(item[0]))
        for series, index in fx_events:
            bar = series.bars[index]
            book.update_pair(series.meta.currency_base, series.meta.currency_profit, bar.open)

        for series, index in bundle:
            name = series.meta.name
            if name not in broker.positions and name not in broker.pending:
                continue
            bar = series.bars[index]
            quote_to_eur = book.eur_per_unit(series.meta.currency_profit)
            broker.on_bar(name, bar, index, quote_to_eur)

        for series, index in fx_events:
            bar = series.bars[index]
            book.update_pair(series.meta.currency_base, series.meta.currency_profit, bar.close)
        for position in broker.positions.values():
            quote_to_eur = book.eur_per_unit(position.quote_currency)
            if quote_to_eur:
                position.last_q2e = quote_to_eur
        broker.mark_equity(ts)
        broker.enforce_limits(ts)

        for series, index in bundle:
            if not series.tradable or series.prep is None:
                continue
            prep = series.prep
            if prep.prior_high[index] is None or prep.prior_low[index] is None:
                continue
            bar = series.bars[index]
            if not (bar.close > prep.prior_high[index] or bar.close < prep.prior_low[index]):
                continue
            decision_time = bar.time + timedelta(hours=1)
            if not session_state(decision_time, series.asset_class, series.schedule).open:
                continue
            if trade_from is not None and decision_time < trade_from:
                continue
            if trade_until is not None and decision_time >= trade_until:
                continue

            def session_open_at(moment: datetime, series=series) -> bool:
                return session_state(moment, series.asset_class, series.schedule).open

            reasons = bar_problems(
                series.bars,
                index,
                now=decision_time,
                bar_seconds=3600,
                atr_prev=prep.atr[index - 1] if index else None,
                outlier_multiple=outlier,
                session_open_at=session_open_at,
            )
            if reasons:
                for reason in reasons:
                    log.add("quality", reason, series.meta.name, decision_time)
                continue
            candidate, reason = signal_at(prep, index, series.meta, strategy)
            if candidate is None:
                if reason not in {"warmup", "no_setup"}:
                    log.add("signal", reason, series.meta.name, decision_time)
                continue
            if not broker.allows_entries():
                log.add("risk", "halted", series.meta.name, decision_time)
                continue
            quote_to_eur = 1.0 if series.meta.currency_profit.upper() == "EUR" else book.eur_per_unit(series.meta.currency_profit)
            order = vet_candidate(
                candidate,
                series.meta,
                cfg,
                broker.account_state(),
                quote_to_eur,
                log,
                calendar=None,
            )
            if order is None:
                continue
            order["signal_time"] = decision_time
            broker.queue(order)
        if step and step % 4000 == 0:
            print(f"  {label} {step}/{len(ordered)} {ts.date()} equity {broker.last_equity:.2f}", flush=True)

    if events:
        # Realise anything still open so the reported P&L is not an unrealised mark.
        broker._flatten(max(events), "end_of_sample")
        broker.last_equity = broker.balance
        broker.equity_curve.append((max(events), broker.balance))
    return SimResult(
        label=label,
        broker=broker,
        rejections=log,
        final_equity=broker.last_equity,
        trade_from=trade_from,
        trade_until=trade_until,
    )

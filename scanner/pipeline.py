"""Wire the scanner into Scout, the risk agent, Skeptic and the coordinator."""

from __future__ import annotations

import time
from datetime import datetime

from agents.charts import review_levels
from agents.chief import coordinate
from agents.news import review_news
from agents.risk import evaluate_risk
from agents.scout import evaluate_volume_anomaly
from agents.sentiment import review_sentiment
from agents.skeptic import review_candidate

from scanner.costs import spread_price
from scanner.funnel import (
    apply_quote_spread,
    last_bar_quality,
    stage1,
    stage2,
    stage3_activity,
    take_batch,
)
from scanner.fx import FxBook
from scanner.models import Candidate, RejectionLog, SymbolMeta
from scanner.news_calendar import in_blackout
from scanner.paper import PaperBroker
from scanner.quality import gate_candidate, resolve_conflicts, series_problems
from scanner.signals import prepare, signal_at

# Pulled once per scan so USD (and a few other) quotes can be sized in EUR.
_FX_PAIRS = (
    ("EURUSD", "EUR", "USD"),
    ("GBPUSD", "GBP", "USD"),
    ("USDJPY", "USD", "JPY"),
    ("USDCHF", "USD", "CHF"),
    ("AUDUSD", "AUD", "USD"),
    ("NZDUSD", "NZD", "USD"),
    ("USDCAD", "USD", "CAD"),
)


def assess_candidate(
    candidate: Candidate,
    meta: SymbolMeta,
    cfg: dict,
    account: dict,
    quote_to_eur: float | None,
    log: RejectionLog,
    calendar: list[dict] | None,
) -> dict:
    """Quality gate, then Scout, charts, news, sentiment, Skeptic, risk and the coordinator.

    Charts levels come from the closed bar. News is the calendar or an explicit
    "not verified". Sentiment is ignored. The language model is not called.
    """
    if candidate.spread <= 0:
        candidate.spread = spread_price(candidate.entry_ref, candidate.asset_class, cfg["costs"])
        candidate.spread_atr = candidate.spread / candidate.atr if candidate.atr else 0.0
    payload = candidate.as_dict()
    payload["trade_mode"] = meta.trade_mode
    charts = review_levels(payload)
    news = review_news(payload, calendar_loaded=calendar is not None)
    sentiment = review_sentiment(payload)
    reasons = gate_candidate(candidate, log)
    if calendar is not None:
        currencies = {meta.currency_base.upper(), meta.currency_profit.upper(), candidate.symbol.upper()}
        if in_blackout(currencies, candidate.time, calendar, int(cfg["strategy"]["news_blackout_minutes"])):
            candidate.news_blackout = True
            payload["news_blackout"] = True
            news = review_news(payload, calendar_loaded=True)
    limits = cfg["strategy"]
    scout = evaluate_volume_anomaly(
        candidate.symbol,
        candidate.volume_ratio,
        candidate.range_atr,
        float(limits["volume_ratio_min"]),
        float(limits["scout_range_atr_min"]),
    )
    skeptic = review_candidate(payload, limits)
    risk = evaluate_risk(payload, account, cfg["risk"], cfg["costs"], quote_to_eur)
    if reasons:
        decision = {
            "decision": "hold",
            "size": 0.0,
            "reason": "quality:" + ",".join(reasons),
            "mode": "PAPER_ONLY",
            "live_order": False,
        }
    else:
        if not scout["anomaly"]:
            log.add("scout", scout["reason"], candidate.symbol, candidate.time)
        if not skeptic["approve"]:
            log.add("skeptic", skeptic["reason"], candidate.symbol, candidate.time)
        if not risk["approve"]:
            log.add("risk", risk["reason"], candidate.symbol, candidate.time)
        decision = coordinate(payload, scout, skeptic, risk)
    order = None
    if decision["decision"] in ("paper_buy", "paper_sell") and not decision.get("live_order"):
        order = {
            "symbol": candidate.symbol,
            "direction": candidate.direction,
            "units": risk["units"],
            "stop_distance": candidate.stop_distance,
            "risk_eur": risk["risk_eur"],
            "signal_time": candidate.time,
            "asset_class": candidate.asset_class,
            "contract_size": candidate.contract_size,
            "quote_currency": candidate.quote_currency,
            "explicit_spread": candidate.spread,
            "signal_index": candidate.bar_index,
            "decision": decision,
            "scout": scout,
            "skeptic": skeptic,
            "risk": risk,
            "charts": charts,
            "news": news,
            "sentiment": sentiment,
        }
    else:
        log.add("coordinator", decision["reason"], candidate.symbol, candidate.time)
    return {
        "symbol": candidate.symbol,
        "time": payload.get("time"),
        "charts": charts,
        "news": news,
        "sentiment": sentiment,
        "scout": scout,
        "skeptic": skeptic,
        "risk": {key: risk[key] for key in ("approve", "units", "reason", "risk_eur", "notional_eur", "action")},
        "chief": decision,
        "order": order,
    }


def vet_candidate(
    candidate: Candidate,
    meta: SymbolMeta,
    cfg: dict,
    account: dict,
    quote_to_eur: float | None,
    log: RejectionLog,
    calendar: list[dict] | None,
) -> dict | None:
    """Paper order, or None. Same checks as assess_candidate."""
    return assess_candidate(candidate, meta, cfg, account, quote_to_eur, log, calendar)["order"]


def _prime_fx(feed, names: set[str], now: datetime) -> FxBook:
    book = FxBook()
    for symbol, base, quote in _FX_PAIRS:
        if symbol not in names:
            continue
        try:
            bars = feed.rates(symbol, 8, now)
        except Exception:
            continue
        if bars:
            book.update_pair(base, quote, bars[-1].close)
    return book


def scan_once(feed, cfg: dict, now: datetime, calendar: list[dict] | None = None, broker: PaperBroker | None = None) -> dict:
    """One pass. Idle (no history requests) when no discovered symbol is in session."""
    log = RejectionLog()
    if broker is None:
        broker = PaperBroker(cfg["risk"], cfg["costs"], cfg["strategy"])
    broker.roll_day(now)
    discovered = feed.discover()
    names = {symbol.name for symbol in discovered}
    book = _prime_fx(feed, names, now)
    tradable = stage1(discovered, now, cfg, log)
    limit = int(cfg["funnel"]["max_history_requests_per_cycle"])
    batch, feed.cursor = take_batch(tradable, int(getattr(feed, "cursor", 0) or 0), limit)
    quotes = []
    pause = float(cfg["funnel"]["pause_ms"]) / 1000.0
    size = max(1, int(cfg["funnel"]["batch_size"]))
    for start in range(0, len(batch), size):
        quotes.extend(feed.quote_batch(batch[start:start + size], now))
        if pause and start + size < len(batch):
            time.sleep(pause)
    liquid = stage2(batch, quotes, now, cfg, log)
    liquid_names = {symbol.name for symbol, _quote in liquid}
    feed.release([symbol.name for symbol in batch if symbol.name not in liquid_names])

    found: list[tuple[SymbolMeta, Candidate]] = []
    tape: list[dict] = []
    history_bars = int(cfg["funnel"]["history_bars"])
    for symbol, quote in liquid:
        bars = feed.rates(symbol.name, history_bars, now)
        apply_quote_spread(bars, quote.spread)
        if bars:
            last = bars[-1]
            tape.append({
                "symbol": symbol.name,
                "asset_class": symbol.asset_class,
                "time": last.time.isoformat(),
                "close": last.close,
                "volume": last.volume,
                "spread": quote.spread,
            })
        structural = series_problems(bars)
        if structural:
            for reason in structural:
                log.add("quality", reason, symbol.name, now)
            continue
        problems = last_bar_quality(symbol, bars, now, cfg)
        if problems:
            for reason in problems:
                log.add("quality", reason, symbol.name, now)
            continue
        aligned, reason, _atr_ratio, _volume_ratio = stage3_activity(bars, cfg)
        if not aligned:
            log.add("funnel", reason, symbol.name, now)
            continue
        prep = prepare(bars, cfg["strategy"])
        candidate, sig_reason = signal_at(prep, len(bars) - 1, symbol, cfg["strategy"])
        if candidate is None:
            log.add("signal", sig_reason, symbol.name, bars[-1].time if bars else now)
            continue
        candidate.spread = quote.spread
        candidate.spread_atr = quote.spread / candidate.atr if candidate.atr else 0.0
        found.append((symbol, candidate))
    feed.release([symbol.name for symbol, _candidate in found])

    by_symbol = {symbol.name: symbol for symbol, _candidate in found}
    kept = resolve_conflicts([candidate for _symbol, candidate in found], log)
    decisions = []
    reviews = []
    for candidate in kept:
        meta = by_symbol[candidate.symbol]
        quote_to_eur = 1.0 if meta.currency_profit.upper() == "EUR" else book.eur_per_unit(meta.currency_profit)
        review = assess_candidate(candidate, meta, cfg, broker.account_state(), quote_to_eur, log, calendar)
        reviews.append({key: review[key] for key in (
            "symbol", "time", "charts", "news", "sentiment", "scout", "skeptic", "risk", "chief",
        )})
        order = review["order"]
        if order is None:
            continue
        broker.queue(order)
        decisions.append({
            "symbol": candidate.symbol,
            "decision": order["decision"],
            "scout": order["scout"],
            "skeptic": order["skeptic"],
            "charts": order["charts"],
            "news": order["news"],
            "sentiment": order["sentiment"],
            "risk": {k: order["risk"][k] for k in ("approve", "units", "reason", "risk_eur", "notional_eur")},
        })
    return {
        "now": now.isoformat(),
        "discovered": len(discovered),
        "stage1_open": len(tradable),
        "stage1_deferred": max(0, len(tradable) - len(batch)),
        "quoted": len(batch),
        "stage2_pass": len(liquid),
        "stage3_candidates": len(found),
        "paper_orders": len(decisions),
        "decisions": decisions,
        "reviews": reviews,
        "tape": tape,
        "rejections": log.as_dict(),
        "account": broker.account_state(),
        "idle": len(tradable) == 0,
        "mode": "PAPER_ONLY",
    }

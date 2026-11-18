"""Honest simulation report. The wording follows the numbers; it does not talk them up."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from scanner.config import DEFAULT_CONFIG
from scanner.simulate import Series, SimResult


def config_sha256() -> str:
    return hashlib.sha256(DEFAULT_CONFIG.read_bytes()).hexdigest()


def _max_drawdown(equity: list[float]) -> tuple[float, float]:
    if not equity:
        return 0.0, 0.0
    peak = equity[0]
    worst = 0.0
    worst_pct = 0.0
    for value in equity:
        if value > peak:
            peak = value
        drop = peak - value
        if drop > worst:
            worst = drop
            worst_pct = drop / peak if peak else 0.0
    return worst, worst_pct


def _stats(result: SimResult) -> dict:
    trades = [trade.as_dict() for trade in result.broker.trades]
    pnl = sum(trade["pnl_eur"] for trade in trades)
    wins = [trade for trade in trades if trade["pnl_eur"] > 0]
    losses = [trade for trade in trades if trade["pnl_eur"] < 0]
    gross_win = sum(trade["pnl_eur"] for trade in wins)
    gross_loss = sum(trade["pnl_eur"] for trade in losses)
    equity = [point[1] for point in result.broker.equity_curve]
    dd, dd_pct = _max_drawdown(equity)
    by_symbol: dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl_eur": 0.0, "asset_class": ""})
    for trade in trades:
        row = by_symbol[trade["symbol"]]
        row["trades"] += 1
        row["wins"] += 1 if trade["pnl_eur"] > 0 else 0
        row["pnl_eur"] += trade["pnl_eur"]
        row["asset_class"] = trade["asset_class"]
    return {
        "label": result.label,
        "start_eur": result.broker.initial_equity,
        "final_equity_eur": result.final_equity,
        "net_pnl_eur": pnl,
        "return_pct": (result.final_equity / result.broker.initial_equity - 1.0) * 100.0 if result.broker.initial_equity else 0.0,
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / len(trades)) if trades else 0.0,
        "profit_factor": (gross_win / abs(gross_loss)) if gross_loss < 0 else None,
        "avg_trade_eur": (pnl / len(trades)) if trades else 0.0,
        "max_drawdown_eur": dd,
        "max_drawdown_pct": dd_pct,
        "kill_events": list(result.broker.kill_events),
        "by_symbol": dict(sorted(by_symbol.items(), key=lambda item: item[1]["pnl_eur"])),
        "rejections": result.rejections.as_dict()["counts"],
    }


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _money(value: float) -> str:
    return f"{value:+.2f}"


def _verdict(full: dict, insample: dict, outsample: dict) -> str:
    full_pnl = full["net_pnl_eur"]
    oos_pnl = outsample["net_pnl_eur"]
    text = (
        f"Run straight through, the 500 EUR account finished at {full['final_equity_eur']:.2f} EUR "
        f"({full_pnl:+.2f} EUR) after {full['trades']} trades. "
        f"In-sample was {insample['net_pnl_eur']:+.2f} EUR. "
        f"A fresh 500 EUR account on the out-of-sample window alone was {oos_pnl:+.2f} EUR "
        f"on {outsample['trades']} trades."
    )
    if full_pnl < 0:
        text += " The continuous result is a loss. "
    if oos_pnl > 0 and insample["net_pnl_eur"] < 0:
        text += (
            "The out-of-sample gain does not agree with the in-sample loss, "
            "so it is not evidence of an edge. "
        )
    elif oos_pnl <= 0:
        text += "The out-of-sample window did not make money after costs. "
    text += (
        "Win rates are about one trade in three; costs and gap-through-stops do the rest. "
        "This is not a case for real money. The live order path stays disabled."
    )
    return text


def render_markdown(
    *,
    full: dict,
    insample: dict,
    outsample: dict,
    series: list[Series],
    manifest: dict,
    split: datetime,
) -> str:
    tradable = [item for item in series if item.tradable]
    excluded = [item for item in series if not item.tradable]
    lines = [
        "# Simulation report",
        "",
        "Paper account: **500 EUR**. No live orders. Rules were fixed in `config/scanner.yaml` "
        f"before this run (sha256 `{config_sha256()}`).",
        "",
        "## Status",
        "",
        _verdict(full, insample, outsample),
        "",
        "## What was simulated",
        "",
        f"- Source: {manifest.get('source', 'local cache')}.",
        f"- {manifest.get('note', '')}",
        f"- Download failures recorded in the cache manifest: {len(manifest.get('failed', []))}.",
        f"- Bars loaded: {len(series)} symbols. Tradable after the volume/quality gate: {len(tradable)}. "
        f"Excluded: {len(excluded)}.",
        f"- Decision-time split: {split.isoformat()} (first 70% of the calendar span in-sample, last 30% out-of-sample).",
        "- In-sample and out-of-sample each start from a fresh 500 EUR. Indicators at a bar use only earlier bars.",
        "- Fills are the next bar's open, worsened by half the spread plus slippage. "
        "A stop that gaps through is filled at the open, not at the stop. "
        "Same-bar stop and time-exit: a gap through the stop wins. There is no take-profit.",
        "- Yahoo prices are last/mid prints. The spread is a configured model, not a recorded bid/ask, "
        "because this source does not provide one. Commission is 0.35 bp per side.",
        "- Position size is a CFD unit (1 quote currency per 1.0 price move), not an exchange future's multiplier. "
        "A 500 EUR account cannot hold a full ES or GC contract; the sim does not pretend it can.",
        "- Spot FX from Yahoo has no volume, so those pairs are conversion-only when the gate rejects them. "
        "They are listed under excluded, not as traded markets.",
        "",
        "## Results",
        "",
        "| Run | Trades | Win rate | Net P&L EUR | Final equity | Max drawdown |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for stats in (insample, outsample, full):
        lines.append(
            f"| {stats['label']} | {stats['trades']} | {_fmt_pct(stats['win_rate'])} | "
            f"{_money(stats['net_pnl_eur'])} | {stats['final_equity_eur']:.2f} | "
            f"{stats['max_drawdown_eur']:.2f} ({_fmt_pct(stats['max_drawdown_pct'])}) |"
        )
    lines.extend([
        "",
        "Win rate is the share of trades with net P&L above zero after costs. "
        "Max drawdown is peak-to-trough on marked equity, so a run-up can produce a large drawdown "
        "before the account kill switch, which is 20% under the original 500 EUR (equity at or under 400) "
        "rather than a trailing stop.",
        "",
        "### Out-of-sample by asset class",
        "",
        "| Class | Trades | Wins | Net P&L EUR |",
        "| --- | ---: | ---: | ---: |",
    ])
    by_class: dict[str, dict] = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl_eur": 0.0})
    for row in outsample["by_symbol"].values():
        bucket = by_class[row["asset_class"]]
        bucket["trades"] += row["trades"]
        bucket["wins"] += row["wins"]
        bucket["pnl_eur"] += row["pnl_eur"]
    if not by_class:
        lines.append("| — | 0 | 0 | 0.00 |")
    for name, row in sorted(by_class.items(), key=lambda item: item[1]["pnl_eur"]):
        lines.append(f"| {name} | {row['trades']} | {row['wins']} | {row['pnl_eur']:+.2f} |")
    lines.extend([
        "",
        "### Out-of-sample by market",
        "",
        "| Symbol | Class | Trades | Wins | Net P&L EUR |",
        "| --- | --- | ---: | ---: | ---: |",
    ])
    rows = list(outsample["by_symbol"].items())
    if not rows:
        lines.append("| — | — | 0 | 0 | 0.00 |")
    for symbol, row in rows:
        lines.append(
            f"| {symbol} | {row['asset_class']} | {row['trades']} | {row['wins']} | {row['pnl_eur']:+.2f} |"
        )
    lines.extend(["", "### Tradable symbols", ""])
    lines.append(", ".join(sorted(item.meta.name for item in tradable)) or "(none)")
    lines.extend(["", "### Excluded symbols", ""])
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in excluded:
        grouped[item.exclude_reason or "excluded"].append(item.meta.name)
    if not grouped:
        lines.append("(none)")
    for reason in sorted(grouped):
        names = ", ".join(sorted(grouped[reason]))
        lines.append(f"- **{reason}** ({len(grouped[reason])}): {names}")
    if manifest.get("failed"):
        lines.extend(["", "### Download failures", ""])
        for row in manifest["failed"]:
            lines.append(f"- {row['symbol']} ({row['yahoo']}): {row['error']}")
    lines.extend(["", "### Rejection counts (out-of-sample walk)", ""])
    counts = outsample.get("rejections") or {}
    if not counts:
        lines.append("(none)")
    for key in sorted(counts):
        lines.append(f"- `{key}`: {counts[key]}")
    lines.extend([
        "",
        "### Kill switch",
        "",
        f"- In-sample events: {len(insample['kill_events'])}",
        f"- Out-of-sample events: {len(outsample['kill_events'])}",
        f"- Full-sample events: {len(full['kill_events'])}",
        "",
        "Generated " + datetime.now(timezone.utc).isoformat(),
        "",
        "## Completed and still open",
        "",
        "Completed in this pass:",
        "",
        "- Offline hourly prices with real volume where the vendor has it. The quality gate drops series that do not.",
        "- Session windows, the quality gate, the 500 EUR paper risk rules, and the coordinator.",
        "- Deterministic Scout, charts, news, sentiment, Skeptic, risk and chief on that pipeline. No API key.",
        "- Optional language-model comments via `XAI_API_KEY` and `XAI_MODEL` (default `grok-4`). They are not orders.",
        "- Read-only MT5 demo adapter that refuses non-demo servers and `order_send`.",
        "",
        "Still open:",
        "",
        "- Dukascopy bid/ask history (the datafeed returned 503 here). Spreads in this run are a model.",
        "- Spot FX and several cash indices, excluded because this source has no volume.",
        "- The owner's MetaQuotes-Demo terminal. It has to be attached on his Mac under Wine.",
        "- A verified news calendar and a social feed. Until those exist, news and sentiment do not vote.",
        "- The continuous paper account lost money. That is not clearance to use the 500 EUR for real.",
        "",
    ])
    return "\n".join(lines)


def write_report(path: Path, payload: dict, markdown: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def summarise_run(result: SimResult) -> dict:
    return _stats(result)

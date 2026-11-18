"""Paper desk.

The decision is always the deterministic pipeline: scanner, quality gate, Scout,
charts, news, sentiment (ignored), Skeptic, risk, coordinator, paper broker.
A language model is asked only when a real API key is present, and its text
cannot change the paper order.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .base import call_agent, llm_available, model_name
from .charts import SYSTEM as CHARTS_SYSTEM
from .chief import SYSTEM as CHIEF_SYSTEM
from .news import SYSTEM as NEWS_SYSTEM
from .scout import SYSTEM as SCOUT_SYSTEM
from .sentiment import SYSTEM as SENTIMENT_SYSTEM
from .skeptic import SYSTEM as SKEPTIC_SYSTEM

_SCAN_BARS = 400


def run_paper_scan(feed, now=None):
    """One deterministic scan. No language-model call and no live order."""
    from scanner.config import load_config
    from scanner.pipeline import scan_once

    if now is None:
        now = datetime.now(timezone.utc)
    return scan_once(feed, load_config(), now)


def _offline_feed():
    from pathlib import Path

    from scanner.feeds.memory import MemoryFeed
    from scanner.feeds.offline import load_cache

    cache = Path(__file__).resolve().parents[1] / "data" / "cache"
    loaded = load_cache(cache, max_bars=_SCAN_BARS)
    if not loaded:
        return None, None
    symbols = [meta for meta, _bars in loaded]
    bars = {meta.name: rows for meta, rows in loaded}
    last_close = max(rows[-1].time for _meta, rows in loaded) + timedelta(hours=1)
    return MemoryFeed(symbols, bars), last_close


def _agents_from_scan(scan: dict) -> dict:
    reviews = scan.get("reviews") or []
    return {
        "scout": [row.get("scout") for row in reviews],
        "news": [row.get("news") for row in reviews],
        "charts": [row.get("charts") for row in reviews],
        "sentiment": [row.get("sentiment") for row in reviews],
        "skeptic": [row.get("skeptic") for row in reviews],
        "risk": [row.get("risk") for row in reviews],
        "chief": [row.get("chief") for row in reviews],
    }


def _brief(scan: dict) -> dict:
    """Facts the optional model is allowed to see. No mock headlines."""
    return {
        "mode": "PAPER_ONLY",
        "now": scan.get("now"),
        "tape": scan.get("tape") or [],
        "reviews": scan.get("reviews") or [],
        "paper_orders": scan.get("paper_orders"),
        "rejection_counts": (scan.get("rejections") or {}).get("counts", {}),
        "note": "Sentiment has no feed. News is calendar-only. Do not invent either.",
    }


def _advisory(brief: dict) -> dict:
    text = json.dumps(brief, default=str)
    out = {}
    for name, system in (
        ("scout", SCOUT_SYSTEM),
        ("news", NEWS_SYSTEM),
        ("charts", CHARTS_SYSTEM),
        ("sentiment", SENTIMENT_SYSTEM),
        ("skeptic", SKEPTIC_SYSTEM),
        ("chief", CHIEF_SYSTEM),
    ):
        try:
            out[name] = call_agent(system, text)
        except Exception as exc:
            out[name] = None
            out["error"] = str(exc)
            break
    return out


def run_trading_desk(feed=None, now=None, use_llm=None):
    """Scan real cached prices (or `feed`) and let the deterministic team decide.

    `use_llm` defaults to on only when XAI_API_KEY is a real key. Advisory text
    is stored separately and is not an order.
    """
    from scanner.config import load_config
    from scanner.pipeline import scan_once

    if feed is None:
        feed, last_close = _offline_feed()
        if feed is None:
            return {
                "mode": "PAPER_ONLY",
                "live_order": False,
                "status": "NO_CACHE",
                "detail": "No offline bars. Run: python -m scanner download --cache data/cache",
                "llm": {"enabled": False, "model": None},
                "agents": {},
                "paper_orders": 0,
            }
        if now is None:
            now = last_close
    if now is None:
        now = datetime.now(timezone.utc)

    scan = scan_once(feed, load_config(), now)
    enabled = llm_available() if use_llm is None else bool(use_llm) and llm_available()
    brief = _brief(scan)
    advisory = _advisory(brief) if enabled else None
    return {
        "mode": "PAPER_ONLY",
        "live_order": False,
        "status": "IDLE" if scan.get("idle") else "SCANNED",
        "llm": {
            "enabled": enabled,
            "model": model_name() if enabled else None,
            "advisory": advisory,
            "advisory_is_not_an_order": True,
        },
        "scan": {
            "now": scan.get("now"),
            "discovered": scan.get("discovered"),
            "stage1_open": scan.get("stage1_open"),
            "quoted": scan.get("quoted"),
            "stage2_pass": scan.get("stage2_pass"),
            "stage3_candidates": scan.get("stage3_candidates"),
            "idle": scan.get("idle"),
        },
        "agents": _agents_from_scan(scan),
        "decisions": scan.get("decisions"),
        "paper_orders": scan.get("paper_orders"),
        "account": scan.get("account"),
        "tape": scan.get("tape"),
        "rejection_counts": brief["rejection_counts"],
    }

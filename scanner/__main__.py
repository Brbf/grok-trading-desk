"""Command line. Default behaviour is one shot, not a resident process.

    python -m scanner download --cache data/cache
    python -m scanner simulate --cache data/cache --report reports/simulation_report.md
    python -m scanner scan --feed offline --at 2026-01-14T15:00:00+00:00
    python -m scanner scan --feed mt5 --once
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scanner.config import load_config
from scanner.feeds.memory import MemoryFeed
from scanner.feeds.offline import load_cache
from scanner.feeds.yahoo import download_universe
from scanner.offline_universe import offline_instruments
from scanner.pipeline import scan_once
from scanner.report import render_markdown, summarise_run, write_report
from scanner.sessions import session_state
from scanner.simulate import build_series, run_walk


def _parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _any_session(now: datetime, cfg: dict) -> bool:
    for name, schedule in cfg["sessions"]["classes"].items():
        if name == "unknown":
            continue
        if session_state(now, name, schedule).open:
            return True
    return False


def _next_open(now: datetime, cfg: dict) -> datetime:
    cursor = now
    for _ in range(7 * 24 * 4):
        cursor += timedelta(minutes=15)
        if _any_session(cursor, cfg):
            return cursor
    return now + timedelta(hours=12)


def _cmd_download(args) -> int:
    specs = offline_instruments()
    print(f"Downloading up to {len(specs)} instruments into {args.cache}", flush=True)
    manifest = download_universe(specs, Path(args.cache), workers=args.workers, refresh=args.refresh)
    print(
        f"ok {len(manifest['downloaded'])} failed {len(manifest['failed'])} "
        f"cached {manifest['skipped_existing']}",
        flush=True,
    )
    return 0 if manifest["downloaded"] or manifest["skipped_existing"] else 1


def _calendar_span(series) -> tuple[datetime, datetime]:
    starts = [item.bars[0].time for item in series if item.bars]
    ends = [item.bars[-1].time + timedelta(hours=1) for item in series if item.bars]
    return min(starts), max(ends)


def _cmd_simulate(args) -> int:
    cache = Path(args.cache)
    loaded = load_cache(cache)
    if not loaded:
        print("No cached bars. Run: python -m scanner download --cache data/cache", file=sys.stderr)
        return 2
    cfg = load_config()
    series = build_series(loaded, cfg, __import__("scanner.models", fromlist=["RejectionLog"]).RejectionLog())
    start, end = _calendar_span(series)
    split = start + (end - start) * 0.70
    print(f"Loaded {len(loaded)} symbols. Split {split.isoformat()}", flush=True)
    insample = run_walk(series, cfg, label="in-sample", trade_until=split)
    print(f"in-sample trades {len(insample.broker.trades)} equity {insample.final_equity:.2f}", flush=True)
    outsample = run_walk(series, cfg, label="out-of-sample", trade_from=split)
    print(f"out-of-sample trades {len(outsample.broker.trades)} equity {outsample.final_equity:.2f}", flush=True)
    full = run_walk(series, cfg, label="full sample")
    print(f"full trades {len(full.broker.trades)} equity {full.final_equity:.2f}", flush=True)
    stats = {
        "in-sample": summarise_run(insample),
        "out-of-sample": summarise_run(outsample),
        "full sample": summarise_run(full),
    }
    manifest_path = cache / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {
        "source": "local cache",
        "note": "No manifest beside the cache.",
    }
    markdown = render_markdown(
        full=stats["full sample"],
        insample=stats["in-sample"],
        outsample=stats["out-of-sample"],
        series=series,
        manifest=manifest,
        split=split,
    )
    payload = {
        "status": "SIMULATION_COMPLETED",
        "split": split.isoformat(),
        "span": {"start": start.isoformat(), "end": end.isoformat()},
        "results": stats,
        "trades": {
            "in-sample": [trade.as_dict() for trade in insample.broker.trades],
            "out-of-sample": [trade.as_dict() for trade in outsample.broker.trades],
            "full sample": [trade.as_dict() for trade in full.broker.trades],
        },
        "tradable": sorted(item.meta.name for item in series if item.tradable),
        "manifest": {
            "source": manifest.get("source"),
            "note": manifest.get("note"),
            "failed": manifest.get("failed", []),
            "downloaded": len(manifest.get("downloaded", [])),
        },
    }
    write_report(Path(args.report), payload, markdown)
    print(f"Wrote {args.report}", flush=True)
    return 0


def _cmd_scan(args) -> int:
    cfg = load_config()
    if args.loop and args.feed == "mt5":
        import time

        from scanner.feeds.mt5 import MT5ReadOnlyFeed

        feed = MT5ReadOnlyFeed(cache_path=Path(args.cache) / "mt5_symbols.json")
        feed.connect(terminal_path=args.terminal_path)
        while True:
            now = datetime.now(timezone.utc)
            if not _any_session(now, cfg):
                wake = _next_open(now, cfg)
                delay = min(900, max(1, int((wake - now).total_seconds())))
                print(f"idle until session window ({wake.isoformat()}), sleeping {delay}s", flush=True)
                time.sleep(delay)
                continue
            result = scan_once(feed, cfg, now)
            print(json.dumps({k: result[k] for k in ("now", "discovered", "stage1_open", "quoted", "paper_orders", "idle")}))
            time.sleep(60)
    now = _parse_time(args.at)
    if args.feed == "mt5":
        from scanner.feeds.mt5 import MT5ReadOnlyFeed

        feed = MT5ReadOnlyFeed(cache_path=Path(args.cache) / "mt5_symbols.json")
        print(json.dumps(feed.connect(terminal_path=args.terminal_path)))
    else:
        loaded = load_cache(Path(args.cache))
        if not loaded:
            print("No cached bars for the offline feed.", file=sys.stderr)
            return 2
        symbols = [meta for meta, _bars in loaded]
        bars = {meta.name: rows for meta, rows in loaded}
        feed = MemoryFeed(symbols, bars)
    result = scan_once(feed, cfg, now)
    print(json.dumps({k: result[k] for k in (
        "now", "discovered", "stage1_open", "stage1_deferred", "quoted",
        "stage2_pass", "stage3_candidates", "paper_orders", "idle", "mode", "decisions",
    )}, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scanner", description="Paper multi-market scanner. No live orders.")
    sub = parser.add_subparsers(dest="command", required=True)

    download = sub.add_parser("download", help="Cache free hourly history for the offline universe")
    download.add_argument("--cache", default="data/cache")
    download.add_argument("--workers", type=int, default=4)
    download.add_argument("--refresh", action="store_true")

    simulate = sub.add_parser("simulate", help="Walk-forward paper simulation on the cache")
    simulate.add_argument("--cache", default="data/cache")
    simulate.add_argument("--report", default="reports/simulation_report.md")

    scan = sub.add_parser("scan", help="One paper scan, or an idle-aware loop for the MT5 demo")
    scan.add_argument("--feed", choices=("offline", "mt5"), default="offline")
    scan.add_argument("--once", action="store_true", default=True)
    scan.add_argument("--loop", action="store_true", help="MT5 only. Sleeps outside session windows.")
    scan.add_argument("--cache", default="data/cache")
    scan.add_argument("--terminal-path", default=None)
    scan.add_argument("--at", default=None, help="UTC time for an offline scan, e.g. 2026-01-14T15:00:00+00:00")

    args = parser.parse_args(argv)
    if args.command == "download":
        return _cmd_download(args)
    if args.command == "simulate":
        return _cmd_simulate(args)
    if args.command == "scan":
        return _cmd_scan(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

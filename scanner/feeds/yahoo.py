"""Download hourly candles from Yahoo's chart endpoint into the local cache.

Yahoo is the free source used when Dukascopy's datafeed is unreachable.
Spot FX from this source has no volume; the quality gate rejects it.
"""

from __future__ import annotations

import csv
import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

_USER_AGENT = "Mozilla/5.0 (compatible; grok-trading-desk/1.0; research)"


def _fetch(yahoo: str, timeout: int = 40) -> dict:
    query = urllib.parse.urlencode({"interval": "1h", "range": "730d", "events": "history"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo)}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    last_error = "empty"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            result = (payload.get("chart") or {}).get("result")
            if not result:
                error = (payload.get("chart") or {}).get("error") or {}
                raise RuntimeError(error.get("description") or "empty chart")
            return result[0]
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code == 429:
                time.sleep(2.0 + attempt * 2.0)
                continue
            if exc.code == 404:
                raise RuntimeError("not found") from exc
            time.sleep(1.0 + attempt)
        except Exception as exc:  # network, JSON, empty chart
            last_error = str(exc)
            time.sleep(1.0 + attempt)
    raise RuntimeError(last_error)


def _write(directory: Path, spec: dict, chart: dict) -> int:
    timestamps = chart.get("timestamp") or []
    quote = chart["indicators"]["quote"][0]
    currency = ((chart.get("meta") or {}).get("currency")) or spec["quote"]
    path = directory / f"{spec['symbol']}.csv.gz"
    rows = 0
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time", "open", "high", "low", "close", "volume"])
        for index, stamp in enumerate(timestamps):
            try:
                prices = [quote["open"][index], quote["high"][index], quote["low"][index], quote["close"][index]]
                if any(price is None for price in prices):
                    continue
                volume = quote["volume"][index]
                volume = 0 if volume is None else volume
                opened = datetime.fromtimestamp(int(stamp), tz=timezone.utc)
            except (TypeError, ValueError, IndexError):
                continue
            writer.writerow([opened.isoformat(), *prices, volume])
            rows += 1
    meta = {
        "symbol": spec["symbol"],
        "yahoo": spec["yahoo"],
        "asset_class": spec["asset_class"],
        "quote": currency,
        "base": spec["base"],
        "contract_size": spec["contract_size"],
        "volume_min": spec["volume_min"],
        "volume_step": spec["volume_step"],
        "fx_pair": spec["fx_pair"],
        "rows": rows,
        "source": "yahoo_chart_1h_730d",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    (directory / f"{spec['symbol']}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return rows


def download_universe(specs: list[dict], directory: Path, workers: int = 4, refresh: bool = False) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    pending = []
    for spec in specs:
        target = directory / f"{spec['symbol']}.csv.gz"
        if target.exists() and not refresh and target.stat().st_size > 0:
            continue
        pending.append(spec)

    ok = []
    failed = []

    def _one(spec: dict) -> tuple[dict, int]:
        try:
            chart = _fetch(spec["yahoo"])
            rows = _write(directory, spec, chart)
            if rows < 100:
                raise RuntimeError(f"only {rows} rows")
            return spec, rows
        except Exception:
            for suffix in (".csv.gz", ".meta.json"):
                partial = directory / f"{spec['symbol']}{suffix}"
                if partial.exists():
                    partial.unlink()
            raise

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_one, spec): spec for spec in pending}
        for future in as_completed(futures):
            spec = futures[future]
            try:
                done, rows = future.result()
                ok.append({"symbol": done["symbol"], "yahoo": done["yahoo"], "rows": rows})
            except Exception as exc:
                failed.append({"symbol": spec["symbol"], "yahoo": spec["yahoo"], "error": str(exc)})
    manifest = {
        "source": "yahoo_chart_1h_730d",
        "note": (
            "Dukascopy's datafeed was not reachable from the build environment (HTTP 503). "
            "Yahoo Finance hourly candles are the free substitute. Spot FX volume on this "
            "source is zero and must be rejected by the quality gate."
        ),
        "downloaded": ok,
        "failed": failed,
        "skipped_existing": len(specs) - len(pending),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

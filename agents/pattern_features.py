"""Causal, research-only chart/candlestick features for Coinbase hourly OHLCV.

This is NOT a model trained from posters, a signal engine, a trade executor or
an accuracy claim. Rule outputs are descriptive observations only. All
computations use candles fully closed at or before the prediction origin.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .fabioquant_offline import read_local, PAIRS
from .geometry_features import geometric_candidates

HOUR = timedelta(hours=1)
MAX_RAW_BYTES = 250_000
SCHEMA = "GrokDesk-Hourly-Pattern-Features-Research-v1"
PATTERN_NAMES = (
    "doji_shape", "hammer_shape", "shooting_star_shape",
    "bullish_engulfing_shape", "bearish_engulfing_shape",
    "inside_bar", "outside_bar",
    "three_rising_bodies", "three_falling_bodies",
)


def _origin(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Origin must be an ISO UTC timestamp") from exc
    if (dt.tzinfo is None or dt.utcoffset() != timedelta(0)
            or dt.minute or dt.second or dt.microsecond):
        raise ValueError("Origin must be on a complete UTC hour")
    return dt


def _num(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Invalid provider numeric value")
    return float(value)


def decode_hourly_asof(raw: bytes, origin: str, *, lookback: int = 25) -> list[dict]:
    """Coinbase source is [epoch_seconds, low, high, open, close, volume].

    Filter by timestamp BEFORE accessing price fields. Candles starting at
    origin or later are excluded, even if physically present in the source.
    """
    t0 = _origin(origin)
    if type(lookback) is not int or not 3 <= lookback <= 25:
        raise ValueError("Unsupported bounded historical lookback")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RAW_BYTES:
        raise ValueError("Unbounded or empty source")
    try:
        source = json.loads(raw)
    except ValueError as exc:
        raise ValueError("Invalid Coinbase JSON") from exc
    if not isinstance(source, list) or len(source) > 300:
        raise ValueError("Unexpected price source format")
    start = t0 - lookback * HOUR
    candles = {}
    for item in source:
        if not isinstance(item, list) or len(item) != 6 or type(item[0]) is not int:
            raise ValueError("Malformed Coinbase OHLCV record")
        try:
            t = datetime.fromtimestamp(item[0], timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError("Invalid candle time") from exc
        if t < start or t >= t0:
            continue
        if t.minute or t.second or t.microsecond or t + HOUR > t0:
            raise ValueError("Incomplete candle")
        low, high, opn, close, volume = map(_num, item[1:])
        if not (0 < low <= min(opn, close) <= max(opn, close) <= high
                and volume >= 0):
            raise ValueError("Impossible historical OHLCV")
        if t in candles:
            raise ValueError("Duplicate hourly candle")
        candles[t] = {"t": t.isoformat(), "open": opn, "high": high,
                      "low": low, "close": close, "volume": volume}
    required = [start + i * HOUR for i in range(lookback)]
    if sorted(candles) != required:
        raise ValueError("Missing or gapped completed historical candles")
    return [candles[t] for t in required]


def _shape(c: dict) -> tuple[float, float, float, float]:
    spread = c["high"] - c["low"]
    body = abs(c["close"] - c["open"])
    upper = c["high"] - max(c["open"], c["close"])
    lower = min(c["open"], c["close"]) - c["low"]
    return spread, body, upper, lower


def patterns_from_closed_candles(candles: list[dict]) -> dict:
    """Simple candle-shape flags only; not chart geometry, breakouts, or trades."""
    if len(candles) < 3:
        raise ValueError("At least three previously closed candles required")
    c, p = candles[-1], candles[-2]
    spread, body, upper, lower = _shape(c)
    min_body = max(body, spread * 0.05)
    have_range = spread > 0.0
    rising = c["close"] > c["open"]
    falling = c["close"] < c["open"]
    rising3 = all(x["close"] > x["open"] for x in candles[-3:])
    falling3 = all(x["close"] < x["open"] for x in candles[-3:])
    flags = {
        "doji_shape": have_range and body <= spread * 0.1,
        "hammer_shape": have_range and lower >= 2 * min_body
            and lower >= spread * 0.55 and upper <= spread * 0.15,
        "shooting_star_shape": have_range and upper >= 2 * min_body
            and upper >= spread * 0.55 and lower <= spread * 0.15,
        "bullish_engulfing_shape": (rising and p["close"] < p["open"]
            and c["open"] <= p["close"] and c["close"] >= p["open"]
            and (c["open"] < p["close"] or c["close"] > p["open"])),
        "bearish_engulfing_shape": (falling and p["close"] > p["open"]
            and c["open"] >= p["close"] and c["close"] <= p["open"]
            and (c["open"] > p["close"] or c["close"] < p["open"])),
        "inside_bar": (c["high"] <= p["high"] and c["low"] >= p["low"]
            and (c["high"] < p["high"] or c["low"] > p["low"])),
        "outside_bar": (c["high"] >= p["high"] and c["low"] <= p["low"]
            and (c["high"] > p["high"] or c["low"] < p["low"])),
        "three_rising_bodies": (rising3 and
            all(candles[i]["close"] > candles[i-1]["close"]
                for i in (-2, -1))),
        "three_falling_bodies": (falling3 and
            all(candles[i]["close"] < candles[i-1]["close"]
                for i in (-2, -1))),
    }
    assert set(flags) == set(PATTERN_NAMES)
    return {
        "flags": flags,
        "observed_shapes": [k for k in PATTERN_NAMES if flags[k]],
        "latest_body_fraction": body / spread if have_range else None,
        "latest_upper_wick_fraction": upper / spread if have_range else None,
        "latest_lower_wick_fraction": lower / spread if have_range else None,
        "last_closed_bar_open_utc": c["t"],
        "no_pattern_probability_or_direction_assumed": True,
    }


def _read_raw(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_RAW_BYTES:
        raise ValueError("Bounded local non-symlink source file required")
    raw = path.read_bytes()
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError("File changed size during reading")
    return raw


def analyze_derived_day(derived: Path, btc: Path, eth: Path) -> dict:
    """Join against the official derived SHA-256 of each archived Coinbase page.

    Four as-of feature rows, never the future outcome labels. No network IO.
    """
    features, derived_sha = read_local(derived)
    manifest = json.loads(_read_raw(derived))
    pair_paths = {"BTC-EUR": btc, "ETH-EUR": eth}
    original = {}
    for pair in PAIRS:
        raw = _read_raw(pair_paths[pair])
        digest = hashlib.sha256(raw).hexdigest()
        if digest != manifest["raw_price_pages"][pair]["sha256"]:
            raise ValueError("Coinbase source raw SHA256 mismatch: " + pair)
        original[pair] = {"raw": raw, "sha256": digest}
    rows = []
    for observation in features:
        pair, origin = observation["pair"], observation["origin"]
        bars = decode_hourly_asof(original[pair]["raw"], origin)
        rows.append({
            "pair": pair, "origin": origin,
            "price_features": observation["price_features"],
            "news_features": observation["news_features"],
            "candle_patterns": patterns_from_closed_candles(bars),
            "geometric_patterns": geometric_candidates(bars),
        })
    return {
        "schema": SCHEMA,
        "mode": "OFFLINE_RESEARCH_ONLY_NO_TRADE",
        "derived_sha256": derived_sha,
        "raw_coinbase_sha256": {k: original[k]["sha256"] for k in PAIRS},
        "no_future_labels_exposed": True,
        "historical_only": True,
        "timeframe": "1h",
        "lookback_fully_closed_candles": 25,
        "geometric_pattern_candidates_implemented": True,
        "geometric_patterns_are_only_descriptive": True,
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Research-only as-of candle pattern features")
    ap.add_argument("--derived", required=True, type=Path)
    ap.add_argument("--btc", required=True, type=Path)
    ap.add_argument("--eth", required=True, type=Path)
    args = ap.parse_args()
    print(json.dumps(analyze_derived_day(args.derived, args.btc, args.eth),
                     sort_keys=True, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    main()

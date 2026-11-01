"""Read-only offline bridge from FabioQuant derived day to Grok Trading Desk.

No network, no xAI calls, no execution, no exchange or broker API.
The input format is FabioQuant-GDELT-PriceNews-PIT-Derived-v1, produced by
FabioQuant's validated pipeline. This bridge validates its *claims*, but does
not re-hash original GDELT/price data and cannot independently attest provenance.
Future outcome labels are deliberately never returned to agent roles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SOURCE_SCHEMA = "FabioQuant-GDELT-PriceNews-PIT-Derived-v1"
BRIDGE_SCHEMA = "GrokDesk-FabioQuant-Offline-PIT-v1"
PAIRS = ("BTC-EUR", "ETH-EUR")
MAX_INPUT_BYTES = 180_000


def _utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("UTC timestamp string required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Bad UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must be UTC")
    return parsed


def _finite_features(values: object, width: int, name: str) -> list[float]:
    if not isinstance(values, list) or len(values) != width:
        raise ValueError(f"{name} must contain {width} values")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise ValueError(f"{name} contains invalid or nonfinite values")
    return [float(x) for x in values]


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_derived(obj: object) -> list[dict]:
    """Validate exact daily research structure. Do NOT attest the raw sources."""
    if not isinstance(obj, dict) or obj.get("schema") != SOURCE_SCHEMA:
        raise ValueError("Unknown FabioQuant derived schema")
    try:
        day = date.fromisoformat(obj["day"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid source day") from exc
    if (obj.get("source_day_complete") is not True
            or obj.get("all_46_original_zips_sha256_readback") is not True
            or obj.get("news_timestamp_is_proxy_not_first_publication") is not True
            or obj.get("model_fitted") is not False
            or obj.get("retrospective_only") is not True):
        raise ValueError("Incomplete or misleading source provenance flags")
    sources = obj.get("gkg_originals")
    if not isinstance(sources, list) or len(sources) != 46:
        raise ValueError("46 archived GKG sources required")
    if len({s.get("name") for s in sources if isinstance(s, dict)}) != 46:
        raise ValueError("Missing or repeated source names")
    for source in sources:
        if (not isinstance(source, dict) or not _sha(source.get("sha256"))
                or type(source.get("bytes")) is not int or source["bytes"] <= 0):
            raise ValueError("Invalid GKG source manifest entry")
    prices = obj.get("raw_price_pages")
    if not isinstance(prices, dict) or set(prices) != set(PAIRS):
        raise ValueError("Both Coinbase markets are required")
    for pair in PAIRS:
        item = prices[pair]
        if (not isinstance(item, dict) or not _sha(item.get("sha256"))
                or item.get("verified_full_hourly_bars") != 37):
            raise ValueError("Incomplete price source metadata")
    rows = obj.get("rows")
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("Expected two historical origins for two assets")
    by_key = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("pair") not in PAIRS:
            raise ValueError("Unexpected market row")
        origin = _utc(row.get("origin"))
        if origin.date() != day or origin.hour not in (12, 18) or any(
            (origin.minute, origin.second, origin.microsecond)
        ):
            raise ValueError("Unexpected or non-hourly origin")
        if (row.get("source_proxy_not_proven_original_publication") is not True
                or type(row.get("eligible_batches")) is not int
                or row["eligible_batches"] != 23):
            raise ValueError("Incorrect news availability declaration")
        # The future outcome is inspected for structural consistency only.
        # It NEVER enters agent inputs, logs or summaries.
        if type(row.get("label")) is not int or row["label"] not in (0, 1):
            raise ValueError("Missing outcome metadata")
        price = _finite_features(row.get("price"), 4, "price")
        news = _finite_features(row.get("news"), 2, "news")
        if news[0] < 0:
            raise ValueError("News count feature cannot be negative")
        key = (origin.isoformat(), row["pair"])
        if key in by_key:
            raise ValueError("Duplicate origin/asset")
        by_key[key] = {
            "origin": origin.isoformat(),
            "pair": row["pair"],
            "price_features": {
                "logret_1h": price[0],
                "logret_6h": price[1],
                "realized_volatility_24h": price[2],
                "log_volume_ratio_6h_to_24h": price[3],
            },
            "news_features": {
                "log1p_deduplicated_doc_count_6h": news[0],
                "mean_generic_gkg_tone_6h": news[1],
            },
        }
    required = {
        (datetime(day.year, day.month, day.day, h, tzinfo=timezone.utc).isoformat(), pair)
        for h in (12, 18) for pair in PAIRS
    }
    if set(by_key) != required:
        raise ValueError("Missing required market/origin pair")
    return [by_key[k] for k in sorted(by_key)]


def run_offline_desk(features: dict) -> dict:
    """Deterministic role audit, NOT an AI prediction or trading decision."""
    price, news = features["price_features"], features["news_features"]
    return {
        "origin": features["origin"],
        "pair": features["pair"],
        "scout": {"realized_volatility_24h": price["realized_volatility_24h"],
                  "log_volume_ratio_6h_to_24h": price["log_volume_ratio_6h_to_24h"]},
        "charts": {"logret_1h": price["logret_1h"], "logret_6h": price["logret_6h"]},
        "news": {"log1p_deduplicated_doc_count_6h":
                 news["log1p_deduplicated_doc_count_6h"]},
        "sentiment": {"generic_gkg_tone_6h": news["mean_generic_gkg_tone_6h"],
                      "investor_sentiment_validated": False},
        "skeptic": {"status": "NOT_VALIDATED",
                    "warning": "30-minute GKG availability proxy is not proven first publication"},
        "chief": {"decision": "NO_TRADE",
                  "reason": "No fitted, calibrated or independently evaluated strategy"},
    }


def read_local(path: Path) -> tuple[list[dict], str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Input must be a local, non-symlink file")
    if not (0 < path.stat().st_size <= MAX_INPUT_BYTES):
        raise ValueError("Local derived report exceeds strict size bound")
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Input grew while reading")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid JSON") from exc
    return validate_derived(obj), hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline historical feature audit: no AI API calls")
    parser.add_argument("--input", required=True, type=Path,
                        help="Local FabioQuant _derived/research_rows_verified.json")
    args = parser.parse_args()
    features, digest = read_local(args.input)
    result = {
        "schema": BRIDGE_SCHEMA,
        "mode": "OFFLINE_RESEARCH_ONLY",
        "source_derived_sha256": digest,
        "source_manifest_validation": "STRUCTURAL_ONLY_NOT_INDEPENDENT_RAW_ATTESTATION",
        "source_news_first_publication_proven": False,
        "outcome_labels_exposed_to_agents": False,
        "rows": [run_offline_desk(row) for row in features],
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    main()

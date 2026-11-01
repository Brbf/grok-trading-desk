"""Synthetic only: verifies pattern definitions and no future data leakage."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.fabioquant_offline import SOURCE_SCHEMA
from agents.pattern_features import (
    analyze_derived_day, decode_hourly_asof, patterns_from_closed_candles,
)

UTC = timezone.utc
DAY = datetime(2024, 7, 10, tzinfo=UTC)
START = DAY - timedelta(hours=13)
HOUR = timedelta(hours=1)


def price_page():
    arr = []
    for i in range(37):
        t = START + i * HOUR
        o, c, lo, hi = 100.0, 101.0, 99.0, 102.0
        if t == DAY + timedelta(hours=10):
            o, c, lo, hi = 105.0, 104.0, 103.0, 106.0
        if t == DAY + timedelta(hours=11):
            o, c, lo, hi = 103.0, 106.0, 102.0, 107.0
        arr.append([int(t.timestamp()), lo, hi, o, c, 12.0])
    return arr


def derived(btc_bytes, eth_bytes):
    return {
        "schema": SOURCE_SCHEMA,
        "day": "2024-07-10",
        "source_archive": "synthetic-test-fixture",
        "source_day_complete": True,
        "all_46_original_zips_sha256_readback": True,
        "news_timestamp_is_proxy_not_first_publication": True,
        "model_fitted": False,
        "retrospective_only": True,
        "gkg_originals": [
            {"name": f"synthetic-{i:02d}.zip", "sha256": "a"*64, "bytes": 10}
            for i in range(46)],
        "raw_price_pages": {
            "BTC-EUR": {"sha256": hashlib.sha256(btc_bytes).hexdigest(),
                        "verified_full_hourly_bars": 37},
            "ETH-EUR": {"sha256": hashlib.sha256(eth_bytes).hexdigest(),
                        "verified_full_hourly_bars": 37},
        },
        "rows": [
            {"origin": f"2024-07-10T{hour:02d}:00:00+00:00", "pair": pair,
             "price": [0.1, 0.2, 0.3, 0.4], "news": [1.0, -0.2],
             "label": 1,
             "source_proxy_not_proven_original_publication": True,
             "eligible_batches": 23}
            for hour in (12, 18) for pair in ("BTC-EUR", "ETH-EUR")
        ],
    }


class PatternTests(unittest.TestCase):
    def test_engulfing_shape_from_completed_price_candles(self):
        raw = json.dumps(price_page()).encode()
        candles = decode_hourly_asof(raw, "2024-07-10T12:00:00+00:00")
        result = patterns_from_closed_candles(candles)
        self.assertEqual(len(candles), 25)
        self.assertEqual(result["last_closed_bar_open_utc"],
                         "2024-07-10T11:00:00+00:00")
        self.assertTrue(result["flags"]["bullish_engulfing_shape"])

    def test_future_price_changes_do_not_change_causal_features(self):
        original = price_page()
        modified = price_page()
        for item in modified:
            if item[0] >= int((DAY + timedelta(hours=12)).timestamp()):
                item[1:] = [1, 999999, 2, 55555, 1000]
        a = decode_hourly_asof(json.dumps(original).encode(),
                              "2024-07-10T12:00:00Z")
        b = decode_hourly_asof(json.dumps(modified).encode(),
                              "2024-07-10T12:00:00Z")
        self.assertEqual(patterns_from_closed_candles(a),
                         patterns_from_closed_candles(b))

    def test_gapped_completed_history_rejected(self):
        source = [x for x in price_page()
                  if x[0] != int((DAY + timedelta(hours=9)).timestamp())]
        with self.assertRaisesRegex(ValueError, "gapped"):
            decode_hourly_asof(json.dumps(source).encode(),
                               "2024-07-10T12:00:00Z")

    def test_duplicate_history_rejected(self):
        source = price_page()
        source.append(source[24])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            decode_hourly_asof(json.dumps(source).encode(),
                               "2024-07-10T12:00:00Z")

    def test_future_only_history_rejected(self):
        source = [x for x in price_page()
                  if x[0] >= int((DAY + timedelta(hours=12)).timestamp())]
        with self.assertRaises(ValueError):
            decode_hourly_asof(json.dumps(source).encode(),
                               "2024-07-10T12:00:00Z")

    def test_invalid_ohlcv_rejected(self):
        source = price_page()
        source[24][1] = 300.0
        with self.assertRaisesRegex(ValueError, "Impossible"):
            decode_hourly_asof(json.dumps(source).encode(),
                               "2024-07-10T12:00:00Z")

    def test_intra_hour_origin_rejected(self):
        with self.assertRaisesRegex(ValueError, "complete UTC hour"):
            decode_hourly_asof(json.dumps(price_page()).encode(),
                               "2024-07-10T12:25:00Z")

    def test_range_shapes_are_not_directional_predictions(self):
        source = price_page()
        source[24] = [source[24][0], 97.0, 101.5, 101.0, 100.9, 15]
        candles = decode_hourly_asof(json.dumps(source).encode(),
                                     "2024-07-10T12:00:00Z")
        result = patterns_from_closed_candles(candles)
        self.assertTrue(result["flags"]["hammer_shape"])
        self.assertTrue(result["no_pattern_probability_or_direction_assumed"])
        self.assertNotIn("signal", result)

    def test_end_to_end_four_observations_with_news_and_without_labels(self):
        raw = json.dumps(price_page()).encode()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "btc.json").write_bytes(raw)
            (root / "eth.json").write_bytes(raw)
            (root / "derived.json").write_text(json.dumps(derived(raw, raw)))
            result = analyze_derived_day(root / "derived.json",
                                         root / "btc.json", root / "eth.json")
            self.assertEqual(len(result["rows"]), 4)
            for row in result["rows"]:
                self.assertIn("price_features", row)
                self.assertIn("news_features", row)
                self.assertIn("candle_patterns", row)
                self.assertIn("geometric_patterns", row)
                self.assertTrue(row["geometric_patterns"]["descriptive_not_directional"])
            self.assertNotIn('"label"', json.dumps(result))
            self.assertTrue(result["no_future_labels_exposed"])
            self.assertTrue(result["geometric_pattern_candidates_implemented"])
            self.assertTrue(result["geometric_patterns_are_only_descriptive"])

    def test_cross_source_hash_mismatch_is_rejected(self):
        raw = json.dumps(price_page()).encode()
        wrong = json.dumps(price_page(), separators=(",", ":")).encode()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "btc.json").write_bytes(wrong)
            (root / "eth.json").write_bytes(raw)
            (root / "derived.json").write_text(json.dumps(derived(raw, raw)))
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                analyze_derived_day(root / "derived.json",
                                    root / "btc.json", root / "eth.json")


if __name__ == "__main__":
    unittest.main()

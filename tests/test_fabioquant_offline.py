"""Synthetic contract tests. No real market data or API keys required."""
import json
import tempfile
import unittest
from pathlib import Path

from agents.fabioquant_offline import (
    BRIDGE_SCHEMA, SOURCE_SCHEMA, read_local, run_offline_desk, validate_derived,
)


def fixture():
    rows = []
    for hour in (12, 18):
        for pair in ("BTC-EUR", "ETH-EUR"):
            rows.append({
                "origin": f"2024-07-10T{hour:02}:00:00+00:00",
                "pair": pair,
                "price": [0.001, 0.002, 0.003, 0.004],
                "news": [2.4, -0.5],
                "label": 1,
                "source_proxy_not_proven_original_publication": True,
                "eligible_batches": 23,
            })
    return {
        "schema": SOURCE_SCHEMA,
        "day": "2024-07-10",
        "source_archive": "synthetic-only",
        "source_day_complete": True,
        "all_46_original_zips_sha256_readback": True,
        "news_timestamp_is_proxy_not_first_publication": True,
        "model_fitted": False,
        "retrospective_only": True,
        "gkg_originals": [
            {"name": f"SYNTHETIC-{i:02d}.zip", "sha256": "a" * 64, "bytes": 10}
            for i in range(46)
        ],
        "raw_price_pages": {
            pair: {"sha256": "b" * 64, "verified_full_hourly_bars": 37}
            for pair in ("BTC-EUR", "ETH-EUR")
        },
        "rows": rows,
    }


class OfflineAdapterTests(unittest.TestCase):
    def test_four_valid_observations_without_future_label(self):
        rows = validate_derived(fixture())
        self.assertEqual(len(rows), 4)
        self.assertEqual({x["pair"] for x in rows}, {"BTC-EUR", "ETH-EUR"})
        for row in rows:
            report = run_offline_desk(row)
            self.assertEqual(report["chief"]["decision"], "NO_TRADE")
            self.assertFalse(report["sentiment"]["investor_sentiment_validated"])
            self.assertNotIn("label", json.dumps(report))

    def test_missing_archived_source_fails_closed(self):
        x = fixture()
        x["gkg_originals"].pop()
        with self.assertRaises(ValueError):
            validate_derived(x)

    def test_future_origin_fails_closed(self):
        x = fixture()
        x["rows"][0]["origin"] = "2024-07-11T12:00:00+00:00"
        with self.assertRaises(ValueError):
            validate_derived(x)

    def test_duplicate_asset_origin_fails_closed(self):
        x = fixture()
        x["rows"][1] = dict(x["rows"][0])
        with self.assertRaises(ValueError):
            validate_derived(x)

    def test_nonfinite_price_fails_closed(self):
        x = fixture()
        x["rows"][0]["price"][2] = float("nan")
        with self.assertRaises(ValueError):
            validate_derived(x)

    def test_negative_news_count_fails_closed(self):
        x = fixture()
        x["rows"][0]["news"][0] = -1.0
        with self.assertRaises(ValueError):
            validate_derived(x)

    def test_untested_first_publication_flag_fails_closed(self):
        x = fixture()
        x["news_timestamp_is_proxy_not_first_publication"] = False
        with self.assertRaises(ValueError):
            validate_derived(x)

    def test_local_file_read_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "derived.json"
            p.write_text(json.dumps(fixture()), encoding="utf-8")
            rows, fingerprint = read_local(p)
            self.assertEqual(len(rows), 4)
            self.assertEqual(len(fingerprint), 64)

    def test_symlink_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "derived.json"
            p.write_text(json.dumps(fixture()), encoding="utf-8")
            link = Path(td) / "alias.json"
            link.symlink_to(p)
            with self.assertRaises(ValueError):
                read_local(link)


if __name__ == "__main__":
    unittest.main()

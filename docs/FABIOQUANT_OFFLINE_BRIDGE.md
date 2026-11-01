# Grok Trading Desk + FabioQuant Data & News — offline bridge v0.1

**Scope:** read-only BTC-EUR / ETH-EUR historical data audit, no broker, no orders,
no live feeds, no AI API calls, no inferred trading advantage. The existing
Grok agent pipeline remains unchanged. The private FabioQuant repository and
its archived sources remain untouched.

## Verified upstream structure

Input is exactly the local, derived JSON exported from FabioQuant:
`fabioquant/gdelt_price_news_pipeline.py`, branch
`research/gdelt-price-news-pipeline-2026-10-31`, file
`_derived/research_rows_verified.json` (schema
`FabioQuant-GDELT-PriceNews-PIT-Derived-v1`).

The upstream generator creates four observations per day (BTC-EUR / ETH-EUR
at 12:00 and 18:00 UTC) from hourly Coinbase price bars and GDELT GKG
snapshots. The six-hour forecast outcome is retrospective and **must never be
shown to the decision-making agents**. The news timestamp is a 30-minute
source-availability proxy, **not authenticated first publication**.

**Do not copy the private FabioQuant source, original market data, GDELT ZIPs,
Google Drive manifest, `.env`, tokens or derived exports into this public
repository.** Store the derived input locally outside the clone.

## Local usage

Python 3.10+; uses the standard library only. No `pip install` or xAI key
needed.

```bash
python3 -m unittest discover -s tests -p 'test_fabioquant_offline.py' -v
python3 -m agents.fabioquant_offline \
  --input "/path/to/local/research_rows_verified.json"
```

The second command succeeds only when that local derived JSON exists and
passes the bounded checks. It emits JSON to stdout, **not to GitHub**.
Do not pipe the output into a Git-tracked file.

Output includes the six Grok-role names:
- Scout / Charts — already-computed historical price features;
- News / Sentiment — GDELT count and generic tone (NOT investor sentiment);
- Skeptic — provenance limitations;
- Chief — fixed `NO_TRADE` because no strategy is statistically validated.

These are deterministic role **diagnostics**, not Grok model responses.
No external API calls and no financial position simulation are performed.
The original `main.py` still uses mock strings and is intentionally unchanged.

## Data integrity and limitations

- Requires 46 unique GKG source manifest entries, both Coinbase price
  descriptors with 37 hourly bars, fixed 12:00/18:00 UTC origins, and four
  aligned historical research rows (23 eligible GKG batches at each origin).
- Rejects duplicate pairs, bad timestamps, non-finite features and missing
  point-in-time metadata. Rejects oversized input and symlink input.
- Computes the SHA-256 of the **derived input file** for local reproducibility.
- **Structural checks are NOT independent raw-archive verification.** The
  adapter cannot certify the original GDELT ZIPs, Coinbase history, provider
  billing, publication timestamps or historical data coverage. Those are
  upstream audit responsibilities.
- The importer discards each row's future `label` after validating its
  shape: it cannot leak future outcomes into the agent features.
- Four rows from a single day cannot demonstrate profitable trading,
  forecast skill, cost-adjusted performance or causal impact of news.
- FabioQuant's locked 84-day chronological train/calibration/test protocol
  remains independent and unmodified. Its incomplete-coverage gate stays
  in force. This adapter does not train or score the protected study.
- No raw data, derived data, keys or credentials are part of the commits.
- Synthetic tests are **not** a real-data integration run.

## Next gated milestone

Once a derived day has been **locally exported and independently checked**
from FabioQuant's existing archive, run the offline adapter with that local
file. Compare the output to the upstream feature record without exposing
future labels. Add reproducible source-provenance checks for the local
export before broadening coverage. Only with a complete, immutable
chronological study should a price-only vs price-plus-news comparison
be attempted (Brier/log-loss, uncertainty, costs and negative results).
No real-money or live trading features are in scope.

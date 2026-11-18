"""Offline research universe.

This is the set we can actually download for free. It is not a cap on the MT5
scanner, which discovers every symbol on the demo account. Spot FX is included
even though Yahoo hourly volume is zero: the quality gate is expected to reject
those series instead of inventing volume. EURUSD is also the EUR conversion pair.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FX_MAJORS = ["EURUSD", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"]
FX_JPY = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"]
FX_CROSSES = [
    "EURGBP", "EURCHF", "EURAUD", "EURCAD", "EURNZD", "GBPCHF", "GBPAUD", "GBPCAD",
    "GBPNZD", "AUDCAD", "AUDCHF", "AUDNZD", "NZDCAD", "NZDCHF", "CADCHF",
]
FX_EXOTICS = [
    "USDSEK", "USDNOK", "USDDKK", "USDZAR", "USDMXN", "USDPLN", "USDHUF", "USDSGD",
    "USDTRY", "USDHKD", "USDCNH", "EURSEK", "EURNOK", "EURPLN", "EURTRY", "GBPZAR",
]

# Suffix _F so CME futures do not clobber S&P 500 cash names (ES, CL).
FUTURES = [
    ("ES_F", "ES=F", "index_us"),
    ("NQ_F", "NQ=F", "index_us"),
    ("YM_F", "YM=F", "index_us"),
    ("RTY_F", "RTY=F", "index_us"),
    ("GC_F", "GC=F", "metal"),
    ("SI_F", "SI=F", "metal"),
    ("HG_F", "HG=F", "metal"),
    ("CL_F", "CL=F", "energy"),
    ("BZ_F", "BZ=F", "energy"),
    ("NG_F", "NG=F", "energy"),
    ("HO_F", "HO=F", "energy"),
    ("RB_F", "RB=F", "energy"),
]

INDICES = [
    ("US500", "^GSPC", "index_us"),
    ("US30", "^DJI", "index_us"),
    ("NAS100", "^NDX", "index_us"),
    ("US2000", "^RUT", "index_us"),
    ("GER40", "^GDAXI", "index_eu"),
    ("EU50", "^STOXX50E", "index_eu"),
    ("FRA40", "^FCHI", "index_eu"),
    ("UK100", "^FTSE", "index_eu"),
    ("JP225", "^N225", "index_asia"),
    ("HK50", "^HSI", "index_asia"),
    ("AUS200", "^AXJO", "index_asia"),
]

CRYPTO = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "LTC-USD",
    "BCH-USD", "LINK-USD", "AVAX-USD", "DOT-USD", "UNI-USD", "ATOM-USD", "XLM-USD",
    "ETC-USD", "BNB-USD", "TRX-USD", "NEAR-USD", "APT-USD", "AAVE-USD", "ALGO-USD",
]

EU_STOCKS = [
    "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "BAS.DE", "BAYN.DE", "BMW.DE", "MBG.DE",
    "AIR.PA", "MC.PA", "OR.PA", "SAN.PA", "TTE.PA", "AI.PA", "SU.PA",
    "ASML.AS", "PHIA.AS", "INGA.AS", "AD.AS",
]


def _fx(symbol: str, asset_class: str) -> dict:
    return {
        "symbol": symbol,
        "yahoo": f"{symbol}=X",
        "asset_class": asset_class,
        "quote": symbol[3:],
        "base": symbol[:3],
        "contract_size": 1.0,
        "volume_min": 1000.0,
        "volume_step": 1000.0,
        "fx_pair": True,
    }


def _cfd(symbol: str, yahoo: str, asset_class: str, quote: str = "USD") -> dict:
    return {
        "symbol": symbol,
        "yahoo": yahoo,
        "asset_class": asset_class,
        "quote": quote,
        "base": symbol,
        "contract_size": 1.0,
        "volume_min": 0.01,
        "volume_step": 0.01,
        "fx_pair": False,
    }


def sp500(path: Path | None = None) -> list[dict]:
    csv_path = path or (ROOT / "data" / "sp500.csv")
    rows = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            symbol = record["Symbol"].strip()
            if not symbol:
                continue
            rows.append(_cfd(symbol, symbol.replace(".", "-"), "stock_us", "USD"))
    return rows


def offline_instruments(root: Path | None = None) -> list[dict]:
    root = root or ROOT
    items: list[dict] = []
    for symbol in FX_MAJORS:
        items.append(_fx(symbol, "fx_major"))
    for symbol in FX_JPY:
        items.append(_fx(symbol, "fx_jpy"))
    for symbol in FX_CROSSES:
        items.append(_fx(symbol, "fx_cross"))
    for symbol in FX_EXOTICS:
        items.append(_fx(symbol, "fx_exotic"))
    for symbol, yahoo, asset in FUTURES:
        items.append(_cfd(symbol, yahoo, asset))
    for symbol, yahoo, asset in INDICES:
        quote = "EUR" if symbol in {"GER40", "EU50", "FRA40"} else "USD"
        if symbol == "UK100":
            quote = "GBP"
        if symbol in {"JP225"}:
            quote = "JPY"
        if symbol == "HK50":
            quote = "HKD"
        if symbol == "AUS200":
            quote = "AUD"
        items.append(_cfd(symbol, yahoo, asset, quote))
    for symbol in CRYPTO:
        items.append(_cfd(symbol, symbol, "crypto", "USD"))
    for symbol in EU_STOCKS:
        items.append(_cfd(symbol, symbol, "stock_eu", "EUR"))
    items.extend(sp500(root / "data" / "sp500.csv"))
    # De-duplicate by yahoo id, first definition wins.
    seen = set()
    unique = []
    for item in items:
        if item["yahoo"] in seen:
            continue
        seen.add(item["yahoo"])
        unique.append(item)
    return unique

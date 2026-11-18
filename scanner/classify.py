"""Map an MT5 symbol name and path to an asset class. Unknown stays unknown (no trade)."""

from __future__ import annotations

CRYPTO_BASES = {
    "BTC", "ETH", "LTC", "XRP", "BCH", "SOL", "ADA", "DOGE", "DOT", "LINK",
    "AVAX", "UNI", "ATOM", "XLM", "BNB", "TRX", "ETC", "XMR", "EOS", "FIL",
    "APT", "ARB", "OP", "NEAR", "ALGO", "AAVE", "SHIB", "TON", "PEPE",
}

CURRENCIES = {
    "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "SEK", "NOK",
    "DKK", "ZAR", "MXN", "PLN", "HUF", "SGD", "TRY", "HKD", "CNH", "CZK",
    "RON", "ILS", "THB", "INR", "NGN", "CNY",
}

EXOTIC = {
    "TRY", "ZAR", "MXN", "PLN", "HUF", "NOK", "SEK", "DKK", "CNH", "CNY",
    "SGD", "THB", "CZK", "RON", "ILS", "INR", "NGN", "HKD",
}

MAJORS = {"EURUSD", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"}

METALS = {"XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "GOLD", "SILVER"}

ENERGIES = {
    "XTIUSD", "XBRUSD", "USOIL", "UKOIL", "WTI", "BRENT", "XNGUSD", "NATGAS",
    "USOIL.CASH", "UKOIL.CASH",
}

INDEX_US = {
    "US500", "SPX500", "SPX", "US30", "US100", "NAS100", "USTEC", "US2000",
    "NDX", "DJI", "USA500", "USA30", "USA100", "SP500", "NASDAQ", "DOW",
}
INDEX_EU = {
    "GER40", "DE40", "DAX40", "DAX", "FRA40", "FCHI40", "UK100", "FTSE",
    "EU50", "STOXX50", "EUSTX50", "ESP35", "SPA35", "NED25", "IT40", "SUI20",
    "EUSTX", "DE30", "FR40",
}
INDEX_ASIA = {
    "JP225", "JPN225", "NI225", "NIKKEI", "HK50", "HSI", "AUS200", "AU200",
    "CHINA50", "CN50", "CHINAH", "SG30",
}

def _stem(name: str) -> str:
    token = name.upper().strip()
    token = token.split("+")[0]
    token = token.split(".")[0]
    return token.replace("#", "")


def _parts(path: str) -> list[str]:
    return [p for p in path.replace("/", "\\").upper().split("\\") if p]


def _crypto_name(name: str) -> bool:
    if name in CRYPTO_BASES:
        return True
    for quote in ("USDT", "USD", "EUR"):
        if name.endswith(quote) and name[: -len(quote)] in CRYPTO_BASES:
            return True
    return False


def _fx_class(name: str) -> str | None:
    if len(name) != 6:
        return None
    base, quote = name[:3], name[3:]
    if base not in CURRENCIES or quote not in CURRENCIES:
        return None
    if "JPY" in (base, quote):
        return "fx_jpy"
    if name in MAJORS:
        return "fx_major"
    if base in EXOTIC or quote in EXOTIC:
        return "fx_exotic"
    return "fx_cross"


def _index_class(name: str, parts: list[str]) -> str | None:
    if name in INDEX_US:
        return "index_us"
    if name in INDEX_EU:
        return "index_eu"
    if name in INDEX_ASIA:
        return "index_asia"
    blob = " ".join(parts)
    if any(token in blob for token in (" US", "USA", "NYSE", "NASDAQ", "DOW", "S&P")):
        return "index_us"
    if any(token in blob for token in ("EUROPE", "GERMANY", "DAX", "FRANCE", "LONDON", "UK")):
        return "index_eu"
    if any(token in blob for token in ("JAPAN", "HONG", "ASIA", "AUSTRALIA", "CHINA")):
        return "index_asia"
    return None


def _stock_region(parts: list[str]) -> str:
    blob = " ".join(parts)
    if any(token in blob for token in ("JAPAN", "TOKYO", "HONG", "ASIA", "AUSTRALIA", "SINGAPORE", "CHINA")):
        return "stock_asia"
    if any(token in blob for token in ("EUROPE", "GERMANY", "XETRA", "FRANCE", "PARIS", "AMSTERDAM", "ITALY", "SPAIN", " LSE", "LONDON")):
        return "stock_eu"
    if any(token in parts for token in ("EU", "DE", "FR", "NL", "IT", "ES", "UK")):
        return "stock_eu"
    if any(token in parts for token in ("JP", "HK", "AU", "SG", "CN")):
        return "stock_asia"
    return "stock_us"


def classify(name: str, path: str = "") -> str:
    stem = _stem(name)
    parts = _parts(path)
    part_set = set(parts)

    if part_set & {"CRYPTO", "CRYPTOCURRENCY"} or _crypto_name(stem):
        return "crypto"
    if part_set & {"METAL", "METALS"} or stem in METALS or stem.startswith(("XAU", "XAG", "XPT", "XPD")):
        return "metal"
    if part_set & {"ENERGY", "ENERGIES", "COMMODITY", "COMMODITIES"} or stem in ENERGIES or stem.startswith(("XTI", "XBR")):
        return "energy"
    if part_set & {"INDEX", "INDICES", "INDEXES"} or stem in INDEX_US | INDEX_EU | INDEX_ASIA:
        found = _index_class(stem, parts)
        if found:
            return found
        return "unknown"
    if part_set & {"STOCK", "STOCKS", "SHARE", "SHARES", "EQUITY", "EQUITIES"}:
        return _stock_region(parts)
    if part_set & {"FOREX", "FX", "CURRENCIES"} or _fx_class(stem):
        fx = _fx_class(stem)
        if fx:
            return fx
        return "unknown"
    return "unknown"

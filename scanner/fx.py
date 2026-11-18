"""Causal conversion into EUR using FX pairs observed so far."""

from __future__ import annotations


class FxBook:
    """USD value of 1 unit of each currency, updated only with prices already known."""

    def __init__(self) -> None:
        self.usd_per: dict[str, float] = {"USD": 1.0}

    def update_pair(self, base: str, quote: str, price: float) -> None:
        if price <= 0 or not base or not quote:
            return
        base = base.upper()
        quote = quote.upper()
        # price = quote currency per 1 base.
        if quote == "USD":
            self.usd_per[base] = price
        elif base == "USD":
            self.usd_per[quote] = 1.0 / price
        else:
            # Cross: only if one leg is already in USD terms.
            if quote in self.usd_per:
                self.usd_per[base] = price * self.usd_per[quote]
            elif base in self.usd_per and self.usd_per[base] > 0:
                self.usd_per[quote] = self.usd_per[base] / price

    def eur_per_unit(self, currency: str) -> float | None:
        currency = (currency or "").upper()
        if currency == "EUR":
            return 1.0
        usd = self.usd_per.get(currency)
        eur = self.usd_per.get("EUR")
        if usd is None or eur is None or eur <= 0:
            return None
        return usd / eur

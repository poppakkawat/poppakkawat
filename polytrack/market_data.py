"""Live quotes for traditional instruments (and crypto), stdlib only.

Used to anchor prediction-market signals against what the underlying asset
is actually doing. Sources, all public/keyless:

- Crypto spot + 24h open: Coinbase
- Equities / ETFs / indices / futures proxies: Yahoo Finance chart endpoint

Network failures degrade gracefully to ``None`` rather than raising — a
missing quote should never sink the whole report.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

# Tickers we price via Coinbase instead of Yahoo.
CRYPTO = {"BTC", "ETH", "SOL", "DOGE", "XRP", "LTC", "ADA"}
UA = "Mozilla/5.0 (compatible; polytrack/0.1)"


@dataclass
class Quote:
    symbol: str
    price: float
    prev: float | None = None  # reference price (prev close / 24h open)

    @property
    def pct_change(self) -> float | None:
        if self.prev and self.prev != 0:
            return (self.price - self.prev) / self.prev * 100.0
        return None


def _get_json(url: str, timeout: int = 12) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _crypto_quote(sym: str) -> Quote | None:
    spot = _get_json(f"https://api.coinbase.com/v2/prices/{sym}-USD/spot")
    if not spot:
        return None
    try:
        price = float(spot["data"]["amount"])
    except (KeyError, ValueError, TypeError):
        return None
    prev = None
    stats = _get_json(f"https://api.exchange.coinbase.com/products/{sym}-USD/stats")
    if stats and stats.get("open"):
        try:
            prev = float(stats["open"])
        except (ValueError, TypeError):
            prev = None
    return Quote(symbol=sym, price=price, prev=prev)


def _yahoo_quote(sym: str) -> Quote | None:
    data = _get_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
        "?range=5d&interval=1d"
    )
    try:
        meta = data["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
        prev = meta.get("chartPreviousClose")
        prev = float(prev) if prev is not None else None
        return Quote(symbol=sym, price=price, prev=prev)
    except (KeyError, TypeError, ValueError, IndexError):
        return None


_cache: dict[str, Quote | None] = {}


def get_quote(symbol: str) -> Quote | None:
    """Return a live Quote for ``symbol`` (cached for the process)."""
    sym = symbol.upper()
    if sym in _cache:
        return _cache[sym]
    q = _crypto_quote(sym) if sym in CRYPTO else _yahoo_quote(sym)
    _cache[sym] = q
    return q


def get_quotes(symbols: list[str]) -> dict[str, Quote | None]:
    return {s: get_quote(s) for s in symbols}

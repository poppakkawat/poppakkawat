"""Client for Polymarket's public data API (no API key required).

Docs: the data API at https://data-api.polymarket.com exposes recent
trades. We use the CASH filter to fetch only economically meaningful
trades and page backwards in time.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

DATA_API = "https://data-api.polymarket.com"
USER_AGENT = "polytrack/0.1 (+https://github.com/poppakkawat/poppakkawat)"


@dataclass
class Trade:
    """A single Polymarket trade, normalized."""

    wallet: str
    trader: str
    side: str
    size: float
    price: float
    timestamp: int
    title: str
    outcome: str
    slug: str
    condition_id: str
    asset: str
    tx_hash: str
    venue: str = "polymarket"
    url: str = ""

    @property
    def usd(self) -> float:
        """Notional value of the trade in USD (shares * price)."""
        return self.size * self.price

    @classmethod
    def from_api(cls, d: dict) -> "Trade":
        return cls(
            wallet=d.get("proxyWallet", ""),
            trader=d.get("name") or d.get("pseudonym") or d.get("proxyWallet", "")[:10],
            side=d.get("side", ""),
            size=float(d.get("size", 0) or 0),
            price=float(d.get("price", 0) or 0),
            timestamp=int(d.get("timestamp", 0) or 0),
            title=d.get("title", "(unknown market)"),
            outcome=d.get("outcome", ""),
            slug=d.get("slug", ""),
            condition_id=d.get("conditionId", ""),
            asset=d.get("asset", ""),
            tx_hash=d.get("transactionHash", ""),
            venue="polymarket",
            url=(f"https://polymarket.com/event/{d.get('slug')}"
                 if d.get("slug") else ""),
        )


def _get(path: str, params: dict, retries: int = 4, timeout: int = 30) -> list:
    """GET a JSON list from the data API, with simple backoff retries."""
    url = f"{DATA_API}{path}?{urllib.parse.urlencode(params)}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # network hiccup, rate limit, etc.
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to GET {url}: {last_err}")


def fetch_large_trades(
    min_usd: float = 5000,
    since_ts: int | None = None,
    max_trades: int = 5000,
    page_size: int = 500,
) -> list[Trade]:
    """Fetch trades >= ``min_usd`` notional, newest first.

    Pages backwards until a trade older than ``since_ts`` is seen, or until
    ``max_trades`` are collected, or the feed is exhausted.
    """
    out: list[Trade] = []
    offset = 0
    while len(out) < max_trades:
        try:
            batch = _get(
                "/trades",
                {
                    "limit": page_size,
                    "offset": offset,
                    "filterType": "CASH",
                    "filterAmount": min_usd,
                    "takerOnly": "false",
                },
            )
        except RuntimeError:
            # Deep pagination can intermittently time out. If we already
            # have data, return it rather than failing the whole run.
            if out:
                break
            raise
        if not batch:
            break
        stop = False
        for raw in batch:
            t = Trade.from_api(raw)
            if since_ts is not None and t.timestamp < since_ts:
                stop = True
                break
            out.append(t)
        if stop or len(batch) < page_size:
            break
        offset += page_size
    return out


def fetch_user_trades(
    address: str,
    since_ts: int | None = None,
    max_trades: int = 1000,
    page_size: int = 500,
) -> list[Trade]:
    """Fetch ALL trades for a single wallet (any size), newest first.

    Used for the smart-money watchlist so we catch a tracked wallet's
    moves even when they're below the global notional threshold.
    """
    out: list[Trade] = []
    offset = 0
    while len(out) < max_trades:
        try:
            batch = _get(
                "/trades",
                {"user": address, "limit": page_size, "offset": offset},
            )
        except RuntimeError:
            if out:
                break
            raise
        if not batch:
            break
        stop = False
        for raw in batch:
            t = Trade.from_api(raw)
            if since_ts is not None and t.timestamp < since_ts:
                stop = True
                break
            out.append(t)
        if stop or len(batch) < page_size:
            break
        offset += page_size
    return out

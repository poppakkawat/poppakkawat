"""Client for Kalshi's public market-data API (no auth required for reads).

Base: https://api.elections.kalshi.com/trade-api/v2

Kalshi trades are anonymous (no wallet/trader identity), prices are in
dollars (0–1), and ``count_fp`` is the number of $1 contracts. We normalize
them into the same :class:`~polytrack.client.Trade` shape used for
Polymarket so the analytics and report code is venue-agnostic.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime

from .client import Trade

KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"
USER_AGENT = "polytrack/0.1 (+https://github.com/poppakkawat/poppakkawat)"


def _get(path: str, params: dict, retries: int = 4, timeout: int = 30) -> dict:
    url = f"{KALSHI_API}{path}?{urllib.parse.urlencode(params)}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to GET {url}: {last_err}")


def _parse_ts(s: str) -> int:
    """ISO-8601 (with trailing Z) -> unix seconds."""
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def _raw_to_trade(d: dict) -> Trade:
    side = d.get("taker_side", "")  # "yes" or "no"
    if side == "no":
        price = float(d.get("no_price_dollars", 0) or 0)
        outcome = "No"
    else:
        price = float(d.get("yes_price_dollars", 0) or 0)
        outcome = "Yes"
    size = float(d.get("count_fp", 0) or 0)
    ticker = d.get("ticker", "")
    return Trade(
        wallet="",  # Kalshi trades are anonymous
        trader="(anonymous)",
        side="BUY",  # the taker is always lifting/hitting to open a side
        size=size,
        price=price,
        timestamp=_parse_ts(d.get("created_time", "")),
        title=ticker,  # replaced with a human title in resolve_titles()
        outcome=outcome,
        slug=ticker,
        condition_id=f"kalshi:{ticker}",
        asset=f"kalshi:{ticker}:{outcome}",
        tx_hash=d.get("trade_id", ""),
        venue="kalshi",
        url="",
    )


def resolve_titles(trades: list[Trade], chunk: int = 20) -> None:
    """Fill in human-readable titles and event URLs in place.

    Looks up market metadata for the distinct tickers present, in batches.
    Failures are non-fatal — the ticker stays as the title.
    """
    tickers = sorted({t.slug for t in trades if t.slug})
    meta: dict[str, dict] = {}
    for i in range(0, len(tickers), chunk):
        batch = tickers[i:i + chunk]
        try:
            data = _get("/markets", {"tickers": ",".join(batch), "limit": chunk})
        except RuntimeError:
            continue
        for m in data.get("markets", []):
            meta[m.get("ticker", "")] = m

    for t in trades:
        m = meta.get(t.slug)
        if not m:
            continue
        title = m.get("title") or t.slug
        sub = m.get("yes_sub_title") or ""
        t.title = f"{title} — {sub}" if sub and sub not in title else title
        event = m.get("event_ticker") or t.slug
        t.url = f"https://kalshi.com/markets/{event}"


def fetch_kalshi_trades(
    min_usd: float = 5000,
    since_ts: int | None = None,
    max_trades: int = 60000,
    page_size: int = 1000,
) -> list[Trade]:
    """Fetch Kalshi trades >= ``min_usd`` notional within the window.

    Kalshi has no server-side cash filter, so we page (newest first, bounded
    by ``min_ts``) and filter client-side, then resolve market titles.

    ``max_trades`` caps how many raw trades we scan. On very high-volume days
    (e.g. World Cup) Kalshi can produce hundreds of thousands of tiny trades;
    scanning all of them is slow, so we cap to the most recent ``max_trades``.
    Large/notable trades are overwhelmingly recent, so this keeps the daily
    job fast and bounded while still catching what matters.
    """
    out: list[Trade] = []
    cursor: str | None = None
    scanned = 0
    while scanned < max_trades:
        params: dict = {"limit": page_size}
        if since_ts is not None:
            params["min_ts"] = since_ts
        if cursor:
            params["cursor"] = cursor
        try:
            data = _get("/markets/trades", params)
        except RuntimeError:
            if out:
                break
            raise
        batch = data.get("trades", [])
        if not batch:
            break
        for raw in batch:
            scanned += 1
            t = _raw_to_trade(raw)
            if t.usd >= min_usd:
                out.append(t)
        cursor = data.get("cursor")
        if not cursor:
            break

    resolve_titles(out)
    return out

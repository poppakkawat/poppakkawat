"""Price history from Yahoo Finance's public chart endpoint (stdlib only)."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

UA = "Mozilla/5.0 (compatible; pixel-floor/0.1)"


@dataclass
class Series:
    symbol: str
    price: float | None = None
    prev_close: float | None = None
    # (unix_ts, open, high, low, close), oldest first, rows with gaps dropped
    bars: list[tuple[int, float, float, float, float]] = field(default_factory=list)


def chart(symbol: str, rng: str, interval: str, retries: int = 2) -> Series:
    """Fetch one symbol. Network or parse failures return an empty Series."""
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(symbol)
        + f"?range={rng}&interval={interval}"
    )
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return _parse(symbol, data)
        except Exception:
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    return Series(symbol)


def _parse(symbol: str, data: dict) -> Series:
    try:
        res = data["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        return Series(symbol)
    meta = res.get("meta") or {}
    s = Series(
        symbol,
        price=_f(meta.get("regularMarketPrice")),
        prev_close=_f(meta.get("chartPreviousClose") or meta.get("previousClose")),
    )
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    cols = [q.get(k) or [] for k in ("open", "high", "low", "close")]
    for i, ts in enumerate(res.get("timestamp") or []):
        row = [c[i] if i < len(c) else None for c in cols]
        if None in row:
            continue
        s.bars.append((int(ts), *(float(v) for v in row)))
    return s


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

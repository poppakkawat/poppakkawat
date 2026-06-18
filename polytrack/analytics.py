"""Analytics over a list of trades: leaderboards, hot markets, whales."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .client import Trade


@dataclass
class Aggregate:
    """Rolled-up stats for a market or trader."""

    key: str
    label: str
    usd: float = 0.0
    count: int = 0
    buy_usd: float = 0.0
    sell_usd: float = 0.0
    extra: dict = field(default_factory=dict)


@dataclass
class Swing:
    """Price movement for one market outcome over the window."""

    title: str
    outcome: str
    slug: str
    open_price: float
    close_price: float
    high: float
    low: float
    count: int
    volume_usd: float

    @property
    def delta(self) -> float:
        """Signed price change (close - open), in probability points."""
        return self.close_price - self.open_price

    @property
    def abs_delta(self) -> float:
        return abs(self.delta)


@dataclass
class WatchHit:
    """A watched wallet's activity over the window."""

    address: str
    label: str
    trades: list[Trade]
    usd: float
    buy_usd: float
    sell_usd: float


@dataclass
class Analysis:
    trades: list[Trade]
    total_usd: float
    count: int
    buy_usd: float
    sell_usd: float
    top_trades: list[Trade]
    hot_markets: list[Aggregate]
    top_traders: list[Aggregate]
    conviction: list[Trade]
    price_swings: list[Swing] = field(default_factory=list)
    watchlist: list[WatchHit] = field(default_factory=list)


def _add_side(agg: Aggregate, t: Trade) -> None:
    agg.usd += t.usd
    agg.count += 1
    if t.side == "BUY":
        agg.buy_usd += t.usd
    else:
        agg.sell_usd += t.usd


def detect_swings(
    trades: list[Trade], top_n: int = 10, min_points: int = 3
) -> list[Swing]:
    """Estimate per-outcome price movement from observed trades.

    Groups trades by outcome token (``asset``), then for each group with at
    least ``min_points`` trades computes open/close/high/low from the trade
    prices in chronological order. Returns the biggest absolute movers.

    Note: this is derived from trades we sampled (≥ the notional threshold),
    so it's a signal, not an exact mid-price history.
    """
    groups: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        if t.size > 0:
            groups[t.asset].append(t)

    swings: list[Swing] = []
    for asset, ts in groups.items():
        if len(ts) < min_points:
            continue
        ts.sort(key=lambda t: t.timestamp)
        prices = [t.price for t in ts]
        first, last = ts[0], ts[-1]
        swings.append(
            Swing(
                title=first.title,
                outcome=first.outcome,
                slug=first.slug,
                open_price=prices[0],
                close_price=prices[-1],
                high=max(prices),
                low=min(prices),
                count=len(ts),
                volume_usd=sum(t.usd for t in ts),
            )
        )
    swings.sort(key=lambda s: s.abs_delta, reverse=True)
    return swings[:top_n]


def collect_watchlist(
    watch_trades: list[Trade], watchlist: dict[str, str], top_n: int = 25
) -> list[WatchHit]:
    """Roll up a tracked wallet's trades into per-wallet watch hits."""
    by_wallet: dict[str, list[Trade]] = defaultdict(list)
    for t in watch_trades:
        addr = t.wallet.lower()
        if addr in watchlist:
            by_wallet[addr].append(t)

    hits: list[WatchHit] = []
    for addr, label in watchlist.items():
        ts = by_wallet.get(addr, [])
        if not ts:
            continue
        ts.sort(key=lambda t: t.timestamp, reverse=True)
        buy = sum(t.usd for t in ts if t.side == "BUY")
        total = sum(t.usd for t in ts)
        hits.append(
            WatchHit(
                address=addr,
                label=label,
                trades=ts[:top_n],
                usd=total,
                buy_usd=buy,
                sell_usd=total - buy,
            )
        )
    hits.sort(key=lambda h: h.usd, reverse=True)
    return hits


def analyze(
    trades: list[Trade],
    top_n: int = 10,
    watch_trades: list[Trade] | None = None,
    watchlist: dict[str, str] | None = None,
) -> Analysis:
    """Compute the full analytics bundle from a list of trades."""
    total_usd = sum(t.usd for t in trades)
    buy_usd = sum(t.usd for t in trades if t.side == "BUY")
    sell_usd = total_usd - buy_usd

    markets: dict[str, Aggregate] = {}
    traders: dict[str, Aggregate] = {}
    for t in trades:
        m = markets.setdefault(t.condition_id, Aggregate(t.condition_id, t.title))
        _add_side(m, t)
        tr = traders.setdefault(t.wallet, Aggregate(t.wallet, t.trader))
        _add_side(tr, t)

    hot_markets = sorted(markets.values(), key=lambda a: a.usd, reverse=True)[:top_n]
    top_traders = sorted(traders.values(), key=lambda a: a.usd, reverse=True)[:top_n]
    top_trades = sorted(trades, key=lambda t: t.usd, reverse=True)[:top_n]

    # "Conviction": large trades where someone is buying near an extreme
    # price (strong directional bet) — buying cheap longshots or pricey
    # near-certainties in size.
    conviction = sorted(
        (t for t in trades if t.side == "BUY" and (t.price <= 0.15 or t.price >= 0.85)),
        key=lambda t: t.usd,
        reverse=True,
    )[:top_n]

    price_swings = detect_swings(trades, top_n=top_n)
    watch_hits = (
        collect_watchlist(watch_trades or [], watchlist)
        if watchlist
        else []
    )

    return Analysis(
        trades=trades,
        total_usd=total_usd,
        count=len(trades),
        buy_usd=buy_usd,
        sell_usd=sell_usd,
        top_trades=top_trades,
        hot_markets=hot_markets,
        top_traders=top_traders,
        conviction=conviction,
        price_swings=price_swings,
        watchlist=watch_hits,
    )

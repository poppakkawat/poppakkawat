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


def _add_side(agg: Aggregate, t: Trade) -> None:
    agg.usd += t.usd
    agg.count += 1
    if t.side == "BUY":
        agg.buy_usd += t.usd
    else:
        agg.sell_usd += t.usd


def analyze(trades: list[Trade], top_n: int = 10) -> Analysis:
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
    )

"""Turn prediction-market activity into cross-market trade signals.

The premise: a prediction market's price for an outcome *is* the crowd's
probability for that event. Many events map cleanly onto tradeable
instruments (rate cuts -> bonds, war -> oil/gold/defense, BTC up -> COIN).
When the prediction market has strong conviction but the underlying
instrument hasn't moved, that's a potential edge ("not priced in").

This module is deliberately rule-based and transparent — every signal shows
its mapping and rationale. It is research tooling, **not** financial advice;
prediction markets can be illiquid, biased, or simply wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .client import Trade
from .market_data import Quote, get_quotes

# Outcome labels that mean "the event happens / price goes up".
POSITIVE = {"yes", "up", "over", "above"}
NEGATIVE = {"no", "down", "under", "below"}

# sign = effect on the instrument when the event's YES probability is HIGH:
#   +1 bullish, -1 bearish, 0 raises volatility / direction unclear.
@dataclass
class Rule:
    label: str
    keywords: tuple[str, ...]
    instruments: tuple[tuple[str, str, int], ...]  # (ticker, name, sign)
    rationale: str
    exclude: tuple[str, ...] = ()


RULES: tuple[Rule, ...] = (
    Rule(
        "Fed rate cut",
        ("rate cut", "cut rates", "cuts rates", "decrease interest", "lower rates",
         "fed cut", "rate decrease", "50+ bps decrease", "25 bps decrease"),
        (("TLT", "20Y Treasuries", +1), ("SPY", "S&P 500", +1),
         ("GLD", "Gold", +1), ("XLF", "Financials", +1)),
        "Cuts ease financial conditions: bullish bonds, equities, gold.",
    ),
    Rule(
        "Fed rate hike",
        ("rate hike", "hike rates", "hikes rates", "raise rates", "increase interest",
         "fed hike", "rate increase", "bps increase"),
        (("TLT", "20Y Treasuries", -1), ("SPY", "S&P 500", -1), ("GLD", "Gold", -1)),
        "Hikes tighten conditions: bearish bonds, equities, gold.",
    ),
    Rule(
        "Recession",
        ("recession", "gdp decline", "economic contraction"),
        (("SPY", "S&P 500", -1), ("TLT", "20Y Treasuries", +1),
         ("XLP", "Consumer Staples", +1), ("HYG", "High-Yield Credit", -1)),
        "Recession risk: risk-off, defensives and Treasuries bid.",
    ),
    Rule(
        "Inflation / CPI",
        ("cpi", "inflation"),
        (("TIP", "TIPS", +1), ("GLD", "Gold", +1), ("TLT", "20Y Treasuries", -1)),
        "Hot inflation: bullish inflation hedges, bearish duration.",
        exclude=("deflation",),
    ),
    Rule(
        "Government shutdown",
        ("government shutdown", "shutdown",),
        (("SPY", "S&P 500", -1), ("GLD", "Gold", +1), ("^VIX", "Volatility", 0)),
        "Shutdown risk: mild risk-off, vol and gold bid.",
    ),
    Rule(
        "Tariffs / trade war",
        ("tariff", "trade war", "import tax"),
        (("SPY", "S&P 500", -1), ("FXI", "China Large-Caps", -1), ("GLD", "Gold", +1)),
        "Tariffs hit risk assets and China exposure; gold benefits.",
    ),
    Rule(
        "Armed conflict / war",
        ("invade", "invasion", "war ", "military strike", "airstrike", "nuclear",
         "attack iran", "strike iran", "missile"),
        (("CL=F", "Crude Oil", +1), ("XLE", "Energy", +1), ("GLD", "Gold", +1),
         ("ITA", "Defense", +1), ("SPY", "S&P 500", -1), ("^VIX", "Volatility", 0)),
        "Conflict: oil/gold/defense bid, equities risk-off, vol up.",
        exclude=("ceasefire", "peace deal", "peace agreement"),
    ),
    Rule(
        "Ceasefire / peace",
        ("ceasefire", "peace deal", "peace agreement", "permanent peace"),
        (("CL=F", "Crude Oil", -1), ("GLD", "Gold", -1), ("SPY", "S&P 500", +1)),
        "De-escalation: oil/gold cool off, equities risk-on.",
    ),
    Rule(
        "Oil / OPEC",
        ("opec", "crude oil", "oil price", "barrel"),
        (("CL=F", "Crude Oil", +1), ("XLE", "Energy", +1), ("USO", "Oil ETF", +1)),
        "Direct read on crude and energy equities.",
    ),
    Rule(
        "Bitcoin",
        ("bitcoin", "btc "),
        (("BTC", "Bitcoin", +1), ("COIN", "Coinbase", +1),
         ("MSTR", "MicroStrategy", +1), ("IBIT", "iShares BTC ETF", +1)),
        "Higher BTC: bullish crypto proxies COIN/MSTR/IBIT.",
    ),
    Rule(
        "Ethereum",
        ("ethereum", "eth "),
        (("ETH", "Ethereum", +1), ("COIN", "Coinbase", +1)),
        "Higher ETH: bullish crypto complex.",
    ),
    Rule(
        "Nvidia / AI",
        ("nvidia", "nvda"),
        (("NVDA", "Nvidia", +1), ("SMH", "Semiconductors", +1)),
        "Company/AI event mapped to the stock and chip sector.",
    ),
    Rule(
        "Tesla",
        ("tesla", "tsla", "elon musk"),
        (("TSLA", "Tesla", +1),),
        "Company event mapped to the stock.",
    ),
)


@dataclass
class Signal:
    rule: Rule
    market_title: str
    venue: str
    url: str
    yes_prob: float  # crowd probability the "positive" outcome occurs
    n_trades: int
    volume_usd: float
    quotes: dict[str, Quote | None] = field(default_factory=dict)

    @property
    def conviction(self) -> float:
        return abs(self.yes_prob - 0.5) * 2.0  # 0 (coin flip) .. 1 (certain)


def _yes_prob(latest: Trade) -> float | None:
    o = latest.outcome.strip().lower()
    if o in POSITIVE:
        return latest.price
    if o in NEGATIVE:
        return 1.0 - latest.price
    return None  # multi-outcome (e.g. team names) — not a clean binary


def _match_rule(title: str) -> Rule | None:
    t = title.lower()
    for rule in RULES:
        if any(x in t for x in rule.exclude):
            continue
        if any(k in t for k in rule.keywords):
            return rule
    return None


def find_signals(trades: list[Trade], top_n: int = 15) -> list[Signal]:
    """Derive cross-market signals from the fetched trades.

    One signal per matched market, using its most recent trade for the
    implied probability and summing notional/volume across the window.
    """
    by_market: dict[str, list[Trade]] = {}
    for t in trades:
        by_market.setdefault(t.condition_id, []).append(t)

    signals: list[Signal] = []
    for ts in by_market.values():
        rule = _match_rule(ts[0].title)
        if not rule:
            continue
        latest = max(ts, key=lambda t: t.timestamp)
        p = _yes_prob(latest)
        if p is None:
            continue
        signals.append(
            Signal(
                rule=rule,
                market_title=latest.title,
                venue=latest.venue,
                url=latest.url,
                yes_prob=p,
                n_trades=len(ts),
                volume_usd=sum(t.usd for t in ts),
            )
        )

    # Rank: actionable directional views first (decisive enough to imply a
    # trade), then by conviction and liquidity.
    def _actionable(s: Signal) -> int:
        return 1 if expected_sign(s.yes_prob, 1) != 0 else 0

    signals.sort(
        key=lambda s: (_actionable(s), s.conviction, s.volume_usd), reverse=True
    )
    signals = signals[:top_n]

    # Attach live quotes for every instrument referenced.
    tickers = sorted({tk for s in signals for (tk, _, _) in s.rule.instruments})
    quotes = get_quotes(tickers) if tickers else {}
    for s in signals:
        s.quotes = {tk: quotes.get(tk) for (tk, _, _) in s.rule.instruments}
    return signals


def expected_sign(yes_prob: float, instrument_sign: int) -> int:
    """Expected instrument direction given the crowd probability.

    Only takes a directional view when the market is decisive (>=0.60 the
    event happens). Below that we stay neutral to avoid overclaiming.
    """
    if yes_prob >= 0.60:
        return instrument_sign
    return 0


def alignment(yes_prob: float, instrument_sign: int, q: Quote | None) -> str:
    """One-glyph read of prediction-market view vs the instrument's move."""
    exp = expected_sign(yes_prob, instrument_sign)
    if exp == 0:
        return "▫"  # no decisive view yet
    if q is None or q.pct_change is None:
        return "•"  # have a view, no live move to compare
    move = q.pct_change
    if exp > 0:
        return "✅" if move > 0.1 else "⚠️"   # expect up
    return "✅" if move < -0.1 else "⚠️"       # expect down

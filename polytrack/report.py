"""Render an Analysis into a human-friendly Markdown daily report."""

from __future__ import annotations

from datetime import datetime, timezone

from .analytics import Analysis
from .client import Trade
from .signals import Signal, alignment, expected_sign

POLYMARKET_EVENT = "https://polymarket.com/event/"


def _money(x: float) -> str:
    if x >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"${x/1_000:.1f}K"
    return f"${x:,.0f}"


VENUE_TAG = {"polymarket": "PM", "kalshi": "KX"}


def _market_link(t: Trade) -> str:
    title = t.title.replace("|", "\\|")
    return f"[{title}]({t.url})" if t.url else title


def _price(x: float) -> str:
    if x >= 1000:
        return f"{x:,.0f}"
    if x >= 1:
        return f"{x:,.2f}"
    return f"{x:.4f}"


def render_signals(signals: list[Signal], limit: int = 12) -> list[str]:
    """Markdown for the cross-market edge section."""
    lines: list[str] = []
    lines.append("## 🧭 Cross-Market Edge Signals")
    lines.append("")
    if not signals:
        lines.append(
            "_No mapped macro/crypto markets in this window. "
            "Lower `--min` for more coverage._"
        )
        lines.append("")
        return lines
    lines.append(
        "_What prediction markets imply for traditional assets. "
        "Reads: ✅ instrument confirms · ⚠️ not priced in (possible edge) · "
        "▫ no decisive view yet._"
    )
    lines.append("")

    for s in signals[:limit]:
        flags = sum(
            1
            for (tk, _, sign) in s.rule.instruments
            if alignment(s.yes_prob, sign, s.quotes.get(tk)) == "⚠️"
        )
        edge = f" · ⚠️ {flags} possibly unpriced" if flags else ""
        lines.append(
            f"### {VENUE_TAG.get(s.venue, s.venue)} · {s.rule.label} — "
            f"implied **{s.yes_prob:.0%}**{edge}"
        )
        title = s.market_title.replace("|", "\\|")
        link = f"[{title}]({s.url})" if s.url else title
        lines.append(f"_{link}_")
        lines.append("")
        lines.append("| Instrument | Last | Day | Implied view | Read |")
        lines.append("|:-----------|-----:|----:|:------------:|:----:|")
        for (tk, name, sign) in s.rule.instruments:
            q = s.quotes.get(tk)
            last = _price(q.price) if q else "—"
            day = (f"{q.pct_change:+.2f}%" if q and q.pct_change is not None else "—")
            exp = expected_sign(s.yes_prob, sign)
            view = {1: "↑ bullish", -1: "↓ bearish", 0: "→ neutral"}[exp]
            read = alignment(s.yes_prob, sign, q)
            lines.append(f"| {name} ({tk}) | {last} | {day} | {view} | {read} |")
        lines.append("")
        lines.append(f"> {s.rule.rationale}")
        lines.append("")
    return lines


def render(
    analysis: Analysis,
    window_label: str,
    min_usd: float,
    signals: list[Signal] | None = None,
) -> str:
    a = analysis
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines.append(f"# Prediction Markets Daily — {datetime.now(timezone.utc):%Y-%m-%d}")
    lines.append("")
    lines.append(
        f"_Generated {now} · window: {window_label} · "
        f"trades ≥ {_money(min_usd)} notional_"
    )
    lines.append("")

    if a.count == 0:
        lines.append("No qualifying trades found in this window.")
        lines.append("")
        return "\n".join(lines)

    # Summary
    flow = a.buy_usd - a.sell_usd
    bias = "net BUY" if flow >= 0 else "net SELL"
    lines.append("## 📊 Summary")
    lines.append("")
    lines.append(f"- **Notable trades:** {a.count:,}")
    lines.append(f"- **Total notional:** {_money(a.total_usd)}")
    lines.append(
        f"- **Flow:** {_money(a.buy_usd)} buys vs {_money(a.sell_usd)} sells "
        f"→ **{bias}** ({_money(abs(flow))})"
    )

    # Per-venue breakdown (only when more than one venue is present)
    venues: dict[str, list] = {}
    for t in a.trades:
        venues.setdefault(t.venue, []).append(t)
    if len(venues) > 1:
        lines.append("")
        lines.append("| Venue | Trades | Notional |")
        lines.append("|:------|-------:|---------:|")
        for v, ts in sorted(venues.items(), key=lambda kv: -sum(t.usd for t in kv[1])):
            name = {"polymarket": "Polymarket", "kalshi": "Kalshi"}.get(v, v)
            lines.append(f"| {name} | {len(ts)} | {_money(sum(t.usd for t in ts))} |")
    lines.append("")

    # Cross-market edge signals (headline section)
    if signals is not None:
        lines.extend(render_signals(signals))

    # Smart-money watchlist
    if a.watchlist:
        lines.append("## 🧠 Smart-Money Watchlist")
        lines.append("")
        for h in a.watchlist:
            flow = "net BUY" if h.buy_usd >= h.sell_usd else "net SELL"
            lines.append(
                f"### {h.label} — {_money(h.usd)} across {len(h.trades)} trade(s), {flow}"
            )
            lines.append(
                f"_[profile](https://polymarket.com/profile/{h.address})_"
            )
            lines.append("")
            lines.append("| USD | Side | Outcome | Price | Market |")
            lines.append("|----:|:----:|:--------|:-----:|:-------|")
            for t in sorted(h.trades, key=lambda t: t.usd, reverse=True):
                lines.append(
                    f"| {_money(t.usd)} | {t.side} | {t.outcome} | "
                    f"{t.price:.2f} | {_market_link(t)} |"
                )
            lines.append("")

    # Biggest trades
    lines.append("## 🐳 Biggest Trades")
    lines.append("")
    lines.append("| USD | Venue | Side | Outcome | Price | Trader | Market |")
    lines.append("|----:|:-----:|:----:|:--------|:-----:|:-------|:-------|")
    for t in a.top_trades:
        lines.append(
            f"| {_money(t.usd)} | {VENUE_TAG.get(t.venue, t.venue)} | {t.side} | "
            f"{t.outcome} | {t.price:.2f} | {t.trader} | {_market_link(t)} |"
        )
    lines.append("")

    # Hot markets
    lines.append("## 🔥 Hottest Markets")
    lines.append("")
    lines.append("| Notional | Venue | Trades | Market |")
    lines.append("|---------:|:-----:|-------:|:-------|")
    for m in a.hot_markets:
        sample = next((t for t in a.trades if t.condition_id == m.key), None)
        link = _market_link(sample) if sample else m.label
        tag = VENUE_TAG.get(sample.venue, sample.venue) if sample else "?"
        lines.append(f"| {_money(m.usd)} | {tag} | {m.count} | {link} |")
    lines.append("")

    # Price swings
    if a.price_swings:
        lines.append("## 📈 Biggest Price Swings")
        lines.append("")
        lines.append("_Largest open→close moves among sampled trades (≥3 prints)._")
        lines.append("")
        lines.append("| Move | Venue | Open→Close | Range | Outcome | Market |")
        lines.append("|:----:|:-----:|:----------:|:-----:|:--------|:-------|")
        for s in a.price_swings:
            arrow = "🔺" if s.delta >= 0 else "🔻"
            move = f"{arrow} {s.delta:+.2f}"
            oc = f"{s.open_price:.2f}→{s.close_price:.2f}"
            rng = f"{s.low:.2f}–{s.high:.2f}"
            title = s.title.replace("|", "\\|")
            link = f"[{title}]({s.url})" if s.url else title
            tag = VENUE_TAG.get(s.venue, s.venue)
            lines.append(f"| {move} | {tag} | {oc} | {rng} | {s.outcome} | {link} |")
        lines.append("")

    # Top traders
    lines.append("## 💸 Most Active Traders")
    lines.append("")
    lines.append("| Notional | Trades | Buy/Sell | Trader |")
    lines.append("|---------:|-------:|:--------:|:-------|")
    for tr in a.top_traders:
        profile = f"[{tr.label}](https://polymarket.com/profile/{tr.key})"
        lines.append(
            f"| {_money(tr.usd)} | {tr.count} | "
            f"{_money(tr.buy_usd)}/{_money(tr.sell_usd)} | {profile} |"
        )
    lines.append("")

    # Conviction bets
    if a.conviction:
        lines.append("## 🎯 High-Conviction Bets")
        lines.append("")
        lines.append("_Large buys at extreme prices (≤0.15 longshots or ≥0.85 favorites)._")
        lines.append("")
        lines.append("| USD | Price | Outcome | Trader | Market |")
        lines.append("|----:|:-----:|:--------|:-------|:-------|")
        for t in a.conviction:
            lines.append(
                f"| {_money(t.usd)} | {t.price:.2f} | {t.outcome} | "
                f"{t.trader} | {_market_link(t)} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Data: Polymarket & Kalshi public APIs. Not financial advice._")
    lines.append("")
    return "\n".join(lines)

"""Render an Analysis into a human-friendly Markdown daily report."""

from __future__ import annotations

from datetime import datetime, timezone

from .analytics import Analysis
from .client import Trade

POLYMARKET_EVENT = "https://polymarket.com/event/"


def _money(x: float) -> str:
    if x >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"${x/1_000:.1f}K"
    return f"${x:,.0f}"


def _market_link(t: Trade) -> str:
    slug = t.slug or ""
    title = t.title.replace("|", "\\|")
    return f"[{title}]({POLYMARKET_EVENT}{slug})" if slug else title


def render(analysis: Analysis, window_label: str, min_usd: float) -> str:
    a = analysis
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines.append(f"# Polymarket Daily — {datetime.now(timezone.utc):%Y-%m-%d}")
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
    lines.append("")

    # Biggest trades
    lines.append("## 🐳 Biggest Trades")
    lines.append("")
    lines.append("| USD | Side | Outcome | Price | Trader | Market |")
    lines.append("|----:|:----:|:--------|:-----:|:-------|:-------|")
    for t in a.top_trades:
        lines.append(
            f"| {_money(t.usd)} | {t.side} | {t.outcome} | "
            f"{t.price:.2f} | {t.trader} | {_market_link(t)} |"
        )
    lines.append("")

    # Hot markets
    lines.append("## 🔥 Hottest Markets")
    lines.append("")
    lines.append("| Notional | Trades | Buy/Sell | Market |")
    lines.append("|---------:|-------:|:--------:|:-------|")
    for m in a.hot_markets:
        sample = next((t for t in a.trades if t.condition_id == m.key), None)
        link = _market_link(sample) if sample else m.label
        lines.append(
            f"| {_money(m.usd)} | {m.count} | "
            f"{_money(m.buy_usd)}/{_money(m.sell_usd)} | {link} |"
        )
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
    lines.append("_Data: Polymarket public data API. Not financial advice._")
    lines.append("")
    return "\n".join(lines)

"""Command-line entry point for polytrack.

Usage examples:
    python -m polytrack                       # last 24h, $5k+, print report
    python -m polytrack --hours 12 --min 10000
    python -m polytrack --save               # write to reports/YYYY-MM-DD.md
    python -m polytrack --json out.json       # also dump raw analysis as JSON
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .analytics import analyze
from .client import fetch_large_trades, fetch_user_trades
from .kalshi import fetch_kalshi_trades
from .notify import build_summary, notify
from .report import render, render_briefing, render_signals
from .signals import alignment, apply_history, find_signals
from .state import DEFAULT_STATE, load_state, save_state


def load_watchlist(path: str | None) -> dict[str, str]:
    """Load a wallet watchlist from JSON.

    Accepts either a mapping ``{"0xabc...": "Label"}`` or a list of
    ``{"address": "0x...", "label": "..."}`` objects. Addresses are
    lower-cased. Returns {} if the file is absent.
    """
    p = Path(path) if path else Path("watchlist.json")
    if not p.exists():
        if path:  # explicitly requested but missing
            print(f"watchlist: {p} not found.", file=sys.stderr)
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    if isinstance(data, dict):
        for addr, label in data.items():
            out[addr.lower()] = str(label)
    elif isinstance(data, list):
        for item in data:
            addr = (item.get("address") or "").lower()
            if addr:
                out[addr] = str(item.get("label") or addr[:10])
    return out


def _serialize(analysis, min_usd, hours, signals=None) -> dict:
    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "window_hours": hours,
        "min_usd": min_usd,
        "total_usd": analysis.total_usd,
        "count": analysis.count,
        "buy_usd": analysis.buy_usd,
        "sell_usd": analysis.sell_usd,
        "top_trades": [vars(t) | {"usd": t.usd} for t in analysis.top_trades],
        "hot_markets": [vars(m) for m in analysis.hot_markets],
        "top_traders": [vars(t) for t in analysis.top_traders],
        "price_swings": [
            {
                "title": s.title, "outcome": s.outcome, "slug": s.slug,
                "open": s.open_price, "close": s.close_price,
                "high": s.high, "low": s.low, "delta": s.delta,
                "count": s.count, "volume_usd": s.volume_usd,
            }
            for s in analysis.price_swings
        ],
        "watchlist": [
            {
                "address": h.address, "label": h.label, "usd": h.usd,
                "buy_usd": h.buy_usd, "sell_usd": h.sell_usd,
                "trade_count": len(h.trades),
            }
            for h in analysis.watchlist
        ],
    }
    if signals is not None:
        out["signals"] = [
            {
                "theme": s.rule.label, "market": s.market_title, "venue": s.venue,
                "url": s.url, "implied_prob": s.yes_prob, "conviction": s.conviction,
                "volume_usd": s.volume_usd,
                "instruments": [
                    {
                        "ticker": tk, "name": name, "sign": sign,
                        "last": (s.quotes.get(tk).price if s.quotes.get(tk) else None),
                        "pct_change": (
                            s.quotes.get(tk).pct_change if s.quotes.get(tk) else None
                        ),
                    }
                    for (tk, name, sign) in s.rule.instruments
                ],
            }
            for s in signals
        ]
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="polytrack",
        description="Daily updates & analytics of interesting Polymarket trades.",
    )
    p.add_argument("--hours", type=float, default=24,
                   help="Look-back window in hours (default: 24)")
    p.add_argument("--min", dest="min_usd", type=float, default=5000,
                   help="Minimum trade notional in USD (default: 5000)")
    p.add_argument("--top", type=int, default=10,
                   help="Rows per leaderboard (default: 10)")
    p.add_argument("--save", action="store_true",
                   help="Write the report to reports/YYYY-MM-DD.md")
    p.add_argument("--out", type=str, default=None,
                   help="Explicit output path for the Markdown report")
    p.add_argument("--out-dir", type=str, default=None,
                   help="Directory to write YYYY-MM-DD.md into (created if needed)")
    p.add_argument("--json", dest="json_out", type=str, default=None,
                   help="Also write raw analysis JSON to this path")
    p.add_argument("--max-trades", type=int, default=5000,
                   help="Safety cap on trades fetched (default: 5000)")
    p.add_argument("--source", type=str, default="both",
                   choices=["polymarket", "kalshi", "both"],
                   help="Which venue(s) to include (default: both)")
    p.add_argument("--kalshi-min", type=float, default=None,
                   help="Min Kalshi trade notional (default: same as --min)")
    p.add_argument("--watchlist", type=str, default=None,
                   help="Path to watchlist JSON (default: watchlist.json if present)")
    p.add_argument("--no-edge", dest="edge", action="store_false", default=True,
                   help="Skip the cross-market edge signals section")
    p.add_argument("--edge-only", action="store_true",
                   help="Print ONLY the edge briefing + signals")
    p.add_argument("--state-file", type=str, default=str(DEFAULT_STATE),
                   help="Path to day-over-day state JSON (default: reports/state/edge_state.json)")
    p.add_argument("--notify", type=str, default=None,
                   help="Comma-separated channels: discord,telegram,email")
    p.add_argument("--dry-run-notify", action="store_true",
                   help="Print the notification text instead of sending")
    args = p.parse_args(argv)

    since_ts = int(time.time() - args.hours * 3600)
    trades = []

    if args.source in ("polymarket", "both"):
        print(f"Fetching Polymarket trades ≥ ${args.min_usd:,.0f} "
              f"from the last {args.hours:g}h…", file=sys.stderr)
        pm = fetch_large_trades(
            min_usd=args.min_usd, since_ts=since_ts, max_trades=args.max_trades
        )
        print(f"  Polymarket: {len(pm)} trades.", file=sys.stderr)
        trades += pm

    if args.source in ("kalshi", "both"):
        kmin = args.kalshi_min if args.kalshi_min is not None else args.min_usd
        print(f"Fetching Kalshi trades ≥ ${kmin:,.0f} "
              f"from the last {args.hours:g}h…", file=sys.stderr)
        kx = fetch_kalshi_trades(min_usd=kmin, since_ts=since_ts)
        print(f"  Kalshi: {len(kx)} trades.", file=sys.stderr)
        trades += kx

    # Watchlist is Polymarket-only (Kalshi trades are anonymous).
    watchlist = load_watchlist(args.watchlist) if args.source != "kalshi" else {}
    watch_trades = []
    if watchlist:
        print(f"Tracking {len(watchlist)} watched wallet(s)…", file=sys.stderr)
        for addr in watchlist:
            watch_trades.extend(fetch_user_trades(addr, since_ts=since_ts))

    analysis = analyze(
        trades, top_n=args.top, watch_trades=watch_trades, watchlist=watchlist
    )
    window_label = f"last {args.hours:g}h"

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    signals = None
    if args.edge or args.edge_only:
        print("Scanning cross-market edge signals…", file=sys.stderr)
        signals = find_signals(trades)
        # Day-over-day: annotate with prior probabilities, then persist.
        state = load_state(args.state_file)
        apply_history(signals, state, day)
        save_state(state, args.state_file)
        print(f"  {len(signals)} mapped signal(s).", file=sys.stderr)

    if args.edge_only:
        md = "\n".join(
            [f"# Daily Edge Briefing — {day}", "",
             f"_Window: {window_label}_", ""]
            + render_briefing(signals or [])
            + render_signals(signals or [], limit=50)
        )
    else:
        md = render(
            analysis, window_label=window_label,
            min_usd=args.min_usd, signals=signals,
        )

    out_path: Path | None = None
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if args.out:
        out_path = Path(args.out)
    elif args.out_dir:
        out_path = Path(args.out_dir) / f"{day}.md"
    elif args.save:
        out_path = Path("reports") / f"{day}.md"

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"Wrote report → {out_path}", file=sys.stderr)
    else:
        print(md)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                _serialize(analysis, args.min_usd, args.hours, signals=signals),
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Wrote JSON → {args.json_out}", file=sys.stderr)

    if args.notify or args.dry_run_notify:
        channels = (args.notify or "discord,telegram,email").split(",")
        summary = build_summary(analysis, window_label, signals=signals)
        notify(channels, summary, dry_run=args.dry_run_notify)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

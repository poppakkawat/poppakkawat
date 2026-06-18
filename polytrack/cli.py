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
from .client import fetch_large_trades
from .report import render


def _serialize(analysis, min_usd, hours) -> dict:
    return {
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
    }


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
    p.add_argument("--json", dest="json_out", type=str, default=None,
                   help="Also write raw analysis JSON to this path")
    p.add_argument("--max-trades", type=int, default=5000,
                   help="Safety cap on trades fetched (default: 5000)")
    args = p.parse_args(argv)

    since_ts = int(time.time() - args.hours * 3600)
    print(f"Fetching Polymarket trades ≥ ${args.min_usd:,.0f} "
          f"from the last {args.hours:g}h…", file=sys.stderr)

    trades = fetch_large_trades(
        min_usd=args.min_usd, since_ts=since_ts, max_trades=args.max_trades
    )
    print(f"Fetched {len(trades)} trades.", file=sys.stderr)

    analysis = analyze(trades, top_n=args.top)
    window_label = f"last {args.hours:g}h"
    md = render(analysis, window_label=window_label, min_usd=args.min_usd)

    out_path: Path | None = None
    if args.out:
        out_path = Path(args.out)
    elif args.save:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_path = Path("reports") / f"{day}.md"

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"Wrote report → {out_path}", file=sys.stderr)
    else:
        print(md)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(_serialize(analysis, args.min_usd, args.hours), indent=2),
            encoding="utf-8",
        )
        print(f"Wrote JSON → {args.json_out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

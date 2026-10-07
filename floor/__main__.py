"""Update the paper desks and write the dashboard's data file.

    python -m floor --state out/state.json --out out/data.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from . import config as C
from .data import chart
from .desks import local_date, run_alpha, run_grid, run_roc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="floor", description=__doc__)
    ap.add_argument("--state", default="out/state.json", help="state file (read and rewritten)")
    ap.add_argument("--out", default="out/data.json", help="dashboard data file to write")
    args = ap.parse_args(argv)

    st: dict = {}
    if os.path.exists(args.state):
        with open(args.state, encoding="utf-8") as f:
            st = json.load(f)
    now = time.time()

    rate = chart(C.RATE_SYMBOL, "5d", "1d")
    oil = chart(C.GRID_SYMBOL, f"{max(C.GRID_BACKFILL_DAYS, 5)}d", "5m")
    syms = list(dict.fromkeys(C.ALPHA_WATCHLIST + list(C.ALPHA_BENCHMARK)))
    eq_series = {s: chart(s, "1y", "1d") for s in syms}

    missing = [s.symbol for s in [rate, oil, *eq_series.values()] if s.price is None and not s.bars]
    if missing:
        print("no data for: " + ", ".join(missing), file=sys.stderr)
    if not oil.bars and "grid" not in st:
        print("no oil prices on first run; try again later", file=sys.stderr)
        return 1

    roc = run_roc(st, rate, now)
    grid = run_grid(st, oil, now)
    alpha, alpha_events = run_alpha(st, eq_series, now)

    equity = roc.get("equity", 0) + grid.get("equity", C.START_CAPITAL["grid"]) + alpha.get(
        "equity", C.START_CAPITAL["alpha"])
    h = st.setdefault("hud", {})
    today, month = local_date(now), local_date(now)[:7]
    if h.get("day") != today:
        h["day"], h["day_start"] = today, h.get("last", equity)
    if h.get("month") != month:
        h["month"], h["month_start"] = month, h.get("last", equity)
    h["peak"] = max(h.get("peak", equity), equity)
    h["last"] = equity
    capital = sum(C.START_CAPITAL.values())

    events = [e for evs in st.get("events", {}).values() for e in evs] + alpha_events
    events.sort(key=lambda e: e["ts"])

    out = {
        "updated": int(now),
        "updated_iso": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"),
        "mode": "paper",
        "tz_offset_hours": C.TZ_OFFSET_HOURS,
        "hud": {
            "capital": capital, "equity": equity, "day_pnl": equity - h["day_start"],
            "mtd": equity - h["month_start"], "mtd_target": capital * C.MONTHLY_TARGET_PCT / 100,
            "drawdown_pct": (h["peak"] - equity) / h["peak"] * 100 if h["peak"] else 0.0,
            "drawdown_limit_pct": C.MAX_DRAWDOWN_PCT,
        },
        "capital": C.START_CAPITAL,
        "roc": roc, "grid": grid, "alpha": alpha,
        "events": events[-90:],
        "missing": missing,
    }
    st["updated"] = int(now)

    for path, obj in ((args.state, st), (args.out, out)):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    print(f"equity ${equity:,.2f} · WTI {grid.get('price')} · alpha {alpha.get('alpha', 0):+.2f}% · "
          f"{len(events)} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

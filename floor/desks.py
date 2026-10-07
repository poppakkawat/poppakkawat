"""The three paper desks. Each ``run_*`` updates its slice of ``state`` in place
and returns the numbers the dashboard shows for that desk."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from . import config as C
from .data import Series

EVENT_CAP = 40  # per desk, kept in the state file


# --------------------------------------------------------------------------
# helpers

def local_date(ts: float) -> str:
    return datetime.fromtimestamp(ts + C.TZ_OFFSET_HOURS * 3600, timezone.utc).date().isoformat()


def utc_date(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def date_ts(d: str, hour_utc: int = 2) -> int:
    y, m, dd = map(int, d.split("-"))
    return int(datetime(y, m, dd, hour_utc, tzinfo=timezone.utc).timestamp())


def add_event(st: dict, desk: str, ts: float, who: str, text: str, kind: str = "info") -> None:
    evs = st.setdefault("events", {}).setdefault(desk, [])
    evs.append({"id": f"{desk}:{int(ts)}:{len(evs)}:{who}", "ts": int(ts), "desk": desk,
                "who": who, "text": text, "kind": kind})
    del evs[:-EVENT_CAP]


def money(v: float, d: int = 2) -> str:
    return f"{'-' if v < 0 else '+'}${abs(v):,.{d}f}"


# --------------------------------------------------------------------------
# Desk 1: Return on Cash

def run_roc(st: dict, rate: Series, now: float) -> dict:
    r = st.setdefault("roc", {})
    cap = C.START_CAPITAL["roc"]
    cur = rate.price if rate.price is not None else r.get("rate")
    if cur is None:
        cur = 0.0
    today = local_date(now)
    if "last_ts" not in r:
        r.update(cash=cap, accrued_total=0.0, last_ts=now, started=int(now), rate=cur,
                 rate_prev=cur, day={"date": today, "accrued": 0.0})
        add_event(st, "roc", now, "goldie", f"เปิดบัญชีเงินสด paper ${cap:,.0f} @ {cur:.2f}%")

    if r["day"]["date"] != today:
        prev = r["day"]
        if prev["accrued"] > 0:
            add_event(st, "roc", now, "goldie", f"ดอกเบี้ยวันที่ {prev['date']} รวม {money(prev['accrued'])}")
        r["day"] = {"date": today, "accrued": 0.0}

    dt = max(0.0, now - r["last_ts"])
    base = r["cash"] + r["accrued_total"]
    accr = base * (r["rate"] / 100.0) * dt / (365 * 86400)
    r["accrued_total"] += accr
    r["day"]["accrued"] += accr
    r["last_ts"] = now

    if abs(cur - r["rate"]) >= 0.02:
        add_event(st, "roc", now, "penny", f"อัตรา T-Bill 13 สัปดาห์ {r['rate']:.2f}% → {cur:.2f}%",
                  "alert" if cur < r["rate"] else "info")
        r["rate_prev"] = r["rate"]
    r["rate"] = cur

    return {
        "cash": r["cash"], "rate": cur, "rate_prev": r.get("rate_prev", cur),
        "accrued_today": r["day"]["accrued"], "accrued_total": r["accrued_total"],
        "equity": r["cash"] + r["accrued_total"], "started": r["started"],
    }


# --------------------------------------------------------------------------
# Desk 2: Beta / Oil Grid (long-only grid)

def _levels(g: dict) -> list[float]:
    n = int(round((g["hi"] - g["lo"]) / g["step"]))
    return [round(g["lo"] + i * g["step"], 2) for i in range(n + 1)]


def run_grid(st: dict, s: Series, now: float) -> dict:
    g = st.setdefault("grid", {})
    bars = s.bars
    if bars and "lo" not in g:
        start = now - C.GRID_BACKFILL_DAYS * 86400
        first = next((b for b in bars if b[0] >= start), bars[0])
        centre = round(first[4] / C.GRID_STEP) * C.GRID_STEP
        lo = C.GRID_LO if C.GRID_LO is not None else centre - C.GRID_STEP * C.GRID_LEVELS_EACH_SIDE
        hi = C.GRID_HI if C.GRID_HI is not None else centre + C.GRID_STEP * C.GRID_LEVELS_EACH_SIDE
        g.update(lo=round(lo, 2), hi=round(hi, 2), step=C.GRID_STEP, bbl=C.GRID_BARRELS_PER_LEVEL,
                 held=[], realized_total=0.0, fills_total=0, last_ts=first[0] - 1,
                 last_price=first[4], out=False, heavy=0, started=first[0],
                 day={"date": local_date(first[0]), "fills": 0, "realized": 0.0})
        add_event(st, "grid", first[0], "boss",
                  f"ตั้งกรอบ Grid {g['lo']:.2f}–{g['hi']:.2f} ห่างชั้นละ ${C.GRID_STEP:.2f}")
    if "lo" not in g:
        return {}

    levels = _levels(g)
    held = set(g["held"])
    step, bbl = g["step"], g["bbl"]

    def day_for(ts: int) -> dict:
        d = local_date(ts)
        if g["day"]["date"] != d:
            g["day"] = {"date": d, "fills": 0, "realized": 0.0}
        return g["day"]

    def cross(a: float, b: float, ts: int) -> None:
        if b < a:
            for L in sorted((L for L in levels if b <= L < a), reverse=True):
                if L < g["hi"] and L not in held:
                    held.add(L)
                    g["fills_total"] += 1
                    day_for(ts)["fills"] += 1
                    add_event(st, "grid", ts, "bot", f"BUY {bbl} bbl @ {L:.2f}", "buy")
        elif b > a:
            for L in sorted(L for L in levels if a < L <= b):
                below = round(L - step, 2)
                if below in held:
                    held.discard(below)
                    gain = step * bbl
                    g["realized_total"] += gain
                    g["fills_total"] += 1
                    day = day_for(ts)
                    day["fills"] += 1
                    day["realized"] += gain
                    add_event(st, "grid", ts, "bot", f"SELL @ {L:.2f} ปิดรอบ {money(gain)}", "sell")

    p0 = g["last_price"]
    for ts, o, h, l, c in bars:
        if ts <= g["last_ts"]:
            continue
        if abs(o - p0) > C.GRID_GAP_SKIP:
            add_event(st, "grid", ts, "boss", f"ราคากระโดด {p0:.2f} → {o:.2f} (gap/roll) ข้ามชั้นในช่องว่าง", "alert")
            p0 = o
        path = [p0, o, l, h, c] if c >= o else [p0, o, h, l, c]
        for a, b in zip(path, path[1:]):
            cross(a, b, ts)
        p0 = c
        g["last_ts"] = ts
        out = c < g["lo"] or c > g["hi"]
        if out != g["out"]:
            add_event(st, "grid", ts, "boss",
                      f"ราคา {c:.2f} หลุดกรอบ Grid! หยุดเติมชั้น" if out else f"ราคา {c:.2f} กลับเข้ากรอบแล้ว",
                      "alert" if out else "info")
            g["out"] = out
        n = len(held)
        heavy = 2 if n >= 12 else 1 if n >= 8 else 0
        if heavy > g["heavy"]:
            add_event(st, "grid", ts, "dusty", f"ถือ {n} ชั้น ({n * bbl} bbl) สถานะเริ่มหนัก", "alert")
        elif heavy < g["heavy"] and heavy == 0:
            add_event(st, "grid", ts, "dusty", f"สถานะเบาลง เหลือ {n} ชั้น")
        g["heavy"] = heavy
    g["last_price"] = p0
    g["held"] = sorted(held)
    day_for(int(now))

    price = s.price if s.price is not None else p0
    unreal = sum((price - L) * bbl for L in held)
    hist = [round(b[4], 2) for b in bars[-160:]]
    return {
        "label": C.GRID_LABEL, "symbol": s.symbol, "price": price, "prev_close": s.prev_close,
        "lo": g["lo"], "hi": g["hi"], "step": step, "bbl": bbl, "held": g["held"],
        "fills_today": g["day"]["fills"], "realized_today": g["day"]["realized"],
        "fills_total": g["fills_total"], "realized_total": g["realized_total"],
        "unrealized": unreal, "out": price < g["lo"] or price > g["hi"], "hist": hist,
        "equity": C.START_CAPITAL["grid"] + g["realized_total"] + unreal, "started": g["started"],
    }


# --------------------------------------------------------------------------
# Desk 3: Alpha (weekly momentum, recomputed from the start date each run)

def run_alpha(st: dict, series: dict[str, Series], now: float) -> tuple[dict, list[dict]]:
    a = st.setdefault("alpha", {})
    if "start" not in a:
        a["start"] = utc_date(now - C.ALPHA_BACKTEST_DAYS * 86400)
    start = a["start"]

    closes: dict[str, dict[str, float]] = {}
    for sym, s in series.items():
        closes[sym] = {utc_date(b[0]): b[4] for b in s.bars}
    cal = sorted({d for m in closes.values() for d in m})
    if not cal:
        return {}, []

    def daily_ret(sym: str) -> dict[str, float]:
        out, prev = {}, None
        for d in cal:
            c = closes[sym].get(d)
            if c is not None:
                out[d] = (c / prev - 1) if prev else 0.0
                prev = c
        return out

    rets = {sym: daily_ret(sym) for sym in closes}
    bench_w = {k: w for k, w in C.ALPHA_BENCHMARK.items() if k in rets}
    wsum = sum(bench_w.values()) or 1.0

    events: list[dict] = []

    def ev(ts: int, who: str, text: str, kind: str = "info") -> None:
        events.append({"id": f"alpha:{ts}:{len(events)}", "ts": ts, "desk": "alpha",
                       "who": who, "text": text, "kind": kind})

    pos: dict[str, dict] = {}
    closed: list[dict] = []
    port = bench = 1.0
    hist, excess, port_hist = [], [], []
    prev_week = None
    for i, d in enumerate(cal):
        if d < start:
            continue
        week = datetime.fromisoformat(d).isocalendar()[:2]
        if week != prev_week:
            prev_week = week
            moms = {}
            for sym in C.ALPHA_WATCHLIST:
                past = [closes[sym][x] for x in cal[:i] if x in closes.get(sym, {})]
                if len(past) > C.ALPHA_LOOKBACK:
                    moms[sym] = past[-1] / past[-C.ALPHA_LOOKBACK - 1] - 1
            picks = [s for s, m in sorted(moms.items(), key=lambda kv: -kv[1]) if m > 0][: C.ALPHA_TOP_N]
            ts = date_ts(d)
            for sym in [s for s in pos if s not in picks]:
                p = pos.pop(sym)
                r, br = (p["cum"] - 1) * 100, (p["bcum"] - 1) * 100
                hit = r > br
                closed.append({"sym": sym, "ret": r, "bench": br, "hit": hit})
                ev(ts, "kage", f"ปิด {sym} {r:+.1f}% (ตลาด {br:+.1f}%)", "hit" if hit else "miss")
            for k, sym in enumerate(s for s in picks if s not in pos):
                pos[sym] = {"entry": d, "cum": 1.0, "bcum": 1.0, "mom": moms[sym]}
                ev(ts + 60 + k * 120, "merlin", f"สัญญาณ LONG {sym} · โมเมนตัม {moms[sym] * 100:+.1f}%")
                ev(ts + 120 + k * 120, "kage", f"เข้า {sym} สัดส่วน 1/{C.ALPHA_TOP_N}")
        br = sum(rets[k].get(d, 0.0) * w for k, w in bench_w.items()) / wsum
        pr = (sum(rets[s].get(d, 0.0) for s in pos) / C.ALPHA_TOP_N) if pos else 0.0
        for sym, p in pos.items():
            p["cum"] *= 1 + rets[sym].get(d, 0.0)
            p["bcum"] *= 1 + br
        port *= 1 + pr
        bench *= 1 + br
        excess.append(pr - br)
        hist.append(round((port - bench) * 100, 3))
        port_hist.append(round((port - 1) * 100, 3))

    ir = None
    if len(excess) >= 20:
        m = sum(excess) / len(excess)
        sd = math.sqrt(sum((x - m) ** 2 for x in excess) / (len(excess) - 1))
        ir = (m / sd * math.sqrt(252)) if sd > 0 else None

    # Scout: today's big movers in the watchlist
    movers = []
    for sym in C.ALPHA_WATCHLIST:
        b = series.get(sym)
        if b and len(b.bars) >= 2:
            movers.append({"sym": sym, "chg": (b.bars[-1][4] / b.bars[-2][4] - 1) * 100,
                           "date": utc_date(b.bars[-1][0])})
    movers.sort(key=lambda m: -abs(m["chg"]))
    seen = a.setdefault("seen", {})
    for m in movers:
        if abs(m["chg"]) < C.ALPHA_MOVER_ALERT_PCT:
            break
        key = f"{m['sym']}:{m['date']}"
        if key not in seen:
            seen[key] = 1
            add_event(st, "alpha", now, "scout", f"{m['sym']} ขยับแรง {m['chg']:+.1f}% วันนี้",
                      "alert" if m["chg"] < 0 else "info")
    a["seen"] = dict(list(seen.items())[-60:])

    hits = sum(1 for c in closed if c["hit"])
    data = {
        "start": start, "alpha": hist[-1] if hist else 0.0,
        "port": (port - 1) * 100, "bench": (bench - 1) * 100,
        "hist": hist[-60:], "ir": ir, "hits": hits, "closed": len(closed),
        "holdings": [{"sym": s, "entry": p["entry"], "ret": (p["cum"] - 1) * 100} for s, p in pos.items()],
        "signals": sum(1 for e in events if e["who"] == "merlin"),
        "movers": movers[:3], "equity": C.START_CAPITAL["alpha"] * port,
        "bench_label": " + ".join(C.ALPHA_BENCHMARK),
    }
    return data, events[-EVENT_CAP:]

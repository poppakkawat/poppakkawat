"""Obsidian notes: one Markdown summary per day plus a hub note.

The daily note carries the day's numbers as YAML frontmatter (for Dataview)
and the day's events as a short list, so an AI reading the vault gets the
floor's state without parsing JSON or HTML.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from . import config as C

DASHBOARD_URL = "https://poppakkawat.github.io/poppakkawat/"
WHO = {"goldie": "Goldie", "penny": "Penny", "boss": "Rig Boss", "bot": "GridBot-7",
       "dusty": "Dusty", "merlin": "Merlin", "kage": "Kage", "scout": "Scout"}
DESK = {"roc": "Return on Cash", "grid": "Oil Grid", "alpha": "Alpha"}


def _local(ts: float) -> datetime:
    return datetime.fromtimestamp(ts + C.TZ_OFFSET_HOURS * 3600, timezone.utc)


def _usd(v: float, sign: bool = False) -> str:
    s = f"${abs(v):,.2f}"
    return (("-" if v < 0 else "+") + s) if sign else ("-" + s if v < 0 else s)


def daily_note(d: dict) -> tuple[str, str]:
    """Return (YYYY-MM-DD, markdown) for the day of ``d['updated']``."""
    now = _local(d["updated"])
    day = now.date().isoformat()
    h, r, g, a = d["hud"], d.get("roc") or {}, d.get("grid") or {}, d.get("alpha") or {}
    holdings = [x["sym"] for x in a.get("holdings", [])]
    fm = {
        "date": day,
        "updated": now.strftime("%Y-%m-%d %H:%M"),
        "mode": d.get("mode", "paper"),
        "equity": round(h["equity"], 2),
        "day_pnl": round(h["day_pnl"], 2),
        "mtd": round(h["mtd"], 2),
        "drawdown_pct": round(h["drawdown_pct"], 2),
        "tbill_rate": round(r.get("rate", 0), 3),
        "cash_interest_today": round(r.get("accrued_today", 0), 2),
        "wti": round(g.get("price", 0), 2),
        "grid_range": f"{g.get('lo', 0):.2f}-{g.get('hi', 0):.2f}",
        "grid_fills_today": g.get("fills_today", 0),
        "grid_realized_today": round(g.get("realized_today", 0), 2),
        "grid_held_levels": len(g.get("held", [])),
        "grid_out_of_range": bool(g.get("out")),
        "alpha_pct": round(a.get("alpha", 0), 2),
        "alpha_hit_rate": round(a["hits"] / a["closed"] * 100, 1) if a.get("closed") else None,
        "holdings": holdings,
    }
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            v = "[" + ", ".join(v) + "]"
        elif isinstance(v, bool):
            v = str(v).lower()
        elif v is None:
            v = ""
        lines.append(f"{k}: {v}")
    lines += ["tags: [trading-floor, paper]", "---", "",
              f"# Trading Floor · {day}", "",
              f"อัปเดต {fm['updated']} · ทุน {_usd(h['equity'])} · วันนี้ {_usd(h['day_pnl'], True)}"
              f" · เดือนนี้ {_usd(h['mtd'], True)} / เป้า {_usd(h['mtd_target'])}"
              f" · drawdown {h['drawdown_pct']:.2f}%", ""]
    if r:
        lines.append(f"- **Return on Cash:** {_usd(r['cash'])} @ T-Bill {r['rate']:.2f}%"
                     f" · ดอกเบี้ยวันนี้ {_usd(r['accrued_today'], True)} · สะสม {_usd(r['accrued_total'], True)}")
    if g:
        chg = f" ({g['price'] - g['prev_close']:+.2f})" if g.get("prev_close") else ""
        lines.append(f"- **Oil Grid:** {g['label']} ${g['price']:.2f}{chg} · กรอบ {fm['grid_range']}"
                     f"{' **หลุดกรอบ**' if g.get('out') else ''} · fills วันนี้ {g['fills_today']}"
                     f" · ปิดรอบ {_usd(g['realized_today'], True)} · ถือ {len(g['held'])} ชั้น"
                     f" ({len(g['held']) * g['bbl']} bbl) · ลอยตัว {_usd(g['unrealized'], True)}")
    if a:
        held = ", ".join(f"{x['sym']} {x['ret']:+.1f}%" for x in a.get("holdings", [])) or "เงินสด"
        lines.append(f"- **Alpha:** {a['alpha']:+.2f}% เหนือดัชนี (พอร์ต {a['port']:+.2f}%,"
                     f" ดัชนี {a['bench']:+.2f}%) · ถือ {held}")
    todays = [e for e in d.get("events", []) if _local(e["ts"]).date().isoformat() == day]
    lines += ["", "## เหตุการณ์วันนี้", ""]
    if todays:
        for e in todays[-25:]:
            lines.append(f"- {_local(e['ts']).strftime('%H:%M')} · {DESK.get(e['desk'], e['desk'])}"
                         f" · {WHO.get(e['who'], e['who'])}: {e['text']}")
    else:
        lines.append("- ไม่มีเหตุการณ์ใหม่")
    lines += ["", f"[[Trading Floor]] · [Dashboard]({DASHBOARD_URL})", ""]
    return day, "\n".join(lines)


HUB = f"""---
tags: [trading-floor]
---
# Trading Floor

Dashboard: {DASHBOARD_URL}
โค้ดและการตั้งค่า: `floor/config.py` ใน repo poppakkawat/poppakkawat

ระบบนี้อัปเดตเองทุก 30 นาทีบน GitHub Actions และเขียนสรุปลงโฟลเดอร์ `Daily/` วันละ 2 รอบ
(ราว 06:00 และ 18:00 เวลาไทย) ทุกพอร์ตเป็นเงินทดลอง (paper) บนราคาจริงจาก Yahoo Finance

## แผนก

| แผนก | ราคาจริง | กลยุทธ์ทดลอง |
|---|---|---|
| Return on Cash | T-Bill 13 สัปดาห์ (^IRX) | เงินสด {C.START_CAPITAL['roc']:,.0f} USD รับดอกเบี้ยตามอัตราจริง |
| Beta · Oil Grid | WTI (CL=F) แท่ง 5 นาที | Grid ซื้ออย่างเดียว ห่าง ${C.GRID_STEP:.2f} · {C.GRID_LEVELS_EACH_SIDE * 2 + 1} ชั้น · {C.GRID_BARRELS_PER_LEVEL} bbl/ชั้น |
| Alpha | หุ้น {len(C.ALPHA_WATCHLIST)} ตัว เทียบ {' + '.join(C.ALPHA_BENCHMARK)} | ถือ {C.ALPHA_TOP_N} ตัวที่โมเมนตัม {C.ALPHA_LOOKBACK} วันแรงสุด ปรับทุกสัปดาห์ |

## ตัวละคร

- **Goldie** · **Penny** — Return on Cash: ดอกเบี้ยและอัตรา T-Bill
- **Rig Boss** · **GridBot-7** · **Dusty** — Oil Grid: กรอบราคา คำสั่งซื้อขาย ขนาดสถานะ
- **Merlin** · **Kage** · **Scout** — Alpha: สัญญาณ การเข้าออก หุ้นที่ขยับแรง

## สรุปล่าสุด (ต้องมีปลั๊กอิน Dataview)

```dataview
TABLE equity, day_pnl, wti, grid_fills_today, grid_held_levels, alpha_pct, holdings
FROM #trading-floor
WHERE date
SORT date DESC
LIMIT 14
```

ไฟล์นี้สร้างครั้งเดียว แก้หรือจดโน้ตเพิ่มได้ ระบบจะไม่เขียนทับ
"""


def write_notes(d: dict, out_dir: str) -> str:
    os.makedirs(os.path.join(out_dir, "Daily"), exist_ok=True)
    day, md = daily_note(d)
    path = os.path.join(out_dir, "Daily", f"{day}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(out_dir, "Trading Floor.md"), "w", encoding="utf-8") as f:
        f.write(HUB)
    return path

"""Push the daily summary to Discord, Telegram, and/or email.

All channels are configured via environment variables so no secrets live
in the repo. Each sender is a no-op (with a warning) when its config is
missing, so partial setups still work.

    Discord:   DISCORD_WEBHOOK_URL
    Telegram:  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    Email:     SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASS,
               EMAIL_FROM, EMAIL_TO
"""

from __future__ import annotations

import json
import os
import smtplib
import sys
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText

from .analytics import Analysis

CHANNELS = ("discord", "telegram", "email")


def _money(x: float) -> str:
    if x >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"${x/1_000:.1f}K"
    return f"${x:,.0f}"


def build_summary(a: Analysis, window_label: str, signals=None) -> str:
    """A compact plain-text digest suitable for chat/email."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if a.count == 0:
        return f"Prediction Markets {day}: no notable trades in the {window_label}."

    flow = a.buy_usd - a.sell_usd
    bias = "net BUY" if flow >= 0 else "net SELL"
    out = [
        f"📈 Prediction Markets Daily — {day} ({window_label})",
        f"{a.count} notable trades · {_money(a.total_usd)} notional · "
        f"{bias} {_money(abs(flow))}",
        "",
        "Biggest trades:",
    ]
    tag = {"polymarket": "PM", "kalshi": "KX"}
    for t in a.top_trades[:5]:
        out.append(
            f"  • [{tag.get(t.venue, t.venue)}] {_money(t.usd)} {t.side} "
            f"{t.outcome} @ {t.price:.2f} — {t.title}"
        )

    if a.price_swings:
        out.append("")
        out.append("Biggest price swings:")
        for s in a.price_swings[:3]:
            arrow = "🔺" if s.delta >= 0 else "🔻"
            out.append(
                f"  • {arrow}{s.delta:+.2f} ({s.open_price:.2f}→{s.close_price:.2f}) "
                f"{s.outcome} — {s.title}"
            )

    if a.watchlist:
        out.append("")
        out.append("Watchlist activity:")
        for h in a.watchlist[:5]:
            out.append(f"  • {h.label}: {_money(h.usd)} across {len(h.trades)} trade(s)")

    if signals:
        from .signals import alignment
        flagged = [
            s for s in signals
            if any(
                alignment(s.yes_prob, sign, s.quotes.get(tk)) == "⚠️"
                for (tk, _, sign) in s.rule.instruments
            )
        ]
        if flagged:
            out.append("")
            out.append("⚠️ Possible cross-market edges (strong view, not priced in):")
            for s in flagged[:5]:
                names = ", ".join(
                    tk for (tk, _, sign) in s.rule.instruments
                    if alignment(s.yes_prob, sign, s.quotes.get(tk)) == "⚠️"
                )
                out.append(
                    f"  • {s.rule.label} {s.yes_prob:.0%} → watch {names} — {s.market_title}"
                )

    return "\n".join(out)


def _post_json(url: str, payload: dict, timeout: int = 20) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


def send_discord(text: str) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        print("discord: DISCORD_WEBHOOK_URL not set, skipping.", file=sys.stderr)
        return False
    # Discord messages cap at 2000 chars.
    _post_json(url, {"content": text[:1990]})
    print("discord: sent.", file=sys.stderr)
    return True


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        print("telegram: TELEGRAM_BOT_TOKEN/CHAT_ID not set, skipping.", file=sys.stderr)
        return False
    _post_json(
        f"https://api.telegram.org/bot{token}/sendMessage",
        {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True},
    )
    print("telegram: sent.", file=sys.stderr)
    return True


def send_email(text: str, subject: str | None = None) -> bool:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    sender = os.environ.get("EMAIL_FROM", user or "")
    recipient = os.environ.get("EMAIL_TO")
    if not (host and recipient):
        print("email: SMTP_HOST/EMAIL_TO not set, skipping.", file=sys.stderr)
        return False
    port = int(os.environ.get("SMTP_PORT", "587"))

    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = subject or (
        f"Prediction Markets Daily — {datetime.now(timezone.utc):%Y-%m-%d}"
    )
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        if user and password:
            server.login(user, password)
        server.sendmail(sender, [r.strip() for r in recipient.split(",")], msg.as_string())
    print("email: sent.", file=sys.stderr)
    return True


def notify(channels: list[str], text: str, dry_run: bool = False) -> None:
    """Dispatch ``text`` to each requested channel."""
    senders = {"discord": send_discord, "telegram": send_telegram, "email": send_email}
    for ch in channels:
        ch = ch.strip().lower()
        if ch not in senders:
            print(f"notify: unknown channel '{ch}', skipping.", file=sys.stderr)
            continue
        if dry_run:
            print(f"\n--- [dry-run] would send to {ch} ---\n{text}\n", file=sys.stderr)
            continue
        try:
            senders[ch](text)
        except Exception as e:  # never let a failed notification kill the run
            print(f"{ch}: failed to send: {e}", file=sys.stderr)

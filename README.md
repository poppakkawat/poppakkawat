# 📈 polytrack — Prediction Market Daily Trade Tracker

Daily updates and analytics of **interesting prediction-market trades** across
**Polymarket and Kalshi**. Pulls the day's notable trades from each venue's
public API, analyzes the flow, and writes a clean Markdown report — whales,
hot markets, top traders, price swings, and high-conviction bets.

- **Zero dependencies.** Pure Python 3 standard library.
- **No API key.** Uses Polymarket's and Kalshi's public data APIs.
- **Two venues.** Combine both, or focus on one with `--source`.
- **Trading edge.** Maps events to traditional instruments and flags
  divergences — where the crowd has conviction but the market hasn't moved.
- **Automatable.** Ships with a GitHub Action that posts a report every day.

## Quick start

```bash
# Both venues, last 24h of trades ≥ $5,000
python3 -m polytrack

# Just one venue
python3 -m polytrack --source polymarket
python3 -m polytrack --source kalshi --min 2000

# Bigger window / higher threshold, save to reports/YYYY-MM-DD.md
python3 -m polytrack --hours 12 --min 25000 --save

# Also dump the raw analysis as JSON
python3 -m polytrack --save --json latest.json
```

See [`reports/`](reports/) for an example of generated output.

## What counts as "interesting"?

The report surfaces several angles on the day's activity:

| Section | What it shows |
|---------|---------------|
| 📊 **Summary** | Total notional, trade count, and net buy/sell flow |
| 🧭 **Cross-Market Edge Signals** | Events mapped to stocks/ETFs/crypto, with divergence flags |
| 🧠 **Smart-Money Watchlist** | Every move (any size) from wallets you track |
| 🐳 **Biggest Trades** | The largest single trades by USD value |
| 🔥 **Hottest Markets** | Markets with the most money moving through them |
| 📈 **Biggest Price Swings** | Markets that *moved* the most (open→close), not just volume |
| 💸 **Most Active Traders** | Wallets deploying the most capital |
| 🎯 **High-Conviction Bets** | Large buys at extreme prices (longshots ≤0.15 or favorites ≥0.85) |

Trade USD value is `shares × price` (Polymarket prices are 0–1 probabilities).

## Options

```
--hours N          Look-back window in hours (default: 24)
--min USD          Minimum trade notional to include (default: 5000)
--top N            Rows per leaderboard (default: 10)
--save             Write to reports/YYYY-MM-DD.md
--out PATH         Explicit Markdown output path
--out-dir DIR      Write YYYY-MM-DD.md into DIR (created if needed)
--json PATH        Also write raw analysis as JSON
--max-trades N     Safety cap on Polymarket trades fetched (default: 5000)
--source V         Venue(s): polymarket | kalshi | both (default: both)
--kalshi-min USD   Min Kalshi trade notional (default: same as --min)
--no-edge          Skip the cross-market edge signals section
--edge-only        Print ONLY the cross-market edge signals
--watchlist PATH   Wallet watchlist JSON (default: watchlist.json if present)
--notify CHANNELS  Comma-separated: discord,telegram,email
--dry-run-notify   Print the notification text instead of sending
```

## 🧭 Cross-market edge signals

This is the "get an edge on traditional markets" engine. A prediction
market's price *is* the crowd's probability for an event — and many events
move tradeable instruments. polytrack maps them and flags **divergences**.

```bash
# Just the signals
python3 -m polytrack --edge-only --min 5000

# Signals are also a section in the full daily report (on by default)
python3 -m polytrack --save
```

**How it works**

1. Scan the fetched markets and match each against rule-based **themes**
   (rate cuts, recession, inflation, war/ceasefire, oil, Bitcoin, etc.).
2. Read the **implied probability** straight from the market price.
3. Map the event to instruments with a known directional relationship
   (e.g. *rate cut → bullish TLT/SPY/GLD*, *war → bullish oil/gold/defense,
   bearish SPY*, *BTC up → bullish COIN/MSTR/IBIT*).
4. Pull **live quotes** (Coinbase for crypto, Yahoo Finance for equities/
   ETFs/futures) and compare:
   - ✅ **confirms** — instrument is moving the way the crowd implies
   - ⚠️ **not priced in** — strong crowd view, instrument hasn't moved (the
     potential edge)
   - ▫ **no decisive view** — probability too close to a coin flip

Example row:

```
### PM · Bitcoin — implied 100% · ⚠️ 3 possibly unpriced
Will the price of Bitcoin be above $62,000 on June 18?

| Instrument        | Last    | Day    | Implied view | Read |
| Bitcoin (BTC)     | 62,609  | -4.86% | ↑ bullish    | ⚠️   |
| Coinbase (COIN)   | 163.69  | +2.03% | ↑ bullish    | ✅   |
| MicroStrategy     | 110.53  | -8.01% | ↑ bullish    | ⚠️   |
```

**Themes & mappings** live in [`polytrack/signals.py`](polytrack/signals.py)
(`RULES`) — add your own in a few lines. Directional reads only fire when
the market is decisive (≥60%) to avoid reading signal into coin flips.

> ⚠️ **Not financial advice.** This is research tooling. Prediction markets
> can be thin, biased, or wrong; correlations break; "not priced in" often
> means the market disagrees with the crowd for good reason. Size accordingly.

## 🏛️ Venues

| | Polymarket | Kalshi |
|---|---|---|
| API | `data-api.polymarket.com` | `api.elections.kalshi.com` |
| Trader identity | Wallet address (public) | Anonymous |
| Notional | `shares × price` | `contracts × price` |
| Watchlist support | ✅ | — (anonymous) |

Each trade in the report is tagged **PM** (Polymarket) or **KX** (Kalshi).
The summary shows a per-venue breakdown when both are included. The
**smart-money watchlist** is Polymarket-only because Kalshi trades carry no
trader identity. Kalshi has no server-side size filter, so polytrack pages
recent trades and filters by `--kalshi-min` client-side.

## 🧠 Smart-money watchlist

Track specific wallets and surface **every** move they make in the window —
even trades below the global threshold. Create a `watchlist.json` (see
[`watchlist.example.json`](watchlist.example.json)):

```json
{
  "0xf0318c32136c2db7fec88b84869aee6a1106c80c": "BreakTheBank",
  "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c": "GRIMDRIP"
}
```

```bash
python3 -m polytrack --watchlist watchlist.json
```

A list form (`[{"address": "0x...", "label": "..."}]`) also works. Your
personal `watchlist.json` is git-ignored; the `.example.json` is tracked.

## 📈 Price-swing detection

The **Biggest Price Swings** section flags markets whose price *moved* the
most over the window — computed as open→close (plus high/low range) from the
sampled trades per outcome. This catches markets that re-rated hard even if
their dollar volume wasn't the highest.

## 🔔 Push notifications

Send a compact daily digest to Discord, Telegram, and/or email. Configure via
environment variables (nothing secret in the repo):

| Channel | Environment variables |
|---------|-----------------------|
| Discord | `DISCORD_WEBHOOK_URL` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Email | `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO` |

```bash
# Preview the message without sending
python3 -m polytrack --dry-run-notify

# Send to specific channels
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python3 -m polytrack --notify discord
```

Missing config for a channel is skipped with a warning; a failed send never
aborts the run.

## Automated daily reports

**In the cloud:** the workflow in
[`.github/workflows/daily.yml`](.github/workflows/daily.yml) runs every day,
generates a fresh report, and commits it to `reports/`. It needs no secrets —
the data API is public. You can also trigger it manually from the Actions
tab, or adjust the schedule/threshold there.

**On your Windows PC → OneDrive:** see [`windows/`](windows/) for a one-command
setup that schedules a daily task and saves each report into your
`OneDrive\Prediction Market update` folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\setup_schedule.ps1
```

## Project layout

```
polytrack/
  client.py       # Polymarket data API client (stdlib urllib)
  kalshi.py       # Kalshi data API client (normalized to same Trade shape)
  analytics.py    # leaderboards, hot markets, price swings, conviction
  signals.py      # cross-market edge: theme rules + divergence detection
  market_data.py  # live crypto (Coinbase) + equity/ETF (Yahoo) quotes
  report.py       # Markdown report rendering (venue-aware)
  notify.py       # Discord / Telegram / email digests
  cli.py          # command-line interface
reports/          # generated daily reports
```

## Notes & limits

- The data API returns trades newest-first; we page back to the requested
  window. A safety cap (`--max-trades`) prevents runaway paging on busy days.
- This is informational only — **not financial advice.**

## Ideas to extend

- Track a watchlist of specific wallets ("smart money") and alert on their moves
- Detect price swings per market over the window, not just volume
- Post the daily summary to Discord/Telegram/email
- Add a sparkline of total volume over the past N days

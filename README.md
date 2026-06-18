# 📈 polytrack — Polymarket Daily Trade Tracker

Daily updates and analytics of **interesting Polymarket trades**. Pulls the
day's notable trades from Polymarket's public data API, analyzes the flow,
and writes a clean Markdown report — whales, hot markets, top traders, and
high-conviction bets.

- **Zero dependencies.** Pure Python 3 standard library.
- **No API key.** Uses Polymarket's public data API.
- **Automatable.** Ships with a GitHub Action that posts a report every day.

## Quick start

```bash
# Print a report for the last 24h of trades ≥ $5,000
python3 -m polytrack

# Bigger window / higher threshold
python3 -m polytrack --hours 12 --min 25000

# Save to reports/YYYY-MM-DD.md
python3 -m polytrack --save

# Also dump the raw analysis as JSON
python3 -m polytrack --save --json latest.json
```

See [`reports/`](reports/) for an example of generated output.

## What counts as "interesting"?

The report surfaces several angles on the day's activity:

| Section | What it shows |
|---------|---------------|
| 📊 **Summary** | Total notional, trade count, and net buy/sell flow |
| 🐳 **Biggest Trades** | The largest single trades by USD value |
| 🔥 **Hottest Markets** | Markets with the most money moving through them |
| 💸 **Most Active Traders** | Wallets deploying the most capital |
| 🎯 **High-Conviction Bets** | Large buys at extreme prices (longshots ≤0.15 or favorites ≥0.85) |

Trade USD value is `shares × price` (Polymarket prices are 0–1 probabilities).

## Options

```
--hours N        Look-back window in hours (default: 24)
--min USD        Minimum trade notional to include (default: 5000)
--top N          Rows per leaderboard (default: 10)
--save           Write to reports/YYYY-MM-DD.md
--out PATH       Explicit Markdown output path
--json PATH      Also write raw analysis as JSON
--max-trades N   Safety cap on trades fetched (default: 5000)
```

## Automated daily reports

The workflow in [`.github/workflows/daily.yml`](.github/workflows/daily.yml)
runs every day, generates a fresh report, and commits it to `reports/`.
It needs no secrets — the data API is public. You can also trigger it
manually from the Actions tab, or adjust the schedule/threshold there.

## Project layout

```
polytrack/
  client.py     # Polymarket data API client (stdlib urllib)
  analytics.py  # leaderboards, hot markets, conviction detection
  report.py     # Markdown report rendering
  cli.py        # command-line interface
reports/        # generated daily reports
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

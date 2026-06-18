# Daily report on Windows (→ OneDrive)

Run polytrack automatically every day and drop the dated report into
`C:\Users\<you>\OneDrive\Prediction Market update\`. OneDrive then syncs it
to your other devices.

## One-time setup

1. **Install Python 3** (if you don't have it): https://www.python.org/downloads/
   — tick *"Add python.exe to PATH"* during install. Verify in a terminal:
   ```
   py -3 --version
   ```

2. **Get the code** onto your PC (pick one):
   - `git clone <this repo>` , or
   - download the repo ZIP and extract it.

3. **(Optional) watchlist** — copy `watchlist.example.json` to
   `watchlist.json` in the repo root and add the wallets you want to track.
   The runner uses `watchlist.json` if present.

4. **Schedule it** — from the repo root in PowerShell:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\windows\setup_schedule.ps1
   ```
   Default time is 08:00. For a different time:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\windows\setup_schedule.ps1 -Time "07:30"
   ```

That's it. A file like `2026-06-18.md` will appear in the OneDrive folder
each day.

## Test it immediately

```powershell
Start-ScheduledTask -TaskName "Polytrack Daily Report"
```
or just double-click `windows\run_report.bat`.

## (Optional) push notifications

To also get a Discord/Telegram/email digest, set the relevant values as
**user environment variables** (Start → "Edit environment variables for your
account"), then add `--notify discord,telegram,email` to `run_report.bat`.
See the main README for the full variable list.

## Change settings

Edit `windows\run_report.bat` to tweak `--hours`, `--min`, `--kalshi-min`,
the output folder (`OUTDIR`), or which `--source` venues to include.

## Remove the schedule

```powershell
Unregister-ScheduledTask -TaskName "Polytrack Daily Report" -Confirm:$false
```

## Notes

- The output folder defaults to `%USERPROFILE%\OneDrive\Prediction Market update`,
  which resolves to `C:\Users\NITRO\OneDrive\Prediction Market update` on your
  machine. Edit `OUTDIR` in `run_report.bat` if your OneDrive path differs.
- The task runs only while you're logged in (no stored password needed). If
  the PC is off at the scheduled time, `-StartWhenAvailable` makes it run at
  the next opportunity.
- Needs internet access (Polymarket, Kalshi, Coinbase, Yahoo Finance).

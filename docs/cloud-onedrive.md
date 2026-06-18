# Daily report → OneDrive, fully in the cloud

This setup runs the report on **GitHub Actions every day** and uploads it
straight into your OneDrive folder using [rclone](https://rclone.org). No
computer of yours needs to be on — GitHub runs it, rclone delivers it.

The file lands at:

```
OneDrive / Prediction Market update / YYYY-MM-DD.md
```

which syncs to every device signed into that OneDrive (including
`C:\Users\NITRO\OneDrive\Prediction Market update`).

You do the rclone authorization **once** (it needs a browser), paste the
result into a GitHub secret, and you're done forever.

---

## Step 1 — Install rclone on any computer (one time)

- Windows: download from https://rclone.org/downloads/ (or `winget install Rclone.Rclone`)
- Mac: `brew install rclone`
- Linux: `curl https://rclone.org/install.sh | sudo bash`

## Step 2 — Connect rclone to your OneDrive

In a terminal:

```
rclone config
```

Then:

1. `n` → new remote
2. name: **`onedrive`**  (use this exact name, or set `RCLONE_REMOTE` later)
3. storage: type **`onedrive`** (Microsoft OneDrive)
4. `client_id` / `client_secret`: leave blank (press Enter)
5. region: `1` (Microsoft Cloud Global)
6. "Use auto config?" → **Yes** — a browser opens; sign in and approve
7. choose **OneDrive Personal** (or Business, whichever you use)
8. confirm the drive, then `y` to save, `q` to quit

Test it:

```
rclone lsd onedrive:
rclone mkdir "onedrive:Prediction Market update"
```

## Step 3 — Copy your rclone config

Print the full config:

```
rclone config show
```

It looks like:

```
[onedrive]
type = onedrive
token = {"access_token":"...","refresh_token":"...","expiry":"..."}
drive_id = ...
drive_type = personal
```

Copy the **entire** `[onedrive]` block (all lines).

## Step 4 — Add it as a GitHub secret

In your GitHub repo: **Settings → Secrets and variables → Actions → New
repository secret**.

| Secret name | Value |
|-------------|-------|
| `RCLONE_CONF` | the whole `[onedrive]` block from Step 3 |

Optional secrets (only if you changed defaults):

| Secret name | Default | Purpose |
|-------------|---------|---------|
| `RCLONE_REMOTE` | `onedrive` | the remote name you chose in Step 2 |
| `ONEDRIVE_DIR` | `Prediction Market update` | destination folder in OneDrive |

## Step 5 — Run it

- The workflow runs automatically every day (13:00 UTC).
- To test now: **Actions tab → "Daily Prediction Markets Report" → Run
  workflow**.

Within a minute the dated `.md` appears in your OneDrive folder and syncs to
your PCs.

---

## Notes & troubleshooting

- **Security:** `RCLONE_CONF` contains an OAuth refresh token. GitHub
  encrypts secrets, and Actions logs never print it. Treat it like a
  password; rotate by re-running `rclone config` and updating the secret.
- **If uploads start failing after a long idle period**, the refresh token
  may have expired. Re-run `rclone config reconnect onedrive:` (or redo
  Step 2), then update the `RCLONE_CONF` secret.
- **Change the time:** edit the `cron` line in
  [`.github/workflows/daily.yml`](../.github/workflows/daily.yml) (UTC).
- **Notifications too?** Add the Discord/Telegram/email secrets from the main
  README and you'll also get a daily digest.
- The report is also committed to `reports/` in the repo as a backup.

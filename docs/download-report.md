# Daily download report

`.github/workflows/download-report.yml` emails a summary of Cat Type downloads and website visits every day at 09:00 Singapore time (GitHub may start scheduled runs late).

## What the email shows

**Downloads** come from each GitHub release asset's `download_count`.

- Package downloads per platform since the previous run, plus the last 7 days compared with the 7 before.
- **New (estimated)**: package downloads minus `SHA256SUMS.txt` downloads. The in-app updater always fetches that checksum file before a package, and the website never links to it, so the difference approximates downloads by new people. Per-platform counts still include updates.
- Counts include downloads from the GitHub releases page and any bots.

**Website** numbers come from [GoatCounter](https://www.goatcounter.com), for the same period and for the last 7 days.

- Landing page visitors, download clicks per button and platform, the click rate (download clicks ÷ landing page visitors), and the top referrers.
- GoatCounter counts visitors, one per browser session, not raw page views. Ad blockers hide some visits.
- Click events are named `download-<placement>-<platform>`: placement `hero` (the main button and its "Intel Mac?" link) or `footer`, and platform `windows`, `mac-arm64` or `mac-intel`. `hero-see-platforms` is the main button on devices with no direct download, which only scrolls to the platform list.

GitHub only keeps running download totals, so every run appends a snapshot to `history.json` on the orphan `download-stats` branch and reports the change since the previous snapshot. The first run only records a baseline. A missed or failed run makes the next email cover the whole gap, because the snapshot is saved only after the email sends. If GoatCounter can't be reached, the email still goes out and says the website stats were unavailable.

## Setup

In the repository's **Settings → Secrets and variables → Actions**:

| Name | Kind | Value |
| --- | --- | --- |
| `SMTP_USERNAME` | Secret | The Gmail address that sends the report |
| `SMTP_PASSWORD` | Secret | A Gmail [app password](https://myaccount.google.com/apppasswords) |
| `GOATCOUNTER_CODE` | Variable | The GoatCounter site code, e.g. `cattype` for `cattype.goatcounter.com` |
| `GOATCOUNTER_TOKEN` | Secret | A GoatCounter API key that can read statistics |
| `REPORT_TO` | Variable (optional) | A different recipient address |

`GOATCOUNTER_CODE` also turns on the counting script: the **Landing page** workflow adds it to every page when the site is built. Without it, the site carries no analytics. After setting it, re-run **Landing page** to publish the script.

To use a mail provider other than Gmail, set repository variables `SMTP_HOST`, `SMTP_PORT` (implicit TLS, default 465) and `SMTP_FROM`.

To preview locally without emailing or saving: `python -m scripts.download_report --history build/history.json --dry-run`

## When the website stats are missing or zero

`scripts/goatcounter_check.py` sends the report's GoatCounter requests, plus simpler ones, and prints each status with GoatCounter's error or a summary of the counts. It checks whether the token is valid, whether it can see the site, whether the site has recorded any visits, and whether the report's hour-based queries behave differently from plain dates. It never prints the token.

- On GitHub: run the **GoatCounter check** workflow from the Actions tab. It uses the same `GOATCOUNTER_CODE` and `GOATCOUNTER_TOKEN`. The repository is public, so its log, with paths and counts, is too.
- Locally: `python -m scripts.goatcounter_check` asks for the API key, or reads `GOATCOUNTER_TOKEN`.

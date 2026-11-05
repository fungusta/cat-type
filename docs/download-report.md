# Daily download report

`.github/workflows/download-report.yml` emails a summary of Cat Type downloads every day at 09:00 Singapore time (GitHub may start scheduled runs late). It reads each release asset's `download_count` from the GitHub API. The website stays a static page with no analytics, so the privacy policy is unchanged.

## What the email shows

- Package downloads per platform since the previous run, plus the last 7 days compared with the 7 before.
- **New (estimated)**: package downloads minus `SHA256SUMS.txt` downloads. The in-app updater always fetches that checksum file before a package, and the website never links to it, so the difference approximates downloads by new people.
- Counts include downloads from the GitHub releases page and any bots. Nothing can tell which website button was used.

GitHub only keeps running totals, so every run appends a snapshot to `history.json` on the orphan `download-stats` branch and reports the change since the previous snapshot. The first run only records a baseline. A missed or failed run makes the next email cover the whole gap, because the snapshot is saved only after the email sends.

## Setup

1. Turn on 2-Step Verification for the Gmail account, then create an app password at <https://myaccount.google.com/apppasswords>.
2. In the repository's **Settings → Secrets and variables → Actions**, add secrets `SMTP_USERNAME` (the Gmail address) and `SMTP_PASSWORD` (the app password). Optionally add a variable `REPORT_TO` to send to a different address.
3. Run the **Download report** workflow once by hand (**Actions → Download report → Run workflow**) to record the baseline. Daily emails start the next morning.

Without the secrets, the workflow still records snapshots and shows the report in the run summary. To use a provider other than Gmail, set repository variables `SMTP_HOST`, `SMTP_PORT` (implicit TLS, default 465) and `SMTP_FROM`.

To preview locally without emailing or saving: `python -m scripts.download_report --history build/history.json --dry-run`

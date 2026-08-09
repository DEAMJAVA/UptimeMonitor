# Uptime Monitor

A self-hosted uptime monitoring app: Flask backend, `pymysqlhelper` for storage
(SQLite by default, MySQL optional), email/password accounts with email
verification, and a dark/red dashboard with historical filters, response-time
graphs, and per-monitor incident logs.

## Features

- Register / login with **email verification** (won't let you log in until verified)
- Create monitors with a **label**, URL, check interval, and a comma-separated
  list of **notification emails** — those addresses get emailed (with the
  monitor's label) whenever it goes down or comes back up
- **Pause / Resume** any monitor — paused monitors are skipped entirely by
  the checker (no checks, no incidents, no emails) and show a distinct
  "Paused" badge instead of a stale status
- Background checker thread pings every monitor on its own interval
- **Network-outage aware**: if a check fails, the checker also probes a
  couple of well-known "canary" URLs (configurable). If those fail too, the
  failure is assumed to be *our own* server/network losing connectivity —
  not the target actually being down — and gets logged as **"unmonitored"**
  instead of "down". No false incident, no false alert email, and that time
  is excluded from uptime % math (neither counted as up nor down)
- Per-monitor dashboard with range filters: **24h / 7d / 1m / 3m / 6m / 1y**
- Analytics per range: current status, uptime % (correctly scoped to only
  the time actually monitored — a brand-new monitor won't falsely show
  ~100% on a "1 year" view), total downtime, longest single downtime, total
  incidents
- Average response-time line chart (Chart.js)
- **Uptime History** bar strip — one bar per time slice, colored up
  (green) / partial (orange) / down (red) / unmonitored (blue) / no data
  (gray), with hover tooltips
- Full incident list (start, end, duration, status) for the selected range
- Dark theme with red accents, responsive down to mobile widths
- .env-driven configuration, with `.env.example` included

## Setup

1. **Create a virtual environment and install dependencies**

   ```bash
   cd uptime_monitor
   python3 -m venv venv
   source venv/bin/activate        # on Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables**

   ```bash
   cp .env.example .env
   ```

   Then edit `.env`:
   - Set `APP_MASTER_KEY` to a long random string (used to sign sessions).
   - Leave `DB_TYPE=sqlite` for the simplest setup, or switch to `mysql` and
     fill in `DB_HOST` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` (create that
     database first — the app creates tables, not the database itself).
   - Fill in `MAIL_SERVER` / `MAIL_USERNAME` / `MAIL_PASSWORD` for a real SMTP
     account so verification and status emails actually send. If you leave
     these blank, the app still works — emails are just printed to the
     console instead of sent (handy for local testing).
   - Set `APP_BASE_URL` to wherever the app is actually reachable, so
     verification links in emails point to the right place.

3. **Run it**

   ```bash
   python app.py
   ```

   Visit `http://localhost:5000`, register an account, verify via the emailed
   link (or console log if SMTP isn't configured), log in, and add a monitor.

## How monitoring works

A background thread wakes up every `CHECK_TICK_SECONDS` and checks any
monitor whose `interval_seconds` has elapsed since its last check (paused
monitors are skipped entirely). Each check records a row (`status`,
`response_time_ms`, `status_code`). Status is one of:

- **up** — the URL responded with a 2xx/3xx status
- **down** — the request failed, and a canary check (see below) confirmed
  our own server has internet access — so the failure is genuinely the
  target's fault
- **unmonitored** — the request failed AND the canary check also failed —
  we can't tell if the target is actually down, so this is logged as a
  monitoring gap rather than an outage. No incident is opened, no email is
  sent, and this time is excluded from the uptime % calculation entirely.

When a monitor's status flips between up and down:

- An **incident** row is opened (on down) or closed (on up).
- If the monitor has notification emails set, everyone on that list gets an
  email naming the monitor's **label**, its URL, the new status, and the time.

The very first check of a brand-new monitor never sends an email (there's no
real "transition" yet — it's just coming online).

### Canary / network-outage detection

Configured via `.env`:

```
CANARY_URLS=https://www.google.com,https://1.1.1.1
CANARY_TIMEOUT_SECONDS=5
```

When a monitor check fails, the checker tries each canary URL with a HEAD
request. If any canary responds, the checker trusts that our own network is
fine and marks the check "down". If all canaries fail too, it assumes the
problem is on our end and marks the check "unmonitored" instead. Adjust the
canary list if `google.com`/`1.1.1.1` aren't reachable from your network.

## Notes on switching to MySQL

Create the database first (e.g. `CREATE DATABASE uptime_monitor;`), then set:

```
DB_TYPE=mysql
DB_HOST=your-host
DB_PORT=3306
DB_USER=your-user
DB_PASSWORD=your-password
DB_NAME=uptime_monitor
```

The app uses the same table-definition code either way — `pymysqlhelper`
handles the SQLite/MySQL differences internally.

## Project structure

```
uptime_monitor/
├── app.py            # Flask app factory / entry point
├── config.py         # loads settings from .env
├── extensions.py      # pymysqlhelper database instance
├── models.py          # table schema + id/timestamp helpers
├── auth.py            # register/login/logout/email verification
├── monitors.py        # dashboard, monitor CRUD, analytics JSON API
├── checker.py          # background thread that pings monitors
├── emailer.py          # SMTP sending (verification + status emails)
├── templates/          # Jinja2 templates (dark/red themed)
├── static/css/style.css
├── static/js/dashboard.js   # range filters, chart, incidents rendering
├── requirements.txt
└── .env.example
```

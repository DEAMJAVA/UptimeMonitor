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
- Background checker thread pings every monitor on its own interval
- Per-monitor dashboard with range filters: **24h / 7d / 1m / 3m / 6m / 1y**
- Analytics per range: current status, uptime %, total downtime, longest
  single downtime, total incidents
- Average response-time line chart (Chart.js)
- Full incident list (start, end, duration, status) for the selected range
- Dark theme with red accents throughout

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
monitor whose `interval_seconds` has elapsed since its last check. Each
check records a row (`status`, `response_time_ms`, `status_code`). When a
monitor's status flips (up→down or down→up):

- An **incident** row is opened (on down) or closed (on up back).
- If the monitor has notification emails set, everyone on that list gets an
  email naming the monitor's **label**, its URL, the new status, and the time.

The very first check of a brand-new monitor never sends an email (there's no
real "transition" yet — it's just coming online).

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

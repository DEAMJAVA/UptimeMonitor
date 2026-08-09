import threading
import time

import requests

from config import Config
from extensions import db
from models import new_id, now_ts
from emailer import send_status_email

_started = False
_start_lock = threading.Lock()


def parse_emails(raw):
    if not raw:
        return []
    return [e.strip() for e in raw.split(",") if e.strip()]


def _network_reachable():
    """Best-effort check for whether *our* server has internet access at all.
    Used to tell 'the monitored site is down' apart from 'our own network/DNS
    is the thing that's broken right now' before ever recording a check."""
    for canary_url in Config.CANARY_URLS:
        try:
            requests.head(canary_url, timeout=Config.CANARY_TIMEOUT_SECONDS)
            return True
        except requests.RequestException:
            continue
    return False


def check_monitor(monitor):
    """Ping a single monitor's URL, record the result, and react to any
    up/down transition (incident bookkeeping + notification emails).

    Three possible outcomes per check:
      - "up"          the URL responded with a 2xx/3xx status
      - "down"        the request failed AND our own network is reachable
                       (so the failure is genuinely the target's fault)
      - "unmonitored" the request failed AND our own network is unreachable
                       too — we can't tell if the target is actually down,
                       so this period is recorded as a monitoring gap, not
                       an outage.
    """
    url = monitor["url"]
    prev_status = monitor.get("current_status") or "unknown"

    started = time.time()
    status = "down"
    status_code = None
    try:
        resp = requests.get(url, timeout=Config.REQUEST_TIMEOUT_SECONDS)
        status_code = resp.status_code
        status = "up" if 200 <= resp.status_code < 400 else "down"
    except requests.RequestException:
        status = "down" if _network_reachable() else "unmonitored"

    response_time_ms = int((time.time() - started) * 1000) if status != "unmonitored" else None
    ts = now_ts()

    db.insert(
        "checks",
        id=new_id(),
        monitor_id=monitor["id"],
        timestamp=ts,
        status=status,
        response_time_ms=response_time_ms,
        status_code=status_code,
    )

    db.update(
        "monitors",
        filters={"id": monitor["id"]},
        updates={"current_status": status, "last_checked_at": ts},
    )

    if status != prev_status:
        _handle_status_change(monitor, prev_status, status, ts)


def _handle_status_change(monitor, prev_status, new_status, ts):
    # A monitoring gap (our own network was down) is neither an "up" nor a
    # "down" event for the target — don't touch incidents or send email.
    if new_status == "unmonitored":
        return

    if new_status == "down":
        # Avoid opening a second overlapping incident if one is already
        # ongoing (e.g. down -> unmonitored -> down while still broken).
        already_ongoing = db.search("incidents", monitor_id=monitor["id"], status="ongoing")
        if not already_ongoing:
            db.insert(
                "incidents",
                id=new_id(),
                monitor_id=monitor["id"],
                started_at=ts,
                ended_at=None,
                duration_seconds=None,
                status="ongoing",
            )
    elif new_status == "up":
        ongoing = db.search("incidents", monitor_id=monitor["id"], status="ongoing")
        for inc in ongoing:
            duration = ts - inc["started_at"]
            db.update(
                "incidents",
                filters={"id": inc["id"]},
                updates={"ended_at": ts, "duration_seconds": duration, "status": "resolved"},
            )

    # Don't email on the very first real check (prev_status == "unknown") —
    # that's not a real transition, just the monitor coming online for the
    # first time.
    if prev_status == "unknown":
        return

    emails = parse_emails(monitor.get("notify_emails"))
    if emails:
        send_status_email(emails, monitor["label"], monitor["url"], new_status, ts)


def _loop():
    while True:
        try:
            monitors = db.search("monitors")
            now = now_ts()
            for m in monitors:
                if m.get("is_paused"):
                    continue
                interval = m.get("interval_seconds") or 60
                last = m.get("last_checked_at") or 0
                if now - last >= interval:
                    check_monitor(m)
        except Exception as exc:  # noqa: BLE001 - keep the loop alive
            print(f"[checker error] {exc}")
        time.sleep(Config.CHECK_TICK_SECONDS)


def start_background_checker():
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
        thread = threading.Thread(target=_loop, daemon=True, name="uptime-checker")
        thread.start()

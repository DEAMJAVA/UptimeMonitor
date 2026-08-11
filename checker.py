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
    for canary_url in Config.CANARY_URLS:
        try:
            requests.head(canary_url, timeout=Config.CANARY_TIMEOUT_SECONDS)
            return True
        except requests.RequestException:
            continue
    return False


def check_monitor(monitor):
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
    if new_status == "unmonitored":
        return

    downtime_seconds = None

    if new_status == "down":
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
        downtime_seconds = 0
        for inc in ongoing:
            duration = ts - inc["started_at"]
            downtime_seconds += duration
            db.update(
                "incidents",
                filters={"id": inc["id"]},
                updates={"ended_at": ts, "duration_seconds": duration, "status": "resolved"},
            )

    if prev_status == "unknown":
        return

    emails = parse_emails(monitor.get("notify_emails"))
    if emails:
        dashboard_url = f"{Config.APP_BASE_URL}/monitors/{monitor['id']}"
        send_status_email(
            emails,
            monitor["label"],
            monitor["url"],
            new_status,
            ts,
            dashboard_url,
            downtime_seconds=downtime_seconds,
        )


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
        except Exception as exc:
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
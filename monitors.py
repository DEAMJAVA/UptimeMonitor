import bisect

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import text

from extensions import db
from models import new_id, now_ts

monitors_bp = Blueprint("monitors", __name__)

# range key -> window length in seconds
RANGE_SECONDS = {
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
    "1m": 30 * 24 * 3600,
    "3m": 90 * 24 * 3600,
    "6m": 180 * 24 * 3600,
    "1y": 365 * 24 * 3600,
}
RANGE_LABELS = {
    "24h": "24 Hours",
    "7d": "7 Days",
    "1m": "1 Month",
    "3m": "3 Months",
    "6m": "6 Months",
    "1y": "1 Year",
}

INTERVAL_CHOICES = [
    (30, "30 seconds"),
    (60, "1 minute"),
    (300, "5 minutes"),
    (900, "15 minutes"),
    (1800, "30 minutes"),
    (3600, "1 hour"),
]


def get_owned_monitor(monitor_id):
    m = db.get("monitors", id=monitor_id)
    if not m or m["user_id"] != current_user.id:
        return None
    return m


@monitors_bp.route("/")
@login_required
def dashboard():
    monitors = db.search("monitors", user_id=current_user.id)
    monitors.sort(key=lambda m: m.get("created_at") or 0, reverse=True)
    return render_template("dashboard.html", monitors=monitors)


@monitors_bp.route("/monitors/new", methods=["GET", "POST"])
@login_required
def new_monitor():
    if request.method == "POST":
        label = request.form.get("label", "").strip()
        url = request.form.get("url", "").strip()
        interval = int(request.form.get("interval_seconds") or 60)
        notify_emails = request.form.get("notify_emails", "").strip()

        if not label or not url:
            flash("Label and URL are required.", "error")
            return render_template("monitor_form.html", mode="new", interval_choices=INTERVAL_CHOICES)

        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        db.insert(
            "monitors",
            id=new_id(),
            user_id=current_user.id,
            label=label,
            url=url,
            interval_seconds=interval,
            notify_emails=notify_emails,
            current_status="unknown",
            last_checked_at=0,
            created_at=now_ts(),
        )
        flash(f'Monitor "{label}" created.', "success")
        return redirect(url_for("monitors.dashboard"))

    return render_template("monitor_form.html", mode="new", interval_choices=INTERVAL_CHOICES)


@monitors_bp.route("/monitors/<monitor_id>")
@login_required
def monitor_detail(monitor_id):
    m = get_owned_monitor(monitor_id)
    if not m:
        flash("Monitor not found.", "error")
        return redirect(url_for("monitors.dashboard"))
    return render_template(
        "monitor_detail.html",
        monitor=m,
        ranges=list(RANGE_SECONDS.keys()),
        range_labels=RANGE_LABELS,
    )


@monitors_bp.route("/monitors/<monitor_id>/settings", methods=["GET", "POST"])
@login_required
def monitor_settings(monitor_id):
    m = get_owned_monitor(monitor_id)
    if not m:
        flash("Monitor not found.", "error")
        return redirect(url_for("monitors.dashboard"))

    if request.method == "POST":
        label = request.form.get("label", "").strip()
        url = request.form.get("url", "").strip()
        interval = int(request.form.get("interval_seconds") or 60)
        notify_emails = request.form.get("notify_emails", "").strip()

        if not label or not url:
            flash("Label and URL are required.", "error")
            return render_template("monitor_form.html", mode="edit", monitor=m, interval_choices=INTERVAL_CHOICES)

        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        db.update(
            "monitors",
            filters={"id": monitor_id},
            updates={
                "label": label,
                "url": url,
                "interval_seconds": interval,
                "notify_emails": notify_emails,
            },
        )
        flash("Monitor updated.", "success")
        return redirect(url_for("monitors.monitor_detail", monitor_id=monitor_id))

    return render_template("monitor_form.html", mode="edit", monitor=m, interval_choices=INTERVAL_CHOICES)


@monitors_bp.route("/monitors/<monitor_id>/delete", methods=["POST"])
@login_required
def delete_monitor(monitor_id):
    m = get_owned_monitor(monitor_id)
    if not m:
        flash("Monitor not found.", "error")
        return redirect(url_for("monitors.dashboard"))

    db.delete("checks", monitor_id=monitor_id)
    db.delete("incidents", monitor_id=monitor_id)
    db.delete("monitors", id=monitor_id)
    flash(f'Monitor "{m["label"]}" deleted.', "success")
    return redirect(url_for("monitors.dashboard"))


HISTORY_BAR_COUNT = 90


def _build_history_bars(checks, incidents, monitor_created_at, start, now):
    """Split [start, now] into fixed-size slices and classify each one as
    nodata / up / partial / down, for the status-bar strip on the detail page."""
    window = now - start
    if window <= 0:
        return []

    bucket_size = max(1, window / HISTORY_BAR_COUNT)

    # checks are sorted ascending by timestamp (from the SQL query), so we can
    # use binary search to test "is there monitoring data in this slice"
    # instead of rescanning the whole list per bucket.
    timestamps = [c["timestamp"] for c in checks]

    bars = []
    for i in range(HISTORY_BAR_COUNT):
        b_start = start + i * bucket_size
        b_end = start + (i + 1) * bucket_size
        b_end = min(b_end, now)
        bucket_duration = max(0.0, b_end - b_start)

        lo = bisect.bisect_left(timestamps, b_start)
        hi = bisect.bisect_left(timestamps, b_end)
        has_checks = hi > lo

        down_overlap = 0.0
        for inc in incidents:
            inc_end = inc["ended_at"] if inc["ended_at"] is not None else now
            o_start = max(inc["started_at"], b_start)
            o_end = min(inc_end, b_end)
            if o_end > o_start:
                down_overlap += o_end - o_start

        if b_end <= monitor_created_at or bucket_duration <= 0:
            state = "nodata"
        elif not has_checks and down_overlap <= 0:
            state = "nodata"
        elif down_overlap <= 0:
            state = "up"
        elif down_overlap >= bucket_duration * 0.9:
            state = "down"
        else:
            state = "partial"

        bars.append(
            {
                "start": int(b_start),
                "end": int(b_end),
                "state": state,
                "down_fraction": round(down_overlap / bucket_duration, 3) if bucket_duration else 0,
            }
        )

    return bars


@monitors_bp.route("/api/monitors/<monitor_id>/data")
@login_required
def monitor_data(monitor_id):
    m = get_owned_monitor(monitor_id)
    if not m:
        return jsonify({"error": "not found"}), 404

    range_key = request.args.get("range", "24h")
    window = RANGE_SECONDS.get(range_key, RANGE_SECONDS["24h"])
    now = now_ts()
    start = now - window

    with db.engine.connect() as conn:
        check_rows = conn.execute(
            text(
                "SELECT timestamp, response_time_ms, status FROM checks "
                "WHERE monitor_id = :mid AND timestamp >= :start ORDER BY timestamp ASC"
            ),
            {"mid": monitor_id, "start": start},
        ).mappings().all()

        incident_rows = conn.execute(
            text(
                "SELECT id, started_at, ended_at, duration_seconds, status FROM incidents "
                "WHERE monitor_id = :mid AND started_at <= :now "
                "AND (ended_at IS NULL OR ended_at >= :start) "
                "ORDER BY started_at DESC"
            ),
            {"mid": monitor_id, "start": start, "now": now},
        ).mappings().all()

    checks = [dict(c) for c in check_rows]
    incidents = [dict(i) for i in incident_rows]

    # Only count uptime % against the portion of the selected window the
    # monitor actually existed for — otherwise a brand-new monitor with zero
    # downtime so far would show ~100% on a "24h" or "1y" view it has no
    # data for yet.
    monitor_created_at = m.get("created_at") or now
    effective_start = max(start, monitor_created_at)
    monitored_seconds = max(0, now - effective_start)

    total_downtime = 0
    longest_downtime = 0
    incidents_started_in_window = 0
    for inc in incidents:
        overlap_start = max(inc["started_at"], start)
        overlap_end = min(inc["ended_at"] if inc["ended_at"] is not None else now, now)
        duration = max(0, overlap_end - overlap_start)
        total_downtime += duration
        longest_downtime = max(longest_downtime, duration)
        if inc["started_at"] >= start:
            incidents_started_in_window += 1

    uptime_pct = (
        max(0.0, min(100.0, 100.0 - (total_downtime / monitored_seconds * 100)))
        if monitored_seconds > 0
        else None
    )

    # bucket average response time into ~60 points across the window
    bucket_count = 60
    bucket_size = max(1, window // bucket_count)
    buckets = {}
    for c in checks:
        if c["response_time_ms"] is None:
            continue
        idx = (c["timestamp"] - start) // bucket_size
        buckets.setdefault(idx, []).append(c["response_time_ms"])

    response_series = []
    for idx in sorted(buckets.keys()):
        vals = buckets[idx]
        bucket_ts = start + idx * bucket_size
        response_series.append(
            {"timestamp": bucket_ts, "avg_response_ms": round(sum(vals) / len(vals), 1)}
        )

    incidents_out = [
        {
            "id": i["id"],
            "started_at": i["started_at"],
            "ended_at": i["ended_at"],
            "duration_seconds": i["duration_seconds"],
            "status": i["status"],
        }
        for i in incidents
    ]

    history = _build_history_bars(checks, incidents, m.get("created_at") or 0, start, now)

    return jsonify(
        {
            "current_status": m["current_status"],
            "uptime_pct": round(uptime_pct, 3) if uptime_pct is not None else None,
            "total_downtime_seconds": total_downtime,
            "longest_downtime_seconds": longest_downtime,
            "total_incidents": incidents_started_in_window,
            "response_series": response_series,
            "incidents": incidents_out,
            "history": history,
            "window_seconds": window,
            "monitored_seconds": monitored_seconds,
            "server_now": now,
        }
    )

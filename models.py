import time
import uuid

from sqlalchemy import Integer, String, Text

from extensions import db


def new_id():
    return uuid.uuid4().hex


def now_ts():
    return int(time.time())


def init_db():
    db.define_table(
        "users",
        id=String(32),
        email=String(255),
        password_hash=String(255),
        name=String(120),
        is_verified=Integer,
        verification_token=String(64),
        created_at=Integer,
    )

    db.define_table(
        "monitors",
        id=String(32),
        user_id=String(32),
        label=String(120),
        url=String(500),
        interval_seconds=Integer,
        notify_emails=Text,
        current_status=String(20),
        is_paused=Integer,
        last_checked_at=Integer,
        created_at=Integer,
    )

    db.define_table(
        "checks",
        id=String(32),
        monitor_id=String(32),
        timestamp=Integer,
        status=String(20),
        response_time_ms=Integer,
        status_code=Integer,
    )

    db.define_table(
        "incidents",
        id=String(32),
        monitor_id=String(32),
        started_at=Integer,
        ended_at=Integer,
        duration_seconds=Integer,
        status=String(20),
    )

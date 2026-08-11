import os
from dotenv import load_dotenv

load_dotenv()


def _int(name, default):
    val = os.environ.get(name)
    try:
        return int(val) if val not in (None, "") else default
    except ValueError:
        return default


def _bool(name, default):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("APP_MASTER_KEY", "change-this-to-a-random-secret")
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = _int("PORT", 5000)
    DEBUG = _bool("DEBUG", False)
    APP_BASE_URL = os.environ.get("APP_BASE_URL", f"http://localhost:{PORT}")

    DB_TYPE = os.environ.get("DB_TYPE", "sqlite").strip().lower()  # sqlite | mysql
    DB_PATH = os.environ.get("DB_PATH", "uptime_monitor.db")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = _int("DB_PORT", 3306)
    DB_USER = os.environ.get("DB_USER", "")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "uptime_monitor")

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = _int("MAIL_PORT", 587)
    MAIL_USE_TLS = _bool("MAIL_USE_TLS", True)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "") or MAIL_USERNAME

    CHECK_TICK_SECONDS = _int("CHECK_TICK_SECONDS", 5)
    REQUEST_TIMEOUT_SECONDS = _int("REQUEST_TIMEOUT_SECONDS", 10)

    _canary_raw = os.environ.get("CANARY_URLS", "https://www.google.com,https://1.1.1.1")
    CANARY_URLS = [u.strip() for u in _canary_raw.split(",") if u.strip()]
    CANARY_TIMEOUT_SECONDS = _int("CANARY_TIMEOUT_SECONDS", 5)

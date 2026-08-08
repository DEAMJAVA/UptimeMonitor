import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import Config


def send_email(to_addrs, subject, html_body):
    """Send an HTML email. If SMTP isn't configured, log to console instead
    of failing, so the rest of the app keeps working in local/dev setups."""
    if not to_addrs:
        return

    if not Config.MAIL_SERVER or not Config.MAIL_USERNAME:
        print(f"[email suppressed - no SMTP configured] to={to_addrs} subject={subject!r}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = Config.MAIL_DEFAULT_SENDER
    msg["To"] = ", ".join(to_addrs)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=15) as server:
            if Config.MAIL_USE_TLS:
                server.starttls()
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.sendmail(Config.MAIL_DEFAULT_SENDER, to_addrs, msg.as_string())
    except Exception as exc:  # noqa: BLE001 - never let email errors break requests
        print(f"[email error] {exc}")


def send_verification_email(to_email, name, token):
    link = f"{Config.APP_BASE_URL}/verify/{token}"
    html = f"""
    <div style="font-family:Arial,sans-serif;background:#0d0d0f;color:#eaeaea;padding:28px;border-radius:8px">
      <h2 style="color:#e63946;margin-top:0">Verify your email</h2>
      <p>Hi {name},</p>
      <p>Thanks for creating an Uptime Monitor account. Please confirm your email address to activate it.</p>
      <p style="margin:24px 0">
        <a href="{link}" style="background:#e63946;color:#ffffff;padding:12px 22px;
           text-decoration:none;border-radius:6px;font-weight:bold;display:inline-block">
           Verify Email
        </a>
      </p>
      <p style="color:#999;font-size:13px">Or copy and paste this link into your browser:<br>{link}</p>
    </div>
    """
    send_email([to_email], "Verify your Uptime Monitor account", html)


def send_status_email(to_emails, monitor_label, monitor_url, new_status, at_ts):
    when = datetime.datetime.utcfromtimestamp(at_ts).strftime("%Y-%m-%d %H:%M:%S UTC")
    color = "#e63946" if new_status == "down" else "#2ecc71"
    subject = f"[{monitor_label}] is {new_status.upper()}"
    html = f"""
    <div style="font-family:Arial,sans-serif;background:#0d0d0f;color:#eaeaea;padding:28px;border-radius:8px">
      <h2 style="color:{color};margin-top:0">{monitor_label} is now {new_status.upper()}</h2>
      <table style="color:#eaeaea;font-size:14px">
        <tr><td style="padding:4px 12px 4px 0;color:#999">Monitor</td><td>{monitor_label}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#999">URL</td><td>{monitor_url}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#999">Status</td><td style="color:{color};font-weight:bold">{new_status.upper()}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#999">Time</td><td>{when}</td></tr>
      </table>
    </div>
    """
    send_email(to_emails, subject, html)

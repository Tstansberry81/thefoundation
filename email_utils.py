"""Email + token helpers for the Meet You There Foundation site.

Verification uses an itsdangerous signed, time-limited token — no extra column
needed to store it. Sending uses stdlib smtplib over Gmail-style SMTP.

If MAIL_USERNAME / MAIL_PASSWORD are not configured, real sending is skipped and
the caller is expected to surface the link in dev (see app.py). This lets the
whole flow be tested locally before SMTP credentials exist.
"""
import smtplib
import ssl
from email.message import EmailMessage

import certifi
from flask import current_app
from itsdangerous import URLSafeTimedSerializer

_SALT = "email-verify"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)


def generate_token(email: str) -> str:
    """Create a signed token that encodes the email address."""
    return _serializer().dumps(email)


def confirm_token(token: str, max_age: int | None = None) -> str:
    """Return the email encoded in the token, or raise if invalid/expired."""
    if max_age is None:
        max_age = current_app.config.get("EMAIL_TOKEN_MAX_AGE", 86400)
    return _serializer().loads(token, max_age=max_age)


def mail_is_configured() -> bool:
    cfg = current_app.config
    return bool(cfg.get("MAIL_USERNAME") and cfg.get("MAIL_PASSWORD"))


def send_email(
    to: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    reply_to: str | None = None,
) -> bool:
    """Send an email. Returns True if actually sent, False if mail isn't configured.

    Raises on genuine SMTP errors so callers can decide how to react.
    """
    cfg = current_app.config
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["MAIL_SENDER"]
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if not mail_is_configured():
        current_app.logger.warning(
            "MAIL not configured — skipping real send of %r to %s", subject, to
        )
        return False

    # Use certifi's CA bundle so TLS verification works even when the Python
    # build can't see the system certificate store (common on macOS).
    context = ssl.create_default_context(cafile=certifi.where())
    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=20) as server:
        if cfg.get("MAIL_USE_TLS"):
            server.starttls(context=context)
        server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        server.send_message(msg)
    current_app.logger.info("Sent %r to %s", subject, to)
    return True

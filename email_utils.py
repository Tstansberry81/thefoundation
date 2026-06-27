"""Email + token helpers for the Meet You There Foundation site.

Verification uses an itsdangerous signed, time-limited token — no extra column
needed to store it.

Two sending backends:
  * SendGrid HTTPS API (port 443) — used when SENDGRID_API_KEY is set. This is
    the reliable path on cloud hosts like Render, which block outbound SMTP.
  * SMTP (smtplib) — fallback for local/dev or non-SendGrid SMTP servers.

If neither is configured, sending is skipped and the caller surfaces the link in
dev mode (see app.py).
"""
import json
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr

import certifi
from email_validator import EmailNotValidError, validate_email
from flask import current_app
from itsdangerous import URLSafeTimedSerializer

_SALT = "email-verify"


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def generate_token(email: str, salt: str = _SALT) -> str:
    """Create a signed token that encodes the email address.

    A distinct ``salt`` namespaces tokens so, e.g., a verification token can
    never be replayed as a password-reset token.
    """
    return _serializer(salt).dumps(email)


def confirm_token(token: str, max_age: int | None = None, salt: str = _SALT) -> str:
    """Return the email encoded in the token, or raise if invalid/expired."""
    if max_age is None:
        max_age = current_app.config.get("EMAIL_TOKEN_MAX_AGE", 86400)
    return _serializer(salt).loads(token, max_age=max_age)


def normalize_email(email: str) -> str | None:
    """Validate and canonicalize an email address.

    Returns the normalized address, or None if it isn't a valid email. Uses
    email-validator (already a dependency) without doing network DNS checks.
    """
    try:
        result = validate_email(email, check_deliverability=False)
        return result.normalized.lower()
    except EmailNotValidError:
        return None


def mail_is_configured() -> bool:
    cfg = current_app.config
    if cfg.get("SENDGRID_API_KEY"):
        return True
    return bool(cfg.get("MAIL_USERNAME") and cfg.get("MAIL_PASSWORD"))


def send_email(
    to: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    reply_to: str | None = None,
) -> bool:
    """Send an email. Returns True if sent, False if mail isn't configured.

    Prefers the SendGrid HTTPS API when SENDGRID_API_KEY is set (works on hosts
    that block SMTP); otherwise uses SMTP. Raises on genuine send errors.
    """
    cfg = current_app.config

    if not mail_is_configured():
        current_app.logger.warning(
            "MAIL not configured — skipping real send of %r to %s", subject, to
        )
        return False

    if cfg.get("SENDGRID_API_KEY"):
        return _send_via_sendgrid_api(to, subject, text_body, html_body, reply_to)

    return _send_via_smtp(to, subject, text_body, html_body, reply_to)


def _send_via_sendgrid_api(to, subject, text_body, html_body, reply_to) -> bool:
    """Send through SendGrid's v3 API over HTTPS (port 443)."""
    cfg = current_app.config
    from_name, from_email = parseaddr(cfg["MAIL_SENDER"])

    content = [{"type": "text/plain", "value": text_body}]
    if html_body:
        content.append({"type": "text/html", "value": html_body})

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_email, "name": from_name} if from_name else {"email": from_email},
        "subject": subject,
        "content": content,
    }
    if reply_to:
        payload["reply_to"] = {"email": reply_to}

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {cfg['SENDGRID_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, timeout=15, context=context) as resp:
            ok = 200 <= resp.status < 300
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        current_app.logger.error("SendGrid API error %s: %s", exc.code, body)
        raise
    current_app.logger.info("Sent %r to %s via SendGrid API", subject, to)
    return ok


def _send_via_smtp(to, subject, text_body, html_body, reply_to) -> bool:
    """Send via SMTP (smtplib). Used locally / as a fallback."""
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

    # certifi's CA bundle so TLS verification works even when the Python build
    # can't see the system certificate store (common on macOS).
    context = ssl.create_default_context(cafile=certifi.where())
    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=20) as server:
        if cfg.get("MAIL_USE_TLS"):
            server.starttls(context=context)
        server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        server.send_message(msg)
    current_app.logger.info("Sent %r to %s via SMTP", subject, to)
    return True

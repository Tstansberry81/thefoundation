"""Application configuration for the Meet You There Foundation website."""
import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load secrets/settings from a local .env file (never committed) so credentials
# don't have to be exported by hand every time the app runs.
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    # In production, set SECRET_KEY as an environment variable.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production-please")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "foundation.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    # Set SESSION_COOKIE_SECURE=true in the environment once served over HTTPS so
    # cookies are never sent over plain http.
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # Reject oversized request bodies (basic DoS / abuse guard): 1 MB.
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024

    # CSRF tokens stay valid for the session (None = tied to session lifetime).
    WTF_CSRF_TIME_LIMIT = None

    # Rate-limit backend. "memory://" is fine for a single local process; use a
    # Redis URL in production so limits are shared across workers.
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # Set to true ONLY when running behind a trusted reverse proxy / tunnel
    # (ngrok, cloudflared, a deploy host). It makes the app trust X-Forwarded-*
    # headers so client IPs and external URLs are correct. Leave false locally —
    # otherwise clients could spoof their IP to dodge rate limits.
    TRUST_PROXY = os.environ.get("TRUST_PROXY", "false").lower() == "true"
    # Optional: force the scheme used when building external links (e.g. https).
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "http")

    # How long a password-reset link stays valid (seconds). Default 1 hour.
    PASSWORD_RESET_MAX_AGE = int(os.environ.get("PASSWORD_RESET_MAX_AGE", str(60 * 60)))

    # ---------------------------------------------------------------- Email
    # The foundation's support / contact address. Verification emails are sent
    # from here, and the contact form is delivered here.
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "andreamariecoaching@gmail.com")

    # SMTP settings. Defaults target Gmail. To actually SEND mail you must set
    # MAIL_USERNAME + MAIL_PASSWORD (a Gmail "App Password", not the normal one).
    # Until those are set, the app runs in DEV mode: verification links are shown
    # on screen / logged instead of emailed, so you can still test the flow.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")  # e.g. andreamariecoaching@gmail.com
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")  # Gmail App Password
    MAIL_SENDER = os.environ.get(
        "MAIL_SENDER", f"Meet You There Foundation <{SUPPORT_EMAIL}>"
    )

    # How long a verification link stays valid (seconds). Default 24 hours.
    EMAIL_TOKEN_MAX_AGE = int(os.environ.get("EMAIL_TOKEN_MAX_AGE", str(60 * 60 * 24)))

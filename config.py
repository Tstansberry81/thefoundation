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

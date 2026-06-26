"""
Meet You There Foundation — Flask application.

Public pages are viewable by anyone. Signing in is only required to reach the
member portal (the "certain stuff" behind authentication).

Run locally:
    python app.py
Then open http://127.0.0.1:5000
"""
import os

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from itsdangerous import BadSignature, SignatureExpired

from config import Config
from email_utils import (
    confirm_token,
    generate_token,
    mail_is_configured,
    normalize_email,
    send_email,
)
from models import User, db

# Extensions are created at module scope and bound to the app in create_app().
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

# Reusable rate-limit strings for sensitive endpoints.
LIMIT_LOGIN = "10 per minute;50 per hour"
LIMIT_REGISTER = "5 per minute;20 per hour"
LIMIT_EMAIL = "3 per minute;10 per hour"  # resend / forgot-password
LIMIT_CONTACT = "5 per minute;20 per hour"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # When behind a trusted proxy/tunnel, honor X-Forwarded-* so the real client
    # IP (for rate limiting) and the public host (for verification links) are used.
    if app.config.get("TRUST_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Make sure the instance folder (for the SQLite file) exists.
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.login_message = "Please sign in to access that area."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    # ----------------------------------------------------- Security headers
    @app.after_request
    def set_security_headers(response):
        # Content Security Policy: only allow our own assets + Google Fonts.
        # 'unsafe-inline' is permitted for styles only (we use style="" attrs);
        # scripts are external files, so script-src stays locked to 'self'.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "object-src 'none'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        # Only meaningful (and only sent) over HTTPS.
        if request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {
            "now_year": datetime.now().year,
            "support_email": app.config["SUPPORT_EMAIL"],
        }

    # --------------------------------------------------------- Email helpers
    def send_verification_email(user: User):
        """Email a verification link. Returns (link, send_failed)."""
        token = generate_token(user.email)
        verify_url = url_for("verify_email", token=token, _external=True)
        subject = "Please verify your email — Meet You There Foundation"
        text_body = (
            f"Hi {user.name.split()[0]},\n\n"
            "Thank you for creating an account with the Meet You There Foundation.\n"
            "Please confirm your email address by opening the link below:\n\n"
            f"{verify_url}\n\n"
            "This link expires in 24 hours. If you didn't create this account, "
            "you can safely ignore this message.\n\n"
            "— Meet You There Foundation"
        )
        html_body = render_template(
            "email/verify.html", name=user.name.split()[0], verify_url=verify_url
        )
        send_failed = False
        try:
            send_email(
                user.email, subject, text_body, html_body,
                reply_to=app.config["SUPPORT_EMAIL"],
            )
        except Exception as exc:  # pragma: no cover - network failure path
            app.logger.error("Failed to send verification email: %s", exc)
            send_failed = True
        return verify_url, send_failed

    def send_password_reset_email(user: User):
        """Email a password-reset link. Returns (link, send_failed)."""
        token = generate_token(user.email, salt="password-reset")
        reset_url = url_for("reset_password", token=token, _external=True)
        subject = "Reset your password — Meet You There Foundation"
        text_body = (
            f"Hi {user.name.split()[0]},\n\n"
            "We received a request to reset your password. Open the link below to "
            "choose a new one:\n\n"
            f"{reset_url}\n\n"
            "This link expires in 1 hour. If you didn't request this, you can "
            "safely ignore this email — your password won't change.\n\n"
            "— Meet You There Foundation"
        )
        html_body = render_template(
            "email/reset.html", name=user.name.split()[0], reset_url=reset_url
        )
        send_failed = False
        try:
            send_email(
                user.email, subject, text_body, html_body,
                reply_to=app.config["SUPPORT_EMAIL"],
            )
        except Exception as exc:  # pragma: no cover
            app.logger.error("Failed to send reset email: %s", exc)
            send_failed = True
        return reset_url, send_failed

    # ----------------------------------------------------------------- Public
    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/mission")
    def mission():
        return render_template("mission.html")

    @app.route("/programs")
    def programs():
        return render_template("programs.html")

    @app.route("/contact", methods=["GET", "POST"])
    @limiter.limit(LIMIT_CONTACT, methods=["POST"])
    def contact():
        if request.method == "POST":
            # Honeypot: bots fill hidden fields humans never see. If the trap is
            # filled, silently accept and drop the message (don't tip off the bot).
            if request.form.get("website", "").strip():
                flash("Thank you. Your message has been received.", "success")
                return redirect(url_for("contact"))

            name = request.form.get("name", "").strip()[:200]
            from_email = request.form.get("email", "").strip()[:255]
            reason = request.form.get("reason", "").strip()[:200]
            message = request.form.get("message", "").strip()[:5000]

            # Basic validation so empty/garbage submissions don't reach the inbox.
            if not name or not message or normalize_email(from_email) is None:
                flash("Please enter your name, a valid email, and a message.", "error")
                return render_template("contact.html", name=name, email=from_email, reason=reason, message=message)

            # Deliver to the foundation's support inbox when mail is configured;
            # otherwise still acknowledge the visitor gracefully.
            if mail_is_configured():
                body = (
                    f"New message from the website contact form.\n\n"
                    f"Name: {name}\nEmail: {from_email}\nReason: {reason}\n\n"
                    f"Message:\n{message}\n"
                )
                try:
                    send_email(
                        app.config["SUPPORT_EMAIL"],
                        f"Website inquiry from {name or 'a visitor'}",
                        body,
                        reply_to=from_email or None,
                    )
                except Exception as exc:  # pragma: no cover
                    app.logger.error("Contact form send failed: %s", exc)

            flash(
                f"Thank you{', ' + name.split()[0] if name else ''}. Your message has "
                "been received. We'll meet you there soon.",
                "success",
            )
            return redirect(url_for("contact"))
        return render_template("contact.html")

    # ------------------------------------------------------------------- Auth
    @app.route("/login", methods=["GET", "POST"])
    @limiter.limit(LIMIT_LOGIN, methods=["POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("portal"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            remember = bool(request.form.get("remember"))

            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                if not user.email_verified:
                    flash(
                        "Please verify your email before signing in. "
                        "We can send you a new link if you need one.",
                        "error",
                    )
                    return redirect(url_for("verify_sent", email=user.email))
                login_user(user, remember=remember)
                flash(f"Welcome back, {user.name.split()[0]}.", "success")
                next_page = request.args.get("next")
                # Only allow internal redirects. Reject protocol-relative URLs
                # ("//evil.com" or "/\evil.com") which browsers send off-site.
                if (
                    next_page
                    and next_page.startswith("/")
                    and not next_page.startswith(("//", "/\\"))
                ):
                    return redirect(next_page)
                return redirect(url_for("portal"))
            flash("Those credentials don't match our records. Please try again.", "error")

        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    @limiter.limit(LIMIT_REGISTER, methods=["POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("portal"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()[:200]
            raw_email = request.form.get("email", "").strip()
            email = normalize_email(raw_email)
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")

            errors = []
            if len(name) < 2:
                errors.append("Please enter your name.")
            if email is None:
                errors.append("Please enter a valid email address.")
            if len(password) < 8:
                errors.append("Password must be at least 8 characters.")
            if len(password) > 200:
                errors.append("Password is too long.")
            if password != confirm:
                errors.append("Passwords do not match.")
            if email and User.query.filter_by(email=email).first():
                errors.append("An account with that email already exists.")

            if errors:
                for e in errors:
                    flash(e, "error")
                return render_template("register.html", name=name, email=raw_email)

            user = User(name=name, email=email, email_verified=False)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            verify_url, send_failed = send_verification_email(user)
            # In dev (no SMTP configured) surface the link so the flow is testable.
            if not mail_is_configured():
                session["dev_verify_link"] = verify_url
            elif send_failed:
                flash(
                    "Your account was created, but we couldn't send the verification "
                    "email just now. Use 'Resend' below in a moment.",
                    "error",
                )
            return redirect(url_for("verify_sent", email=email))

        return render_template("register.html")

    # -------------------------------------------------- Email verification
    @app.route("/verify-sent")
    def verify_sent():
        email = request.args.get("email", "")
        dev_link = session.pop("dev_verify_link", None)
        return render_template(
            "verify_sent.html",
            email=email,
            dev_link=dev_link,
            mail_configured=mail_is_configured(),
        )

    @app.route("/verify/<token>")
    def verify_email(token: str):
        try:
            email = confirm_token(token)
        except SignatureExpired:
            flash("That verification link has expired. Please request a new one.", "error")
            return redirect(url_for("resend_verification"))
        except BadSignature:
            flash("That verification link is invalid.", "error")
            return redirect(url_for("resend_verification"))

        user = User.query.filter_by(email=email).first()
        if user is None:
            flash("We couldn't find an account for that link.", "error")
            return redirect(url_for("register"))

        if user.email_verified:
            flash("Your email is already verified — please sign in.", "info")
        else:
            user.email_verified = True
            db.session.commit()
            flash("Thank you — your email is verified. You can now sign in.", "success")
        return redirect(url_for("login"))

    @app.route("/resend", methods=["GET", "POST"])
    @limiter.limit(LIMIT_EMAIL, methods=["POST"])
    def resend_verification():
        if request.method == "POST":
            email = normalize_email(request.form.get("email", "").strip()) or ""
            user = User.query.filter_by(email=email).first() if email else None
            if user and not user.email_verified:
                verify_url, _ = send_verification_email(user)
                if not mail_is_configured():
                    session["dev_verify_link"] = verify_url
            # Same response regardless, so we don't reveal which emails exist.
            flash(
                "If that address has an unverified account, a new link is on its way.",
                "info",
            )
            return redirect(url_for("verify_sent", email=email))
        return render_template("resend.html")

    # ---------------------------------------------------- Password reset
    @app.route("/forgot", methods=["GET", "POST"])
    @limiter.limit(LIMIT_EMAIL, methods=["POST"])
    def forgot_password():
        if current_user.is_authenticated:
            return redirect(url_for("portal"))
        if request.method == "POST":
            email = normalize_email(request.form.get("email", "").strip()) or ""
            user = User.query.filter_by(email=email).first() if email else None
            # Only verified accounts can reset (an unverified one should verify).
            if user and user.email_verified:
                send_password_reset_email(user)
            # Same message regardless, so attackers can't enumerate accounts.
            flash(
                "If an account exists for that email, a reset link is on its way.",
                "info",
            )
            return redirect(url_for("login"))
        return render_template("forgot.html")

    @app.route("/reset/<token>", methods=["GET", "POST"])
    @limiter.limit(LIMIT_EMAIL, methods=["POST"])
    def reset_password(token: str):
        if current_user.is_authenticated:
            return redirect(url_for("portal"))
        try:
            email = confirm_token(
                token,
                max_age=app.config["PASSWORD_RESET_MAX_AGE"],
                salt="password-reset",
            )
        except SignatureExpired:
            flash("That reset link has expired. Please request a new one.", "error")
            return redirect(url_for("forgot_password"))
        except BadSignature:
            flash("That reset link is invalid.", "error")
            return redirect(url_for("forgot_password"))

        user = User.query.filter_by(email=email).first()
        if user is None:
            flash("We couldn't find that account.", "error")
            return redirect(url_for("forgot_password"))

        if request.method == "POST":
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")
            errors = []
            if len(password) < 8:
                errors.append("Password must be at least 8 characters.")
            if len(password) > 200:
                errors.append("Password is too long.")
            if password != confirm:
                errors.append("Passwords do not match.")
            if errors:
                for e in errors:
                    flash(e, "error")
                return render_template("reset.html", token=token)
            user.set_password(password)
            db.session.commit()
            flash("Your password has been updated. Please sign in.", "success")
            return redirect(url_for("login"))

        return render_template("reset.html", token=token)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You've been signed out. Take care.", "info")
        return redirect(url_for("home"))

    # -------------------------------------------------------------- Protected
    @app.route("/portal")
    @login_required
    def portal():
        return render_template("portal.html")

    # ----------------------------------------------------------- Error pages
    @app.errorhandler(404)
    def not_found(_):
        return render_template("404.html"), 404

    @app.errorhandler(CSRFError)
    def handle_csrf(_):
        return (
            render_template(
                "error.html",
                code="Session expired",
                title="Please try that again",
                message="Your secure session token expired or didn't match. "
                "Refresh the page and resubmit the form.",
            ),
            400,
        )

    @app.errorhandler(429)
    def too_many_requests(_):
        return (
            render_template(
                "error.html",
                code="Slow down",
                title="Too many attempts",
                message="You've made a lot of requests in a short time. "
                "Please wait a minute and try again.",
            ),
            429,
        )

    @app.errorhandler(500)
    def server_error(_):
        return (
            render_template(
                "error.html",
                code="Something went wrong",
                title="We hit a snag",
                message="An unexpected error occurred. Please try again shortly.",
            ),
            500,
        )

    # --------------------------------------------------------------- CLI seed
    @app.cli.command("init-db")
    def init_db():
        """Create tables, run light migrations, and seed a starter admin."""
        ensure_schema(app)
        print("Database ready. Admin: admin@meetyouthere.org / changeme123")

    return app


def ensure_schema(app: Flask) -> None:
    """Create tables, add new columns to an existing SQLite DB, and seed admin.

    This is a tiny stand-in for a migration tool: if the database was created
    before `email_verified` existed, add the column in place rather than wiping
    any accounts that were already registered.
    """
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        db.create_all()

        # Tiny in-place migration for older *SQLite* databases that predate the
        # email_verified column. On a fresh database (e.g. Postgres on Render)
        # create_all() already includes the column, so this never runs there.
        if db.engine.dialect.name == "sqlite":
            inspector = inspect(db.engine)
            columns = {c["name"] for c in inspector.get_columns("users")}
            if "email_verified" not in columns:
                db.session.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN email_verified "
                        "BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
                # Existing accounts predate verification — treat them as verified.
                db.session.execute(text("UPDATE users SET email_verified = 1"))
                db.session.commit()

        # Seed the admin account. Wrapped so concurrent workers on first deploy
        # can't crash racing to insert the same row.
        try:
            admin = User.query.filter_by(email="admin@meetyouthere.org").first()
            if admin is None:
                admin = User(
                    name="Foundation Admin",
                    email="admin@meetyouthere.org",
                    role="admin",
                    email_verified=True,
                )
                admin.set_password(os.environ.get("ADMIN_PASSWORD", "changeme123"))
                db.session.add(admin)
                db.session.commit()
                print(">> Seeded admin login -> admin@meetyouthere.org")
            elif not admin.email_verified:
                admin.email_verified = True
                db.session.commit()
        except IntegrityError:
            db.session.rollback()


app = create_app()
ensure_schema(app)


if __name__ == "__main__":
    # Debug is OFF by default (the Werkzeug debugger can run code). Opt in for
    # local development with FLASK_DEBUG=1. Bind to localhost only.
    # Port 8000, not 5000 — macOS AirPlay Receiver occupies 5000 and intercepts
    # connections (including tunnels), so we avoid it. Override with PORT=.
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", "8000"))
    app.run(debug=debug, host="127.0.0.1", port=port)

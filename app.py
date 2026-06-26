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
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from itsdangerous import BadSignature, SignatureExpired

from config import Config
from email_utils import confirm_token, generate_token, mail_is_configured, send_email
from models import User, db


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Make sure the instance folder (for the SQLite file) exists.
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.login_message = "Please sign in to access that area."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

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
    def send_verification_email(user: User) -> str:
        """Email a verification link to the user. Returns the link (for dev display)."""
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
        try:
            send_email(
                user.email,
                subject,
                text_body,
                html_body,
                reply_to=app.config["SUPPORT_EMAIL"],
            )
        except Exception as exc:  # pragma: no cover - network failure path
            app.logger.error("Failed to send verification email: %s", exc)
        return verify_url

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
    def contact():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            from_email = request.form.get("email", "").strip()
            reason = request.form.get("reason", "").strip()
            message = request.form.get("message", "").strip()

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
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("portal"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")

            errors = []
            if len(name) < 2:
                errors.append("Please enter your name.")
            if "@" not in email or "." not in email:
                errors.append("Please enter a valid email address.")
            if len(password) < 8:
                errors.append("Password must be at least 8 characters.")
            if password != confirm:
                errors.append("Passwords do not match.")
            if User.query.filter_by(email=email).first():
                errors.append("An account with that email already exists.")

            if errors:
                for e in errors:
                    flash(e, "error")
                return render_template("register.html", name=name, email=email)

            user = User(name=name, email=email, email_verified=False)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            verify_url = send_verification_email(user)
            # In dev (no SMTP configured) surface the link so the flow is testable.
            if not mail_is_configured():
                session["dev_verify_link"] = verify_url
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
    def resend_verification():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = User.query.filter_by(email=email).first()
            if user and not user.email_verified:
                verify_url = send_verification_email(user)
                if not mail_is_configured():
                    session["dev_verify_link"] = verify_url
            # Same response regardless, so we don't reveal which emails exist.
            flash(
                "If that address has an unverified account, a new link is on its way.",
                "info",
            )
            return redirect(url_for("verify_sent", email=email))
        return render_template("resend.html")

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

    with app.app_context():
        db.create_all()

        inspector = inspect(db.engine)
        columns = {c["name"] for c in inspector.get_columns("users")}
        if "email_verified" not in columns:
            db.session.execute(
                text(
                    "ALTER TABLE users ADD COLUMN email_verified "
                    "BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            # Existing accounts predate verification — treat them as verified so
            # nobody gets locked out by the upgrade.
            db.session.execute(text("UPDATE users SET email_verified = 1"))
            db.session.commit()

        admin = User.query.filter_by(email="admin@meetyouthere.org").first()
        if admin is None:
            admin = User(
                name="Foundation Admin",
                email="admin@meetyouthere.org",
                role="admin",
                email_verified=True,
            )
            admin.set_password("changeme123")
            db.session.add(admin)
            db.session.commit()
            print(">> Seeded demo login -> admin@meetyouthere.org / changeme123")
        elif not admin.email_verified:
            admin.email_verified = True
            db.session.commit()


app = create_app()
ensure_schema(app)


if __name__ == "__main__":
    app.run(debug=True, port=5000)

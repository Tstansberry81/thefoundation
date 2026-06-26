# Meet You There Foundation — Website

A professional, accessible website for the Meet You There Foundation, built with
Flask. Public pages are viewable by anyone; signing in is only required to reach
the **Member Portal**.

Design: white + beige palette, Lora + Raleway typography, WCAG-leaning
"Accessible & Ethical" style (generated with the UI/UX Pro Max skill).

## Run it

```bash
cd "~/Desktop/moms website"
source .venv/bin/activate          # the virtual environment is already created
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

The first run automatically creates the database and a demo login so you can try
the protected area immediately:

| Email | Password |
|-------|----------|
| `admin@meetyouthere.org` | `changeme123` |

> Change this password before any real use. You can also create your own account
> from the **Create account** page.

## Pages

| Path | Access | Description |
|------|--------|-------------|
| `/` | Public | Home — mission, values, areas of impact, vision |
| `/mission` | Public | Full mission statement and core values |
| `/programs` | Public | Programs and areas of support |
| `/contact` | Public | Contact / request-support form |
| `/login`, `/register` | Public | Authentication |
| `/portal` | **Login required** | Member portal (protected resources) |

## How auth works

- Passwords are hashed with Werkzeug (never stored in plain text).
- Sessions are managed by Flask-Login.
- The `/portal` route is protected with `@login_required` — visiting it while
  logged out redirects to the login page and returns you afterward.
- **New accounts must verify their email before they can sign in.** Registration
  sends a signed, 24-hour verification link; login is blocked until it's used.
  Users can request a fresh link from the "Check your inbox" / Resend pages.

## Email verification & sending

The verification link is a signed token (no token table needed). Whether the
email is actually delivered depends on SMTP configuration:

- **Out of the box (no SMTP set):** the app runs in *developer mode* — instead of
  emailing, it shows the verification link on screen so you can test the whole
  flow locally.
- **To send real emails**, set these environment variables before `python app.py`:

  ```bash
  export MAIL_USERNAME="andreamariecoaching@gmail.com"
  export MAIL_PASSWORD="your-16-char-gmail-app-password"   # NOT the normal password
  # optional overrides (these are the defaults):
  # export SUPPORT_EMAIL="andreamariecoaching@gmail.com"
  # export MAIL_SERVER="smtp.gmail.com"
  # export MAIL_PORT="587"
  ```

  **Gmail App Password:** at https://myaccount.google.com/apppasswords (requires
  2-Step Verification enabled on the account), create an app password and use it
  as `MAIL_PASSWORD`. Gmail blocks normal-password SMTP logins.

The **support email** (`andreamariecoaching@gmail.com`) is shown in the footer
and on the Contact page, is the "from" address on verification emails, and is
where the Contact form is delivered once SMTP is configured.

## Project structure

```
moms website/
├── app.py              # Flask app, routes, auth
├── models.py           # User model (hashed passwords)
├── config.py           # Configuration (secret key, database)
├── requirements.txt
├── static/
│   ├── css/styles.css  # Full design system (white + beige tokens)
│   ├── js/main.js      # Mobile menu, password show/hide
│   └── img/favicon.svg
├── templates/          # Jinja2 templates (base, pages, auth, portal)
└── instance/           # SQLite database (auto-created, git-ignored)
```

## Changing the look

All colors live as CSS variables at the top of `static/css/styles.css`
(`:root { ... }`). Adjust `--bg`, `--bg-alt`, `--accent`, `--gold`, etc. and
refresh — no rebuild needed.

## Notes for production

- Set a real `SECRET_KEY` environment variable.
- Wire the contact form to an email service (currently it just confirms receipt).
- Serve behind a production WSGI server (gunicorn/uwsgi), not `app.run()`.

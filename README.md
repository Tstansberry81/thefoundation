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

Then open **http://127.0.0.1:8000** in your browser.

> Port is **8000**, not 5000 — macOS's AirPlay Receiver occupies port 5000 and
> intercepts connections (which breaks tunnels/sharing). Override with `PORT=`.

The first run automatically creates the database and a demo login so you can try
the protected area immediately:

| Email | Password |
|-------|----------|
| `admin@meetyouthere.org` | `changeme123` |

> Change this password before any real use. You can also create your own account
> from the **Create account** page.

## Deploying to Render

This repo includes a `render.yaml` Blueprint that provisions a web service **and**
a Postgres database automatically.

1. Push this repo to GitHub (e.g. `Tstansberry81/thefoundation`).
2. Go to **https://dashboard.render.com/select-repo?type=blueprint**, pick the repo,
   and apply the Blueprint. Render reads `render.yaml` and creates the web service
   + `foundation-db` Postgres.
3. Render will prompt for the **secret** env vars (marked `sync: false`):
   - **`MAIL_PASSWORD`** — your Gmail App Password (the 16-char one).
   - **`ADMIN_PASSWORD`** — a strong password for the seeded `admin@meetyouthere.org` account (optional; defaults to `changeme123`).
4. Deploy. On first boot the app creates the tables and seeds the admin account.
5. Visit the `https://thefoundation.onrender.com` URL Render gives you.

What's already wired for production via `render.yaml`:
`SECRET_KEY` (auto-generated), `DATABASE_URL` (from Postgres), `SESSION_COOKIE_SECURE=true`,
`TRUST_PROXY=true`, `FLASK_DEBUG=0`, and gunicorn as the server.

**Notes & limits**
- Render's **free** web service sleeps after ~15 min idle (first request then takes ~30s to wake). The **free Postgres** is time-limited — upgrade to a paid instance for a permanent database.
- Outbound Gmail SMTP works from Render. Gmail may send you a "new sign-in" alert the first time from Render's IP — approve it if asked; the App Password keeps working.
- For best email deliverability to **all** providers, move to a custom domain + a transactional email service later (the app already speaks SMTP, so it's an env-var change).

## Security

The app is hardened against common web attacks:

- **CSRF protection** (Flask-WTF) on every form — forged cross-site POSTs are rejected.
- **Security headers** — Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy (and HSTS over HTTPS).
- **Rate limiting** (Flask-Limiter) on login, register, contact, resend, and password-reset to stop brute-force and spam.
- **Spam honeypot** + validation on the contact form.
- **Password reset** flow via signed, 1-hour, single-purpose tokens.
- **Account-enumeration safe** — login, resend, and forgot-password give the same response whether or not an account exists.
- **Open-redirect safe** login `next=` handling; request size capped; debugger off by default.
- Passwords hashed (Werkzeug); session/CSRF tokens signed with `SECRET_KEY` from `.env`.

For production, also set in the environment: `FLASK_DEBUG=0` (default), `SESSION_COOKIE_SECURE=true` (once on HTTPS), a Redis `RATELIMIT_STORAGE_URI`, and `TRUST_PROXY=true` only when behind a real proxy/tunnel.

## Letting others test it (temporary public link)

The site runs on your Mac only. To let someone test from their own phone, expose it
with a tunnel (no account needed):

```bash
# 1) make sure the app is running (python app.py) on port 8000
# 2) in another terminal, from the project folder:
ssh -R 80:localhost:8000 nokey@localhost.run
```

It prints a public `https://<random>.lhr.life` URL. Share that. While the tunnel
is running, `.env` should keep `TRUST_PROXY=true` so verification links use the
public URL. The URL changes each time you restart the tunnel, and old verification
links stop working when it does — so it's for testing, not launch. For a permanent
site, deploy to a host (Render/Railway/PythonAnywhere) with a domain + email service.

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

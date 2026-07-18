# Book Pharm — Local Setup

Read [`CLAUDE.md`](./CLAUDE.md) first for architecture and conventions. This is just the "get it running" guide.

## Prerequisites

- **Python 3.10** — cPanel's "Setup Python App" supports 3.9.23–3.10.20, so local dev targets 3.10 to match. Install via `winget install --id Python.Python.3.10` if it's not already on your machine (check with `py -0p`).
- **MySQL/MariaDB** — this project uses XAMPP's bundled MariaDB (`C:\xampp\mysql`) for local dev. Any MySQL 8-compatible server works; just point `.env` at it.
- **Node.js** — for `desktop/` (Electron POS), once that phase starts.

## Backend setup (`backend/`)

All backend commands run inside the virtual environment. **Never install packages or run `manage.py` with the system Python.**

```bash
cd backend

# 1. Create and activate the venv (Python 3.10 specifically)
py -3.10 -m venv .venv
source .venv/Scripts/activate      # Git Bash
# .venv\Scripts\Activate.ps1       # PowerShell instead

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env config (one level up, at repo root) and fill in values
cp ../.env.example ../.env

# 4. Start MySQL/MariaDB (e.g. via XAMPP Control Panel), then create the dev DB once:
#    mysql -u root -e "CREATE DATABASE bookpharm_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 5. Migrate and create the owner account
python manage.py migrate
python manage.py createsuperuser

# 6. Run it
python manage.py runserver
```

- Storefront: http://127.0.0.1:8000/
- Portal: http://127.0.0.1:8000/portal/ (log in at `/admin/login/` until Phase 4 builds a dedicated portal login)
- Django admin: http://127.0.0.1:8000/admin/

Every subsequent session, just `cd backend && source .venv/Scripts/activate` before running anything.

## Settings

`config/settings/` is split into `base.py` (shared), `dev.py` (local), and `prod.py` (cPanel/Passenger). `manage.py` defaults to `dev`; `wsgi.py` defaults to `prod`. Override with the `DJANGO_SETTINGS_MODULE` env var if needed.

## Environment variables

See `.env.example` at the repo root. `.env` itself is gitignored — never commit it.

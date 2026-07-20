"""Not a deployment target — a build-time helper for regenerating
backend/vercel_seed_db.sqlite3, the bundled read-only seed the Vercel UAT
environment copies to a writable path on cold start (see vercel.py and
ROADMAP.md's "Vercel UAT, SQLite seed" entry).

Regenerate the seed after the dev MySQL data changes:

    python manage.py migrate --settings=config.settings.sqlite_seed
    python manage.py dumpdata --natural-foreign --natural-primary \\
        -e contenttypes -e auth.permission -e admin.logentry -e sessions.session \\
        --settings=config.settings.dev -o /tmp/dev_data.json
    python manage.py loaddata /tmp/dev_data.json --settings=config.settings.sqlite_seed
"""

from .base import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'vercel_seed_db.sqlite3',
    }
}

DEBUG = True

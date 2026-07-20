"""Vercel deployment — storefront + portal, UAT only (2026-07-20). Not the
production target; that's still cPanel per CLAUDE.md §3. This exists so the
client can click through a real, hosted build before go-live, without
waiting on domain registration / cPanel setup (Phase 8).

Inherits prod.py's security posture (HTTPS redirect, secure cookies, HSTS)
since a real client is looking at this, not just localhost.

Known, accepted gaps for this UAT-only environment (see ROADMAP.md):
- Book cover uploads use local disk (MEDIA_ROOT), which Vercel's serverless
  functions don't persist — writable only under a per-instance temp dir,
  wiped on every cold start. Pointed there below so an upload succeeds
  instead of crashing the book-edit form; it just won't survive across
  requests. Desktop POS's Electron app is unaffected (different codebase,
  doesn't deploy here).
- Database: VERCEL_DB_ENGINE picks between two throwaway options, neither
  of which is the eventual cPanel database:
    'sqlite' (default, 2026-07-20) — backend/vercel_seed_db.sqlite3 is a
      real dumpdata/loaddata snapshot of the dev MySQL database (see
      config/settings/sqlite_seed.py for how to regenerate it), bundled
      read-only with the deployment. Copied to a writable per-instance temp
      path on cold start so the app can actually write (sales, sessions,
      admin edits) — but each cold start gets a *fresh copy* of the seed,
      and concurrent instances don't share writes. Fine for a single
      person clicking through the app; not for a multi-session UAT where
      data needs to persist across visits or across simultaneous testers.
      Picked over Aiven when Aiven's hostname wasn't resolving in DNS yet
      (looked like the service still provisioning) and a working UAT build
      was more urgent than diagnosing that further.
    'mysql' — Aiven's always-free MySQL tier, real persistence, no
      per-instance-reset caveat. Switch back once Aiven resolves: set
      VERCEL_DB_ENGINE=mysql and DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME
      in the Vercel dashboard (values already given to Claude in this
      session — check chat history or the Aiven console).
"""

import shutil
import tempfile
from pathlib import Path

from .prod import *  # noqa: F401,F403

DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)

# Vercel gives every deployment a *.vercel.app host — both the stable
# production alias and a new one per preview/branch deploy — so allow the
# whole suffix rather than pinning one hostname that breaks on the next
# preview URL. A later custom domain still works via DJANGO_ALLOWED_HOSTS
# (base.py already reads it), added on top here, not replaced.
ALLOWED_HOSTS = list(ALLOWED_HOSTS) + ['.vercel.app']
_explicit_hosts = [h for h in ALLOWED_HOSTS if not h.startswith('.')]
CORS_ALLOWED_ORIGINS = [f'https://{h}' for h in _explicit_hosts]
CSRF_TRUSTED_ORIGINS = ['https://*.vercel.app'] + [f'https://{h}' for h in _explicit_hosts]

# Vercel terminates TLS at its edge and forwards to the function over plain
# HTTP internally — without this, Django can't tell the request was
# actually HTTPS, which breaks SECURE_SSL_REDIRECT (infinite redirect loop)
# and the *_COOKIE_SECURE flags inherited from prod.py.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# tempfile.gettempdir() resolves to /tmp on Vercel's actual Linux runtime
# (the only writable path in a Vercel function) and to a real writable temp
# dir on Windows/dev too — so this same logic is genuinely testable locally,
# not just hopefully-correct-on-the-real-target.
_writable_dir = Path(tempfile.gettempdir())

VERCEL_DB_ENGINE = config('VERCEL_DB_ENGINE', default='sqlite')

if VERCEL_DB_ENGINE == 'mysql':
    import ssl

    # PyMySQL-as-MySQLdb is already installed globally in base.py (every
    # settings module needs it now that mysqlclient isn't in
    # requirements.txt at all — see that file's comment).

    # Aiven requires TLS (ssl-mode=REQUIRED) but this UAT instance has no CA
    # certificate configured — this encrypts the connection without
    # verifying the server certificate against a specific CA. Acceptable
    # for a throwaway UAT database; not the standard to hold the real
    # cPanel database to.
    _ssl_context = ssl.create_default_context()
    _ssl_context.check_hostname = False
    _ssl_context.verify_mode = ssl.CERT_NONE
    DATABASES['default']['OPTIONS'] = {
        **DATABASES['default']['OPTIONS'],
        'ssl': _ssl_context,
    }
else:
    # See module docstring: a bundled, read-only snapshot copied to a
    # writable path once per cold start.
    _bundled_seed = BASE_DIR / 'vercel_seed_db.sqlite3'
    _writable_db = _writable_dir / 'vercel_uat_db.sqlite3'
    if not _writable_db.exists():
        shutil.copy(_bundled_seed, _writable_db)

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': _writable_db,
        }
    }

MEDIA_ROOT = _writable_dir / 'media'

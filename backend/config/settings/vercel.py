"""Vercel deployment — storefront + portal, UAT only (2026-07-20). Not the
production target; that's still cPanel per CLAUDE.md §3. This exists so the
client can click through a real, hosted build before go-live, without
waiting on domain registration / cPanel setup (Phase 8).

Inherits prod.py's security posture (HTTPS redirect, secure cookies, HSTS)
since a real client is looking at this, not just localhost.

Known, accepted gaps for this UAT-only environment (see ROADMAP.md):
- Book cover uploads use local disk (MEDIA_ROOT), which Vercel's serverless
  functions don't persist — writable only under /tmp, and wiped on every
  cold start. Pointed at /tmp below so an upload succeeds instead of
  crashing the book-edit form; it just won't survive across requests.
  Desktop POS's Electron app is unaffected (different codebase, doesn't
  deploy here).
- Aiven's free MySQL tier backs this, not the eventual cPanel database —
  same engine (MySQL), different host/instance, picked for a genuinely-free
  tier rather than any behavioral requirement.
"""

import ssl

import pymysql

# Django's mysql backend imports `MySQLdb` — mysqlclient (the driver used
# everywhere else, including cPanel) is a compiled C extension, and
# compiling it inside Vercel's Python build image is untested and a real
# risk of a failed deploy. PyMySQL is pure Python: this shim makes
# `import MySQLdb` transparently resolve to it, so ENGINE stays
# 'django.db.backends.mysql' unchanged — nothing else in the codebase
# needs to know the driver differs here.
pymysql.install_as_MySQLdb()

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

# Aiven requires TLS (ssl-mode=REQUIRED) but this UAT instance has no CA
# certificate configured — this encrypts the connection without verifying
# the server certificate against a specific CA. Acceptable for a throwaway
# UAT database; not the standard to hold the real cPanel database to.
_ssl_context = ssl.create_default_context()
_ssl_context.check_hostname = False
_ssl_context.verify_mode = ssl.CERT_NONE
DATABASES['default']['OPTIONS'] = {
    **DATABASES['default']['OPTIONS'],
    'ssl': _ssl_context,
}

# See module docstring — /tmp is the only writable path in a Vercel
# function; local dev/cPanel keep base.py's BASE_DIR/media unchanged.
from pathlib import Path  # noqa: E402

MEDIA_ROOT = Path('/tmp') / 'media'

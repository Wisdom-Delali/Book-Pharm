"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path

# manage.py gets its own directory on sys.path for free (Python does this
# automatically for a directly-run script) — this file doesn't get that for
# free, because Vercel's Python runtime imports it as a module rather than
# running it as __main__. Without this, `config.settings.*` can't be found
# and django.setup() fails with ModuleNotFoundError: No module named
# 'config', even though the file is right there (confirmed against a real
# Vercel deploy, not assumed).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from django.core.wsgi import get_wsgi_application  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')

application = get_wsgi_application()

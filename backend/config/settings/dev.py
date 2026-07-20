from .base import *  # noqa: F401,F403
from .base import config  # explicit: same .env-backed config instance as base.py

DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', "*"]

CORS_ALLOW_ALL_ORIGINS = True

"""
Shared settings. dev.py and prod.py both import * from here and override
only what differs between environments.
"""

from pathlib import Path

import pymysql
from decouple import Config, Csv, RepositoryEmpty, RepositoryEnv

# django.db.backends.mysql imports `MySQLdb` — mysqlclient (a compiled C
# extension) no longer ships in requirements.txt, so PyMySQL is the only
# driver providing that import anywhere DATABASES uses this engine (dev,
# cPanel prod, and Vercel's optional mysql path alike). Installed once,
# here, rather than per-settings-module, since every one of them imports
# from this file before DATABASES is ever touched.
pymysql.install_as_MySQLdb()

# backend/config/settings/base.py -> backend/ -> repo root (where .env lives, alongside .env.example)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent

# RepositoryEnv opens the file eagerly (FileNotFoundError at import time if
# it's missing) — fine for local dev and cPanel, which both deploy a real
# .env file, but fatal on Vercel, where config arrives as real process env
# vars with no .env file in the bundle at all. RepositoryEmpty is decouple's
# own no-file fallback: Config.get() already checks os.environ before the
# repository regardless of which one backs it, so this doesn't change
# behavior anywhere a .env file exists — it only changes what happens when
# one doesn't.
_env_path = REPO_ROOT / '.env'
config = Config(RepositoryEnv(str(_env_path)) if _env_path.exists() else RepositoryEmpty())

SECRET_KEY = config('DJANGO_SECRET_KEY')

ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    # Book Pharm apps
    'apps.accounts',
    'apps.catalog',
    'apps.sales',
    'apps.fulfillment',
    'apps.customers',
    'apps.payments',
    'apps.messaging',
    'apps.expenses',
    'apps.reports',
    'apps.storefront',
    'apps.portal',
    'apps.api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.storefront.context_processors.cart_context',
                'apps.storefront.context_processors.nav_context',
                'apps.storefront.context_processors.google_maps_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'portal:login'
LOGIN_REDIRECT_URL = 'portal:dashboard'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        # DB_NAME/DB_USER default to '' rather than being required: dev.py
        # and prod.py always set them for real (a real .env file or, on
        # cPanel, real dashboard env vars), so this default is never what
        # actually runs there — it only matters for vercel.py's sqlite
        # path, which replaces this whole dict outright and never touches
        # these values, but still executes this module-level construction
        # first as a side effect of `from .base import *`. Requiring them
        # unconditionally crashed the sqlite-mode deploy at import time
        # before vercel.py ever got the chance to override DATABASES.
        'NAME': config('DB_NAME', default=''),
        'USER': config('DB_USER', default=''),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            # Without this, MySQL/MariaDB silently truncates instead of
            # rejecting bad data (e.g. a value too large for a DecimalField)
            # — unacceptable for money fields (CLAUDE.md §9).
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Accra'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Paystack / SMSOnlineGH — read here so app code never touches os.environ directly
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')
SMSONLINEGH_API_KEY = config('SMSONLINEGH_API_KEY', default='')
SMSONLINEGH_SENDER_ID = config('SMSONLINEGH_SENDER_ID', default='')

# Client-side key (Places Autocomplete + geolocation reverse-geocoding on
# the checkout address field) — Maps JS API keys are designed to be used
# browser-side; restrict by HTTP referrer in Google Cloud Console, not by
# hiding the key. Blank means the address field just stays a plain text
# input — see apps/storefront/context_processors.py::google_maps_context.
GOOGLE_MAPS_API_KEY = config('GOOGLE_MAPS_API_KEY', default='')

# Wording, not a secret — a plain setting (not .env) so changing it is a
# one-line code edit, not a hosting config change. {name_suffix} is filled
# in by send_birthday_sms with ", <first name>" or "" if the customer never
# gave one.
BIRTHDAY_SMS_MESSAGE = 'Happy Birthday{name_suffix} from Book Pharm! Wishing you a wonderful day filled with great stories.'

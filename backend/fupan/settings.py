"""
Django settings for the fupan (daily market review) project.

Supports Django 6.0 + Python 3.14.

For production deployment:
  - Set DEBUG = False
  - Set SECRET_KEY via environment variable
  - Restrict ALLOWED_HOSTS to your actual domain / IP
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

# SECURITY WARNING: keep the secret key used in production secret!
# In production, override via environment variable:
#   export DJANGO_SECRET_KEY="your-secure-random-key"
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-change-me-in-production-use-env-variable",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "fupan.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    }
]

WSGI_APPLICATION = "fupan.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# Django's built-in ORM database (used only for session / auth internals).
# Trade data is stored in a separate SQLite file (TRADE_DB_PATH below).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

# In-process memory cache; automatically invalidated on process restart.
# Analysis results are stored with a 12-hour TTL.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "TIMEOUT": 60 * 60 * 12,
    }
}

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "static/"

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Allow all origins in development. Tighten in production via
#   CORS_ALLOWED_ORIGINS = ["https://your-domain.com"]
CORS_ALLOW_ALL_ORIGINS = True

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# ---------------------------------------------------------------------------
# Project-specific paths
# ---------------------------------------------------------------------------

# Directory for raw downloaded stock data files (CSV / XLSX).
STOCK_DATA_DIR = os.path.join(BASE_DIR, "stock_data")
os.makedirs(STOCK_DATA_DIR, exist_ok=True)

# SQLite database that holds the merged daily trade information.
TRADE_DB_PATH = os.path.join(BASE_DIR, "stock_trade_info.sqlite3")

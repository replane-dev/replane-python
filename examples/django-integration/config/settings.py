"""Django settings for Replane example project."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-example-key-change-in-production"

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "demo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "demo.middleware.ReplaneMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# Replane Configuration
# =============================================================================

REPLANE_BASE_URL = os.environ.get("REPLANE_BASE_URL", "https://your-replane-server.com")
REPLANE_SDK_KEY = os.environ.get("REPLANE_SDK_KEY", "your_sdk_key_here")

# Default values if Replane server is unavailable
REPLANE_DEFAULTS = {
    "rate-limit": 100,
    "new-dashboard-enabled": False,
    "max-upload-size-mb": 10,
    "maintenance-mode": False,
}

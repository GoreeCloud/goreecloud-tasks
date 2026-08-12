"""Django settings for GoreeCloud Tasks.

The settings favor explicit environment configuration and file-based secrets so
development and production values remain outside source control.
"""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    """Read a conventional true/false environment variable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=None):
    """Read a comma-separated environment variable into a clean list."""
    raw = os.getenv(name)
    if raw is None:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def secret_value(value_name, file_name, *, required=False):
    """Read a secret from either an environment value or a protected file.

    The two sources are mutually exclusive so the active source is unambiguous.
    """
    direct_value = os.getenv(value_name)
    file_path = os.getenv(file_name)

    if direct_value and file_path:
        raise ImproperlyConfigured(
            f"Set only one of {value_name} or {file_name}, not both."
        )

    if file_path:
        path = Path(file_path)
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ImproperlyConfigured(
                f"Unable to read secret file configured by {file_name}: {path}"
            ) from exc

    if direct_value:
        return direct_value

    if required:
        raise ImproperlyConfigured(
            f"Set {value_name} or {file_name} before starting GoreeCloud Tasks."
        )

    return None


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = secret_value(
    "DJANGO_SECRET_KEY",
    "DJANGO_SECRET_KEY_FILE",
    required=False,
)
if not SECRET_KEY:
    # Django's test runner needs a secret before tests can initialize settings.
    # This deterministic value is permitted only for the test command.
    if "test" in sys.argv:
        SECRET_KEY = "goreecloud-tasks-test-only-secret-key"
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY or DJANGO_SECRET_KEY_FILE is required."
        )

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    ["localhost", "127.0.0.1"] if DEBUG else [],
)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "projects",
    "tasks",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "goreecloud_tasks.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "goreecloud_tasks.wsgi.application"
ASGI_APPLICATION = "goreecloud_tasks.asgi.application"

DATABASE_ENGINE = os.getenv("DATABASE_ENGINE", "sqlite").strip().lower()
if DATABASE_ENGINE in {"postgres", "postgresql"}:
    database_password = secret_value(
        "POSTGRES_PASSWORD",
        "POSTGRES_PASSWORD_FILE",
        required=True,
    )
    required_database_values = {
        "POSTGRES_DB": os.getenv("POSTGRES_DB"),
        "POSTGRES_USER": os.getenv("POSTGRES_USER"),
        "POSTGRES_HOST": os.getenv("POSTGRES_HOST"),
    }
    missing = [name for name, value in required_database_values.items() if not value]
    if missing:
        raise ImproperlyConfigured(
            "Missing PostgreSQL configuration: " + ", ".join(missing)
        )

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": required_database_values["POSTGRES_DB"],
            "USER": required_database_values["POSTGRES_USER"],
            "PASSWORD": database_password,
            "HOST": required_database_values["POSTGRES_HOST"],
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv(
    "DJANGO_TIME_ZONE",
    os.getenv("TZ", "America/Chicago"),
)
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "tasks:dashboard"
LOGOUT_REDIRECT_URL = "login"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
X_FRAME_OPTIONS = "DENY"

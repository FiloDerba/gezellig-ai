import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-in-production")
DEBUG = os.environ.get("DEBUG", "True").capitalize() == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_filters",
    "rest_framework",
    "drf_spectacular",
    "vocabulary",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # DRF views are CSRF-exempt, so this only guards the admin's own forms.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"
WSGI_APPLICATION = "backend.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    },
]


# Hosted Postgres is often far away, so reuse connections instead of dialling per request.
CONN_MAX_AGE = int(os.environ.get("CONN_MAX_AGE", "600"))

# libpq keys we forward from a connection string's query part. Neon needs sslmode and
# channel_binding; anything outside this set would make psycopg reject the connection.
LIBPQ_PARAMS = frozenset(
    {"sslmode", "channel_binding", "connect_timeout", "application_name", "target_session_attrs"}
)


def _postgres(**overrides) -> dict:
    return {
        "ENGINE": "django.db.backends.postgresql",
        "CONN_MAX_AGE": CONN_MAX_AGE,
        "CONN_HEALTH_CHECKS": True,
        **overrides,
    }


def _database_from_url(url: str) -> dict:
    """Turn a connection string (Neon, Supabase, Heroku style) into a DATABASES entry."""
    parsed = urlparse(url)
    if parsed.scheme.startswith("sqlite"):
        # "sqlite:////tmp/deck.sqlite3" parses with an extra leading slash on the path.
        name = "/" + parsed.path.lstrip("/") if parsed.path.strip("/") else ":memory:"
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": name}
    return _postgres(
        NAME=parsed.path.lstrip("/"),
        USER=unquote(parsed.username or ""),
        PASSWORD=unquote(parsed.password or ""),
        HOST=parsed.hostname or "",
        PORT=str(parsed.port or ""),
        OPTIONS={
            key: values[0]
            for key, values in parse_qs(parsed.query).items()
            if key in LIBPQ_PARAMS
        },
    )


def _database_from_parts() -> dict:
    """Discrete DATABASE_* variables, which is how docker-compose passes the local Postgres."""
    return _postgres(
        NAME=os.environ["DATABASE_NAME"],
        USER=os.environ.get("DATABASE_USER", "postgres"),
        PASSWORD=os.environ.get("DATABASE_PASSWORD", "postgres"),
        HOST=os.environ.get("DATABASE_HOST", "localhost"),
        PORT=os.environ.get("DATABASE_PORT", "5432"),
    )


def _default_database() -> dict:
    """DATABASE_URL wins, then DATABASE_*, then a local SQLite file so `migrate` always works."""
    if os.environ.get("DATABASE_URL"):
        return _database_from_url(os.environ["DATABASE_URL"])
    if os.environ.get("DATABASE_NAME"):
        return _database_from_parts()
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
    }


DATABASES = {"default": _default_database()}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Off in development so an "admin"/"admin" login is possible; enforced once DEBUG is False.
AUTH_PASSWORD_VALIDATORS = (
    []
    if DEBUG
    else [
        {
            "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
            "OPTIONS": {"min_length": 12},
        },
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    ]
)

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "Europe/Amsterdam")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "vocabulary.pagination.StandardPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Dutch Vocabulary API",
    "DESCRIPTION": "Spaced-repetition vocabulary backend for the Dutch learning app.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

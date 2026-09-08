import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# pytest sets this from version 8 onwards.
RUNNING_TESTS = "PYTEST_VERSION" in os.environ

if not RUNNING_TESTS:
    # Real environment variables win, so docker-compose and CI still override the file.
    load_dotenv(BASE_DIR / ".env", override=False)


def env(name: str, default: str = "") -> str:
    """Read a variable, treating a blank value as unset.

    example.env ships keys with empty values (`SECRET_KEY=`), and those would otherwise
    override the defaults below with an empty string.
    """
    return os.environ.get(name, "").strip() or default


SECRET_KEY = env("SECRET_KEY", "insecure-dev-key-change-in-production")
DEBUG = env("DEBUG", "True").capitalize() == "True"
ALLOWED_HOSTS = env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "vocabulary",
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
CONN_MAX_AGE = int(env("CONN_MAX_AGE", "600"))

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
            key: values[0] for key, values in parse_qs(parsed.query).items() if key in LIBPQ_PARAMS
        },
    )


def _sqlite() -> dict:
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
    }


def _default_database() -> dict:
    """Hosted Postgres when DATABASE_URL is set, otherwise a local SQLite file."""
    if env("DATABASE_URL"):
        return _database_from_url(env("DATABASE_URL"))
    return _sqlite()


# The suite creates and drops databases, so it stays on SQLite even when a hosted
# DATABASE_URL is configured. Otherwise `pytest` would do that to the Neon project.
DATABASES = {"default": _sqlite() if RUNNING_TESTS else _default_database()}

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
TIME_ZONE = env("TIME_ZONE", "Europe/Amsterdam")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

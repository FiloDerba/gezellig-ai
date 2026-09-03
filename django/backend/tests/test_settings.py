import pytest

from backend.settings import _database_from_parts, _database_from_url, _default_database

NEON_URL = (
    "postgresql://deck_owner:npg_S3cr3t%2Fpw@ep-cool-water-123456-pooler."
    "eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)


class DatabaseFromUrlTests:
    def test_neon_url_is_split_into_django_settings(self):
        config = _database_from_url(NEON_URL)
        assert config["ENGINE"] == "django.db.backends.postgresql"
        assert config["NAME"] == "neondb"
        assert config["USER"] == "deck_owner"
        assert config["HOST"] == "ep-cool-water-123456-pooler.eu-central-1.aws.neon.tech"

    def test_percent_encoded_password_is_decoded(self):
        """Neon passwords can contain "/" and "+", which arrive percent-encoded."""
        assert _database_from_url(NEON_URL)["PASSWORD"] == "npg_S3cr3t/pw"

    def test_ssl_query_parameters_are_forwarded_to_the_driver(self):
        assert _database_from_url(NEON_URL)["OPTIONS"] == {
            "sslmode": "require",
            "channel_binding": "require",
        }

    def test_unknown_query_parameters_are_dropped(self):
        """psycopg rejects unknown connection keywords, so they must not reach OPTIONS."""
        config = _database_from_url(f"{NEON_URL}&pool_timeout=30&options=-csearch_path%3Dpublic")
        assert "pool_timeout" not in config["OPTIONS"]

    def test_connections_are_reused(self):
        config = _database_from_url(NEON_URL)
        assert config["CONN_MAX_AGE"] > 0
        assert config["CONN_HEALTH_CHECKS"] is True

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("postgres://u:p@host:6543/db", "6543"),
            ("postgresql://u:p@host/db", ""),
        ],
    )
    def test_port_is_optional(self, url, expected):
        assert _database_from_url(url)["PORT"] == expected

    def test_sqlite_url_stays_on_sqlite(self):
        config = _database_from_url("sqlite:////tmp/deck.sqlite3")
        assert config == {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "/tmp/deck.sqlite3",
        }


class DatabaseFromPartsTests:
    def test_compose_style_variables(self, monkeypatch):
        monkeypatch.setenv("DATABASE_NAME", "dutch_vocabulary")
        monkeypatch.setenv("DATABASE_HOST", "db")
        config = _database_from_parts()
        assert config["ENGINE"] == "django.db.backends.postgresql"
        assert config["NAME"] == "dutch_vocabulary"
        assert (config["HOST"], config["PORT"]) == ("db", "5432")

    def test_defaults_match_the_compose_postgres_service(self, monkeypatch):
        monkeypatch.setenv("DATABASE_NAME", "dutch_vocabulary")
        config = _database_from_parts()
        assert (config["USER"], config["PASSWORD"]) == ("postgres", "postgres")


class DefaultDatabaseTests:
    def test_falls_back_to_sqlite_when_nothing_is_configured(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_NAME", raising=False)
        assert _default_database()["ENGINE"] == "django.db.backends.sqlite3"

    def test_database_url_wins_over_discrete_variables(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", NEON_URL)
        monkeypatch.setenv("DATABASE_NAME", "ignored")
        assert _default_database()["NAME"] == "neondb"

    def test_discrete_variables_are_used_without_a_url(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DATABASE_NAME", "dutch_vocabulary")
        assert _default_database()["NAME"] == "dutch_vocabulary"

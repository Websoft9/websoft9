import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.exception import CustomException
from src.services.install_profile import (
    _compare_versions,
    _version_matches_prefix,
    get_port_check_settings,
    matches_external_database_version,
    is_external_database_profile,
    materialize_profile_template,
    validate_external_database_connection,
    validate_profile_settings,
)


PROFILE_SETTINGS = {
    "W9_HTTP_PORT_SET": "9001",
    "W9_DB_HOST_SET": "mysql.example.internal",
    "W9_DB_PORT_SET": "3306",
    "W9_DB_NAME_SET": "wordpress_demo",
    "W9_DB_USER_SET": "wordpress_user",
    "W9_DB_PASSWORD_SET": "database-secret",
}


def _profile_template(app_dir: Path) -> None:
    app_dir.mkdir()
    (app_dir / "docker-compose.yml").write_text("services:\n  mysql: {}\n", encoding="utf-8")
    (app_dir / ".env").write_text("W9_POWER_PASSWORD=\n", encoding="utf-8")
    (app_dir / "docker-compose.external-db.yml").write_text(
        "services:\n  wordpress:\n    ports:\n      - $W9_HTTP_PORT_SET:80\n",
        encoding="utf-8",
    )
    (app_dir / ".env.external-db").write_text(
        "\n".join([
            *(f"{key}={value if key != 'W9_DB_PASSWORD_SET' else ''}" for key, value in PROFILE_SETTINGS.items()),
            "W9_DATABASE_MODE=external",
        ]),
        encoding="utf-8",
    )


def test_profile_validation_uses_the_local_template_whitelist(tmp_path):
    _profile_template(tmp_path / "wordpress")

    validate_profile_settings(tmp_path / "wordpress", "external-db", PROFILE_SETTINGS)

    with pytest.raises(CustomException) as exc_info:
        validate_profile_settings(tmp_path / "wordpress", "external-db", {**PROFILE_SETTINGS, "UNAPPROVED": "value"})

    assert exc_info.value.status_code == 400
    assert "database-secret" not in exc_info.value.details


def test_profile_validation_rejects_settings_from_a_different_template(tmp_path):
    _profile_template(tmp_path / "wordpress")

    with pytest.raises(CustomException) as exc_info:
        validate_profile_settings(
            tmp_path / "wordpress",
            "external-db",
            {"W9_HTTP_PORT_SET": "9001"},
        )

    assert exc_info.value.status_code == 400


def test_external_database_connection_settings_are_excluded_from_port_checks(tmp_path):
    app_dir = tmp_path / "wordpress"
    _profile_template(app_dir)

    assert is_external_database_profile(app_dir, "external-db") is True
    assert get_port_check_settings("external-db", PROFILE_SETTINGS, app_dir) == {"W9_HTTP_PORT_SET": "9001"}
    assert get_port_check_settings(None, PROFILE_SETTINGS) == PROFILE_SETTINGS


def test_external_database_connection_test_is_read_only(monkeypatch):
    calls = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def execute(self, statement):
            calls.append(("execute", statement))

        def fetchone(self):
            return ("8.0.36",)

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            calls.append(("close",))

    class FakePyMySQL:
        MySQLError = Exception

        @staticmethod
        def connect(**kwargs):
            calls.append(("connect", kwargs))
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "pymysql", FakePyMySQL)

    result = validate_external_database_connection(
        host="mysql.example.internal",
        port=3306,
        database_name="wordpress_demo",
        username="wordpress_user",
        password="database-secret",
    )
    assert result.database_type == "mysql"
    assert result.version == (8, 0, 36)

    assert calls == [
        ("connect", {
            "host": "mysql.example.internal",
            "port": 3306,
            "user": "wordpress_user",
            "password": "database-secret",
            "database": "wordpress_demo",
            "connect_timeout": 8,
            "read_timeout": 8,
            "write_timeout": 8,
            "autocommit": True,
        }),
        ("execute", "SELECT 1"),
        ("execute", "SELECT VERSION()"),
        ("close",),
    ]


def test_external_database_connection_falls_back_to_postgresql(monkeypatch):
    class FakePyMySQL:
        class MySQLError(Exception):
            pass

        @staticmethod
        def connect(**kwargs):
            raise FakePyMySQL.MySQLError()

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def execute(self, statement):
            return None

        def fetchone(self):
            return (160003,)

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    class FakePsycopg2:
        Error = Exception

        @staticmethod
        def connect(**kwargs):
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "pymysql", FakePyMySQL)
    monkeypatch.setitem(sys.modules, "psycopg2", FakePsycopg2)

    result = validate_external_database_connection(
        host="postgres.example.internal",
        port=5432,
        database_name="wordpress_demo",
        username="wordpress_user",
        password="database-secret",
    )

    assert result.database_type == "postgresql"
    assert result.version == (16, 0, 3)


def test_profile_materialization_preserves_the_selected_template(tmp_path):
    workspace = tmp_path / "wordpress"
    _profile_template(workspace)
    (workspace / ".env.example").write_text("DOCUMENTATION_ONLY=true\n", encoding="utf-8")

    materialize_profile_template(workspace, "external-db")

    assert "wordpress" in (workspace / "docker-compose.yml").read_text(encoding="utf-8")
    assert not list(workspace.glob("docker-compose.*.yml"))
    assert not (workspace / ".env.external-db").exists()
    assert (workspace / ".env.example").exists()
    env_content = (workspace / ".env").read_text(encoding="utf-8")
    assert "W9_DB_USER_SET=wordpress_user" in env_content
    assert "W9_DB_PASSWORD_SET=" in env_content
    assert "W9_POWER_PASSWORD" not in env_content


def test_database_version_comparison_handles_minimum_and_fixed_major_versions():
    assert _compare_versions((10, 11, 2), (10, 11)) > 0
    assert _compare_versions((8, 0), (8, 0, 0)) == 0
    assert _version_matches_prefix((17, 0, 4), (17,)) is True
    assert _version_matches_prefix((14, 9), (15,)) is False
    assert matches_external_database_version((10, 11, 2), ["MariaDB 10.11+"]) is True
    assert matches_external_database_version((14, 9), ["PostgreSQL 15, 16, 17"]) is False
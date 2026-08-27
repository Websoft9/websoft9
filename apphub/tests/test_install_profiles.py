import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.exception import CustomException
from src.services.install_profile import (
    get_external_database_type,
    get_port_check_settings,
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
    (app_dir / "docker-compose.yml").write_text(
        "services:\n  wordpress:\n    depends_on:\n      - mysql\n    volumes:\n      - wordpress:/var/www/html\n  mysql:\n    volumes:\n      - mysql_data:/var/lib/mysql\nvolumes:\n  wordpress: {}\n  mysql_data: {}\n",
        encoding="utf-8",
    )
    (app_dir / ".env").write_text("W9_POWER_PASSWORD=\nW9_HTTP_PORT_SET=9001\nW9_DB_EXPOSE=mysql\n", encoding="utf-8")
    (app_dir / ".env.external-db").write_text(
        "\n".join([
            *(f"{key}={value if key != 'W9_DB_PASSWORD_SET' else ''}" for key, value in PROFILE_SETTINGS.items() if key != "W9_HTTP_PORT_SET"),
            "W9_DATABASE_MODE=external",
            "W9_COMPOSE_EXCLUDE_SERVICES=mysql",
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


def test_external_profile_validation_accepts_base_template_install_settings(tmp_path):
    app_dir = tmp_path / "wordpress"
    _profile_template(app_dir)

    validate_profile_settings(app_dir, "external-db", PROFILE_SETTINGS)


def test_external_database_connection_settings_are_excluded_from_port_checks(tmp_path):
    app_dir = tmp_path / "wordpress"
    _profile_template(app_dir)
    database_only_settings = {
        key: value
        for key, value in PROFILE_SETTINGS.items()
        if not key.endswith("HTTP_PORT_SET")
    }

    assert is_external_database_profile(app_dir, "external-db") is True
    assert get_port_check_settings("external-db", PROFILE_SETTINGS, app_dir) == {"W9_HTTP_PORT_SET": "9001"}
    assert get_port_check_settings("external-db", database_only_settings, app_dir) == {"W9_HTTP_PORT_SET": "9001"}
    assert get_port_check_settings(None, PROFILE_SETTINGS) == PROFILE_SETTINGS


def test_external_database_type_comes_from_the_base_template(tmp_path):
    app_dir = tmp_path / "wordpress"
    _profile_template(app_dir)

    assert get_external_database_type(app_dir) == "mysql"

    (app_dir / ".env").write_text("W9_DB_EXPOSE=postgresql\n", encoding="utf-8")
    assert get_external_database_type(app_dir) == "postgresql"


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
        "mysql",
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


def test_mysql_external_database_connection_does_not_fall_back_to_postgresql(monkeypatch):
    class FakePyMySQL:
        class MySQLError(Exception):
            pass

        @staticmethod
        def connect(**kwargs):
            raise FakePyMySQL.MySQLError()

    monkeypatch.setitem(sys.modules, "pymysql", FakePyMySQL)

    with pytest.raises(CustomException) as exc_info:
        validate_external_database_connection(
            "mysql",
            host="postgres.example.internal",
            port=5432,
            database_name="wordpress_demo",
            username="wordpress_user",
            password="database-secret",
        )

    assert exc_info.value.status_code == 400


def test_mysql_external_database_connection_requires_a_database_name(monkeypatch):
    with pytest.raises(CustomException) as exc_info:
        validate_external_database_connection(
            "mysql",
            host="mysql.example.internal",
            port=3306,
            database_name=None,
            username="wordpress_user",
            password="database-secret",
        )

    assert exc_info.value.status_code == 400


def test_postgresql_external_database_connection_uses_postgresql_when_declared(monkeypatch):
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

        calls = []

        @staticmethod
        def connect(**kwargs):
            FakePsycopg2.calls.append(kwargs)
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "pymysql", FakePyMySQL)
    monkeypatch.setitem(sys.modules, "psycopg2", FakePsycopg2)

    result = validate_external_database_connection(
        "postgresql",
        host="postgres.example.internal",
        port=5432,
        database_name=None,
        username="wordpress_user",
        password="database-secret",
    )

    assert result.database_type == "postgresql"
    assert result.version == (16, 0, 3)
    assert FakePsycopg2.calls[0]["dbname"] == "postgres"


def test_profile_materialization_merges_external_database_overrides_and_prunes_compose(tmp_path):
    workspace = tmp_path / "wordpress"
    _profile_template(workspace)
    (workspace / ".env.example").write_text("DOCUMENTATION_ONLY=true\n", encoding="utf-8")

    materialize_profile_template(workspace, "external-db")

    compose_content = (workspace / "docker-compose.yml").read_text(encoding="utf-8")
    assert "wordpress" in compose_content
    assert "mysql:" not in compose_content
    assert "mysql_data" not in compose_content
    assert not list(workspace.glob("docker-compose.*.yml"))
    assert not (workspace / ".env.external-db").exists()
    assert (workspace / ".env.example").exists()
    env_content = (workspace / ".env").read_text(encoding="utf-8")
    assert "W9_DB_USER_SET=wordpress_user" in env_content
    assert "W9_DB_PASSWORD_SET=" in env_content
    assert "W9_POWER_PASSWORD=" in env_content


def test_external_profile_pruning_preserves_compose_formatting_and_partial_depends_on(tmp_path):
    workspace = tmp_path / "wordpress"
    workspace.mkdir()
    (workspace / "docker-compose.yml").write_text(
        "# image,docs: https://hub.docker.com/_/wordpress/\n"
        "\n"
        "services:\n"
        "  wordpress:\n"
        "    depends_on:\n"
        "      - mysql\n"
        "      - redis\n"
        "    volumes:\n"
        "      - wordpress:/var/www/html\n"
        "  mysql:\n"
        "    volumes:\n"
        "      - mysql_data:/var/lib/mysql\n"
        "\n"
        "volumes:\n"
        "  wordpress:\n"
        "  mysql_data:\n",
        encoding="utf-8",
    )
    (workspace / ".env").write_text("W9_POWER_PASSWORD=\nW9_HTTP_PORT_SET=9001\n", encoding="utf-8")
    (workspace / ".env.external-db").write_text(
        "\n".join([
            *(f"{key}={value if key != 'W9_DB_PASSWORD_SET' else ''}" for key, value in PROFILE_SETTINGS.items() if key != "W9_HTTP_PORT_SET"),
            "W9_DATABASE_MODE=external",
            "W9_COMPOSE_EXCLUDE_SERVICES=mysql",
        ]),
        encoding="utf-8",
    )

    materialize_profile_template(workspace, "external-db")

    compose_content = (workspace / "docker-compose.yml").read_text(encoding="utf-8")
    assert "# image,docs: https://hub.docker.com/_/wordpress/" in compose_content
    assert "mysql:" not in compose_content
    assert "mysql_data" not in compose_content
    assert "redis" in compose_content
    assert "depends_on:" in compose_content
    assert "wordpress: null" not in compose_content
    assert re.search(r"^volumes:\n  wordpress:\n", compose_content, flags=re.MULTILINE)
    assert "\n\n" in compose_content
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.exception import CustomException
from src.services.install_profile import (
    get_port_check_settings,
    materialize_profile_template,
    test_external_mysql_connection as check_external_mysql_connection,
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
    (app_dir / "docker-compose.external-mysql.yml").write_text(
        "services:\n  wordpress:\n    ports:\n      - $W9_HTTP_PORT_SET:80\n",
        encoding="utf-8",
    )
    (app_dir / ".env.external-mysql").write_text(
        "\n".join(f"{key}={value if key != 'W9_DB_PASSWORD_SET' else ''}" for key, value in PROFILE_SETTINGS.items()),
        encoding="utf-8",
    )


def test_profile_validation_uses_the_local_template_whitelist(tmp_path):
    _profile_template(tmp_path / "wordpress")

    validate_profile_settings(tmp_path / "wordpress", "external-mysql", PROFILE_SETTINGS)

    with pytest.raises(CustomException) as exc_info:
        validate_profile_settings(tmp_path / "wordpress", "external-mysql", {**PROFILE_SETTINGS, "UNAPPROVED": "value"})

    assert exc_info.value.status_code == 400
    assert "database-secret" not in exc_info.value.details


def test_profile_validation_rejects_settings_from_a_different_template(tmp_path):
    _profile_template(tmp_path / "wordpress")

    with pytest.raises(CustomException) as exc_info:
        validate_profile_settings(
            tmp_path / "wordpress",
            "external-mysql",
            {"W9_HTTP_PORT_SET": "9001"},
        )

    assert exc_info.value.status_code == 400


def test_external_mysql_connection_settings_are_excluded_from_port_checks():
    assert get_port_check_settings("external-mysql", PROFILE_SETTINGS) == {"W9_HTTP_PORT_SET": "9001"}
    assert get_port_check_settings(None, PROFILE_SETTINGS) == PROFILE_SETTINGS


def test_external_mysql_connection_test_is_read_only(monkeypatch):
    calls = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def execute(self, statement):
            calls.append(("execute", statement))

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

    check_external_mysql_connection(
        host="mysql.example.internal",
        port=3306,
        database_name="wordpress_demo",
        username="wordpress_user",
        password="database-secret",
    )

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
        ("close",),
    ]


def test_profile_materialization_preserves_the_selected_template(tmp_path):
    workspace = tmp_path / "wordpress"
    _profile_template(workspace)
    (workspace / ".env.example").write_text("DOCUMENTATION_ONLY=true\n", encoding="utf-8")

    materialize_profile_template(workspace, "external-mysql")

    assert "wordpress" in (workspace / "docker-compose.yml").read_text(encoding="utf-8")
    assert not list(workspace.glob("docker-compose.*.yml"))
    assert not (workspace / ".env.external-mysql").exists()
    assert (workspace / ".env.example").exists()
    env_content = (workspace / ".env").read_text(encoding="utf-8")
    assert "W9_DB_USER_SET=wordpress_user" in env_content
    assert "W9_DB_PASSWORD_SET=" in env_content
    assert "W9_POWER_PASSWORD" not in env_content
"""Contract tests for resolving ``database[]`` against one installation."""

from __future__ import annotations

import json

import pytest

from src.services import app_database_manager as db_module
from src.services.app_database_manager import AppDatabaseManager, EnvironmentResolver, expand_value, parse_env_text


class FakeGitea:
    def __init__(self, files: dict[str, str]):
        self.files = files

    def get_file_raw_from_repo(self, repo_name: str, file_path: str):
        return self.files.get(file_path)


class FakePortainer:
    def __init__(self, containers=None, env_by_id=None, fail=False):
        self.containers = containers or []
        self.env_by_id = env_by_id or {}
        self.fail = fail

    def get_local_endpoint_id(self):
        return 1

    def get_containers_by_stack_name(self, stack_name, endpoint_id):
        if self.fail:
            raise RuntimeError("portainer down")
        return self.containers

    def get_container_by_id(self, endpoint_id, container_id):
        if self.fail:
            raise RuntimeError("portainer down")
        return {"Config": {"Env": self.env_by_id.get(container_id, [])}}


@pytest.fixture
def wiring(monkeypatch):
    def install(files: dict[str, str], portainer=None):
        monkeypatch.setattr(db_module, "GiteaManager", lambda *a, **k: FakeGitea(files))
        monkeypatch.setattr(db_module, "PortainerManager", lambda *a, **k: portainer or FakePortainer())
        monkeypatch.setattr(db_module, "ConfigManager", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no ini")))
        return AppDatabaseManager()

    return install


def _declaration(*components) -> str:
    return json.dumps({"name": "demo", "database": list(components)})


WORD_PRESS = {
    "id": "rds",
    "providers": [
        {"type": "internal", "service": "mysql", "driver": "mysql"},
        {"type": "external", "drivers": ["mysql", "mariadb"]},
    ],
    "datasource": {
        "WORDPRESS_DB_HOST": "${host}:${port}",
        "WORDPRESS_DB_NAME": "${name}",
        "WORDPRESS_DB_USER": "${users[*].user}",
        "WORDPRESS_DB_PASSWORD": "${users[*].password}",
    },
}

WORDPRESS_COMPOSE = """
services:
  wordpress:
    env_file: .env
    environment:
      WORDPRESS_DB_HOST: ${WORDPRESS_DB_HOST}
  mysql:
    container_name: ${W9_ID}-mysql
    environment:
      MYSQL_ROOT_PASSWORD: ${W9_POWER_PASSWORD}
      MYSQL_DATABASE: wordpress
      MYSQL_USER: wordpress
      MYSQL_PASSWORD: ${W9_POWER_PASSWORD}
"""

WORDPRESS_ENV = "W9_ID=wordpress_ab12\nW9_POWER_PASSWORD='p@ss'\n"


def test_missing_declaration_keeps_the_caller_on_the_old_path(wiring):
    manager = wiring({"variables.json": json.dumps({"name": "demo"})})

    response = manager.get_databases("demo")

    assert response.declaration == "missing"
    assert response.components == []


def test_legacy_object_is_reported_instead_of_guessed(wiring):
    manager = wiring({"variables.json": json.dumps({"database": {"type": "mysql", "bundled": {"service": "db"}}})})

    response = manager.get_databases("demo")

    assert response.declaration == "legacy"
    assert response.components == []


def test_wordpress_inherits_the_type_dictionary(wiring):
    manager = wiring(
        {
            "variables.json": _declaration(WORD_PRESS),
            "docker-compose.yml": WORDPRESS_COMPOSE,
            ".env": WORDPRESS_ENV,
        }
    )

    component = manager.get_databases("demo").components[0]

    assert (component.id, component.driver, component.service) == ("rds", "mysql", "mysql")
    assert component.mode == "internal"
    assert component.host == "wordpress_ab12-mysql"
    assert component.port == 3306
    assert component.port_from_dictionary is True
    assert component.names == ["wordpress"]
    assert [(account.user, account.usage, account.password) for account in component.accounts] == [
        ("root", ["administration"], "p@ss"),
        ("wordpress", ["application"], "p@ss"),
    ]
    assert component.auth == "password"
    assert [tool.app_key for tool in component.tools] == ["phpmyadmin", "cloudbeaver"]


def test_seafile_reads_names_and_accounts_from_different_sources(wiring):
    seafile = {
        "id": "mariadb",
        "providers": [
            {"type": "internal", "service": "db", "driver": "mariadb"},
            {"type": "external", "drivers": ["mariadb", "mysql"]},
        ],
        "name": [
            "${SEAFILE_MYSQL_DB_CCNET_DB_NAME}",
            "${SEAFILE_MYSQL_DB_SEAFILE_DB_NAME}",
            "${SEAFILE_MYSQL_DB_SEAHUB_DB_NAME}",
        ],
        "users": [
            {"user": "root", "password": "${INIT_SEAFILE_MYSQL_ROOT_PASSWORD}", "usage": ["initialization", "administration"]},
            {"user": "${SEAFILE_MYSQL_DB_USER}", "password": "${SEAFILE_MYSQL_DB_PASSWORD}", "usage": ["application"]},
        ],
    }
    compose = """
services:
  seafile:
    env_file: .env
  db:
    environment:
      MYSQL_ROOT_PASSWORD: ${INIT_SEAFILE_MYSQL_ROOT_PASSWORD}
"""
    env = "\n".join(
        [
            "W9_POWER_PASSWORD=p@ss",
            "INIT_SEAFILE_MYSQL_ROOT_PASSWORD=${W9_POWER_PASSWORD}",
            "SEAFILE_MYSQL_DB_USER=seafile",
            "SEAFILE_MYSQL_DB_PASSWORD=${W9_POWER_PASSWORD}",
            "SEAFILE_MYSQL_DB_CCNET_DB_NAME=ccnet_db",
            "SEAFILE_MYSQL_DB_SEAFILE_DB_NAME=seafile_db",
            "SEAFILE_MYSQL_DB_SEAHUB_DB_NAME=seahub_db",
        ]
    )
    manager = wiring({"variables.json": _declaration(seafile), "docker-compose.yml": compose, ".env": env})

    component = manager.get_databases("demo").components[0]

    assert component.names == ["ccnet_db", "seafile_db", "seahub_db"]
    assert [(account.user, account.password) for account in component.accounts] == [
        ("root", "p@ss"),
        ("seafile", "p@ss"),
    ]


def test_empty_users_means_no_authentication(wiring):
    graylog = {
        "id": "mongodb",
        "providers": [{"type": "internal", "service": "mongodb", "driver": "mongodb"}],
        "name": ["graylog"],
        "users": [],
    }
    manager = wiring(
        {
            "variables.json": _declaration(graylog),
            "docker-compose.yml": "services:\n  mongodb:\n    image: mongo\n",
            ".env": "",
        }
    )

    component = manager.get_databases("demo").components[0]

    assert component.auth == "none"
    assert component.accounts == []
    assert component.names == ["graylog"]


def test_declared_but_unresolvable_accounts_are_unknown_not_none(wiring):
    component_decl = {
        "id": "rds",
        "providers": [{"type": "internal", "service": "db", "driver": "postgresql"}],
        "users": [{"user": "${POSTGRES_USER}", "password": "${POSTGRES_PASSWORD}"}],
    }
    manager = wiring(
        {
            "variables.json": _declaration(component_decl),
            "docker-compose.yml": "services:\n  db:\n    image: postgres\n",
            ".env": "",
        }
    )

    component = manager.get_databases("demo").components[0]

    assert component.accounts == []
    assert component.auth == "unknown"


def test_an_unresolvable_password_is_reported_as_unknown(wiring):
    component_decl = {
        "id": "rds",
        "providers": [{"type": "internal", "service": "db", "driver": "postgresql"}],
        "users": [{"user": "app", "password": "${NOT_DEFINED_ANYWHERE}"}],
    }
    manager = wiring(
        {
            "variables.json": _declaration(component_decl),
            "docker-compose.yml": "services:\n  db:\n    image: postgres\n",
            ".env": "",
        }
    )

    component = manager.get_databases("demo").components[0]

    assert [(account.user, account.password) for account in component.accounts] == [("app", None)]
    assert component.auth == "unknown"


def test_container_environment_wins_over_compose_and_env(wiring):
    component_decl = {
        "id": "rds",
        "providers": [{"type": "internal", "service": "db", "driver": "mysql"}],
        "users": [{"user": "app", "password": "${MYSQL_PASSWORD}"}],
    }
    portainer = FakePortainer(
        containers=[{"Id": "abc", "Names": ["/demo-db-1"], "Labels": {"com.docker.compose.service": "db"}}],
        env_by_id={"abc": ["MYSQL_PASSWORD=from-container"]},
    )
    manager = wiring(
        {
            "variables.json": _declaration(component_decl),
            "docker-compose.yml": "services:\n  db:\n    environment:\n      MYSQL_PASSWORD: from-compose\n",
            ".env": "MYSQL_PASSWORD=from-env\n",
        },
        portainer=portainer,
    )

    component = manager.get_databases("demo").components[0]

    assert component.accounts[0].password == "from-container"
    assert component.host == "demo-db-1"


def test_a_stopped_app_still_resolves_from_compose_and_env(wiring):
    portainer = FakePortainer(fail=True)
    manager = wiring(
        {
            "variables.json": _declaration(WORD_PRESS),
            "docker-compose.yml": WORDPRESS_COMPOSE,
            ".env": WORDPRESS_ENV,
        },
        portainer=portainer,
    )

    component = manager.get_databases("demo").components[0]

    assert component.names == ["wordpress"]
    assert component.accounts[0].password == "p@ss"
    assert component.host == "wordpress_ab12-mysql"


def test_an_unknown_service_marks_the_host(wiring):
    component_decl = {
        "id": "rds",
        "providers": [{"type": "internal", "service": "missing-service", "driver": "mysql"}],
    }
    manager = wiring(
        {
            "variables.json": _declaration(component_decl),
            "docker-compose.yml": "services:\n  db:\n    image: mysql\n",
            ".env": "",
        }
    )

    component = manager.get_databases("demo").components[0]

    assert component.host is None
    assert "host" in component.unknown_fields


def test_external_only_component_is_hidden_until_configured(wiring):
    runtime = {
        "id": "rds",
        "providers": [{"type": "external", "drivers": ["postgresql"]}],
        "datasource": {"DATABASE_URL": "${url}"},
    }
    files = {"variables.json": _declaration(runtime), "docker-compose.yml": "services: {}\n", ".env": ""}

    assert wiring(files).get_databases("demo").components == []


def test_external_mode_reads_the_platform_recorded_connection(wiring):
    # Instances installed before ``datasource`` existed kept the same values
    # under platform-owned keys; they are shown instead of being reported unknown.
    files = {
        "variables.json": _declaration(WORD_PRESS),
        "docker-compose.yml": WORDPRESS_COMPOSE,
        ".env": (
            "W9_DATABASE_MODE=external\n"
            "W9_DB_HOST_SET=db.example.com\n"
            "W9_DB_PORT_SET=3306\n"
            "W9_DB_NAME_SET=blog\n"
            "W9_DB_USER_SET=wp\n"
            "W9_DB_PASSWORD_SET=secret\n"
        ),
    }

    response = wiring(files).get_databases("demo")

    assert response.external_active is True
    component = response.components[0]
    assert component.mode == "external"
    assert component.host == "db.example.com"
    assert component.port == 3306
    assert component.names == ["blog"]
    assert component.auth == "password"
    assert component.accounts[0].user == "wp"
    assert component.accounts[0].password == "secret"


def test_external_mode_prefers_the_declared_datasource(wiring):
    files = {
        "variables.json": _declaration(WORD_PRESS),
        "docker-compose.yml": WORDPRESS_COMPOSE,
        ".env": (
            "W9_DATABASE_MODE=external\n"
            "W9_DB_HOST_SET=legacy.example.com\n"
            "W9_DB_PORT_SET=3306\n"
            "WORDPRESS_DB_HOST=aws.example.com:3307\n"
            "WORDPRESS_DB_NAME=blog\n"
            "WORDPRESS_DB_USER=wp\n"
            "WORDPRESS_DB_PASSWORD=pw\n"
        ),
    }

    component = wiring(files).get_databases("demo").components[0]

    assert (component.host, component.port) == ("aws.example.com", 3307)
    assert component.names == ["blog"]
    assert component.accounts[0].user == "wp"


def test_a_literal_dollar_in_a_password_survives(wiring):
    component_decl = {
        "id": "rds",
        "providers": [{"type": "internal", "service": "db", "driver": "mysql"}],
        "users": [{"user": "app", "password": "${MYSQL_PASSWORD}"}],
    }
    manager = wiring(
        {
            "variables.json": _declaration(component_decl),
            "docker-compose.yml": "services:\n  db:\n    image: mysql\n",
            ".env": "MYSQL_PASSWORD=p@ss$word\n",
        }
    )

    assert manager.get_databases("demo").components[0].accounts[0].password == "p@ss$word"


def test_env_file_of_the_service_is_merged(wiring):
    component_decl = {
        "id": "rds",
        "providers": [{"type": "internal", "service": "db", "driver": "mysql"}],
        "users": [{"user": "app", "password": "${EXTRA_PASSWORD}"}],
    }
    manager = wiring(
        {
            "variables.json": _declaration(component_decl),
            "docker-compose.yml": "services:\n  db:\n    env_file: db.env\n",
            "db.env": "EXTRA_PASSWORD=from-env-file\n",
            ".env": "",
        }
    )

    assert manager.get_databases("demo").components[0].accounts[0].password == "from-env-file"


# ── helpers ──────────────────────────────────────────────────────────────


def test_parse_env_text_strips_quotes_and_skips_comments():
    assert parse_env_text("# c\nA='1'\nB=2\n") == {"A": "1", "B": "2"}


def test_expand_value_handles_defaults_and_escapes():
    values = {"A": "${B}", "B": "x$$y"}

    assert expand_value("${A}", values) == ("x$y", False)
    assert expand_value("${MISSING:-fallback}", values) == ("fallback", False)
    assert expand_value("${MISSING}", values) == ("", True)


def test_resolver_keeps_unknown_nested_references_literal():
    resolver = EnvironmentResolver(project_env={"A": "p@ss$word"}, compose_env={}, container_env={})

    assert resolver.resolve("${A}") == "p@ss$word"
    assert resolver.resolve("${NOPE}") is None

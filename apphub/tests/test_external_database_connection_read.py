"""Reading the connection an external installation actually uses.

The declaration names the variables that receive the connection, so readers reverse the values out of
them. Instances installed before the declaration stored the same connection under the platform keys
(`W9_DB_*_SET`), which must keep working because those installations are never migrated.
"""

import json

from src.services import app_manager as app_module
from src.services.app_manager import AppManger

WORDPRESS_DATASOURCE = {
    "WORDPRESS_DB_HOST": "${host}:${port}",
    "WORDPRESS_DB_NAME": "${name}",
    "WORDPRESS_DB_USER": "${users[*].user}",
    "WORDPRESS_DB_PASSWORD": "${users[*].password}",
}

ODOO_DATASOURCE = {
    "HOST": "${host}",
    "PORT": "${port}",
    "USER": "${users[*].user}",
    "PASSWORD": "${users[*].password}",
}


def test_a_combined_host_and_port_target_is_split():
    env = {
        "WORDPRESS_DB_HOST": "mysql.example.internal:3306",
        "WORDPRESS_DB_NAME": "wordpress_prod",
        "WORDPRESS_DB_USER": "wordpress_user",
        "WORDPRESS_DB_PASSWORD": "secret",
    }

    connection = AppManger._external_connection(env, WORDPRESS_DATASOURCE)

    assert connection == {
        "host": "mysql.example.internal",
        "port": "3306",
        "name": "wordpress_prod",
        "user": "wordpress_user",
        "password": "secret",
    }


def test_separate_host_and_port_targets_are_read_directly():
    env = {"HOST": "postgres.example.internal", "PORT": "5432", "USER": "odoo", "PASSWORD": "secret"}

    connection = AppManger._external_connection(env, ODOO_DATASOURCE)

    assert connection["host"] == "postgres.example.internal"
    assert connection["port"] == "5432"
    assert connection["user"] == "odoo"
    assert connection["password"] == "secret"
    # The declaration has no name target, so the value stays unknown.
    assert connection["name"] == ""


def test_an_instance_without_a_declaration_falls_back_to_the_platform_keys():
    env = {
        "W9_DB_HOST_SET": "legacy.example.internal",
        "W9_DB_PORT_SET": "3307",
        "W9_DB_NAME_SET": "legacy",
        "W9_DB_USER_SET": "root",
        "W9_DB_PASSWORD_SET": "legacy-secret",
    }

    connection = AppManger._external_connection(env, {})

    assert connection == {
        "host": "legacy.example.internal",
        "port": "3307",
        "name": "legacy",
        "user": "root",
        "password": "legacy-secret",
    }


def test_a_bare_host_without_port_keeps_the_port_unknown():
    connection = AppManger._external_connection({"WORDPRESS_DB_HOST": "mysql.example.internal"}, WORDPRESS_DATASOURCE)

    assert connection["host"] == "mysql.example.internal"
    assert connection["port"] == ""


def test_inactive_instances_expose_the_variables_their_declaration_names(monkeypatch):
    files = {
        ".env": (
            "W9_APP_NAME=odoo\n"
            "W9_DATABASE_MODE=external\n"
            "HOST=postgres.example.internal\n"
            "PORT=5432\n"
            "USER=odoo\n"
            "PASSWORD=secret\n"
            "UNRELATED_SETTING=1\n"
        ),
        "variables.json": json.dumps(
            {
                "database": [
                    {
                        "id": "postgres",
                        "providers": [
                            {"type": "internal", "service": "postgresql", "driver": "postgresql"},
                            {"type": "external", "drivers": ["postgresql"]},
                        ],
                        "datasource": ODOO_DATASOURCE,
                    }
                ]
            }
        ),
    }

    class FakeGitea:
        def get_file_raw_from_repo(self, app_id, path):
            return files.get(path, "")

    monkeypatch.setattr(app_module, "GiteaManager", lambda *args, **kwargs: FakeGitea())

    env = AppManger()._read_safe_app_env_from_gitea("odoo_ab123")

    assert env["HOST"] == "postgres.example.internal"
    assert env["PORT"] == "5432"
    assert env["PASSWORD"] == "secret"
    assert "UNRELATED_SETTING" not in env


def test_an_internal_instance_does_not_gain_declared_variables(monkeypatch):
    files = {
        ".env": "W9_APP_NAME=odoo\nHOST=postgres.example.internal\nUSER=odoo\n",
        "variables.json": json.dumps({"database": [{"id": "postgres", "providers": [{"type": "internal"}]}]}),
    }

    class FakeGitea:
        def get_file_raw_from_repo(self, app_id, path):
            return files.get(path, "")

    monkeypatch.setattr(app_module, "GiteaManager", lambda *args, **kwargs: FakeGitea())

    env = AppManger()._read_safe_app_env_from_gitea("odoo_ab123")

    assert env == {"W9_APP_NAME": "odoo"}

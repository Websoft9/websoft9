"""The library is retiring ``.env.external-db`` in favour of ``database[]``.

These tests pin the compatibility contract: when the profile file exists nothing
changes, and when it is absent the declaration provides the same information.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.exception import CustomException
from src.services.external_database import (
    EXTERNAL_DATABASE_PROFILE,
    apply_datasource,
    external_database_declaration,
    external_database_profile_settings,
    read_datasource,
)
from src.services.install_profile import (
    external_database_mapping,
    is_external_database_profile,
    materialize_profile_template,
    validate_profile_settings,
)

WORDPRESS_COMPOSE = """services:
  wordpress:
    image: wordpress
    depends_on:
      - mysql
  mysql:
    image: mysql
volumes:
  mysql_data:
"""

WORD_PRESS_DECLARATION = {
    "name": "demo",
    "database": [
        {
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
    ],
}


def _workspace(root: Path, declaration=WORD_PRESS_DECLARATION, env: str = "W9_DB_EXPOSE=mysql\n") -> Path:
    app_dir = root / "wordpress"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "variables.json").write_text(json.dumps(declaration), encoding="utf-8")
    (app_dir / ".env").write_text(env, encoding="utf-8")
    (app_dir / "docker-compose.yml").write_text(WORDPRESS_COMPOSE, encoding="utf-8")
    return app_dir


# ── declaration parsing ──────────────────────────────────────────────


def test_declaration_exposes_the_three_facts_the_platform_needs(tmp_path):
    declaration = external_database_declaration(_workspace(tmp_path))

    assert declaration is not None
    assert declaration["id"] == "rds"
    assert declaration["drivers"] == ["mysql", "mariadb"]
    assert declaration["internal_services"] == ["mysql"]
    assert declaration["datasource"]["WORDPRESS_DB_HOST"] == "${host}:${port}"


def test_a_component_without_datasource_is_not_writable(tmp_path):
    # ``external.drivers`` alone describes an optional runtime, not something the
    # install form can fill in.
    declaration = {
        "database": [
            {
                "id": "rds",
                "providers": [{"type": "external", "drivers": ["postgresql"]}],
                "datasource": {},
            }
        ]
    }

    assert external_database_declaration(_workspace(tmp_path, declaration)) is None


def test_unsupported_drivers_are_not_offered(tmp_path):
    declaration = {
        "database": [
            {
                "id": "rds",
                "providers": [{"type": "external", "drivers": ["mongodb"]}],
                "datasource": {"MONGO_URL": "${url}"},
            }
        ]
    }

    assert external_database_declaration(_workspace(tmp_path, declaration)) is None


def test_profile_settings_default_the_port_for_the_declared_driver(tmp_path):
    declaration = external_database_declaration(_workspace(tmp_path))
    settings = external_database_profile_settings(declaration)

    assert settings["W9_DB_PORT_SET"] == "3306"
    assert settings["W9_DB_HOST_SET"] == ""
    assert set(settings) == {
        "W9_DB_HOST_SET",
        "W9_DB_PORT_SET",
        "W9_DB_NAME_SET",
        "W9_DB_USER_SET",
        "W9_DB_PASSWORD_SET",
    }


# ── datasource rendering and reverse parsing ─────────────────────────


def test_combined_host_and_port_is_rendered_into_one_value():
    rendered = apply_datasource(
        {"WORDPRESS_DB_HOST": "${host}:${port}", "WORDPRESS_DB_NAME": "${name}"},
        {"host": "db.example.com", "port": "3306", "name": "blog"},
    )

    assert rendered == {"WORDPRESS_DB_HOST": "db.example.com:3306", "WORDPRESS_DB_NAME": "blog"}


def test_an_unresolvable_template_is_dropped_instead_of_written_partially():
    rendered = apply_datasource({"DATABASE_URL": "${url}"}, {"host": "db"})

    assert rendered == {}


def test_reverse_parsing_splits_the_combined_value():
    values = read_datasource(
        {"WORDPRESS_DB_HOST": "${host}:${port}", "WORDPRESS_DB_USER": "${users[*].user}"},
        {"WORDPRESS_DB_HOST": "aws.example.com:3307", "WORDPRESS_DB_USER": "wp"},
    )

    assert values == {"host": "aws.example.com", "port": "3307", "user": "wp"}


def test_reverse_parsing_keeps_an_unparsable_host_as_a_host():
    values = read_datasource({"WORDPRESS_DB_HOST": "${host}:${port}"}, {"WORDPRESS_DB_HOST": "db.local"})

    assert values == {"host": "db.local"}


# ── install path without a profile file ──────────────────────────────


def test_declaration_alone_marks_the_external_profile(tmp_path):
    app_dir = _workspace(tmp_path)

    assert is_external_database_profile(app_dir, EXTERNAL_DATABASE_PROFILE) is True
    assert is_external_database_profile(app_dir, "other") is False


def test_the_profile_file_still_wins_when_present(tmp_path):
    app_dir = _workspace(tmp_path)
    (app_dir / f".env.{EXTERNAL_DATABASE_PROFILE}").write_text("W9_DATABASE_MODE=internal\n", encoding="utf-8")

    assert is_external_database_profile(app_dir, EXTERNAL_DATABASE_PROFILE) is False


def test_validate_accepts_exactly_the_connection_fields(tmp_path):
    app_dir = _workspace(tmp_path, env="W9_HTTP_PORT_SET=8080\nW9_DB_EXPOSE=mysql\n")
    settings = {
        "W9_HTTP_PORT_SET": "8080",
        "W9_DB_HOST_SET": "db",
        "W9_DB_PORT_SET": "3306",
        "W9_DB_NAME_SET": "blog",
        "W9_DB_USER_SET": "wp",
        "W9_DB_PASSWORD_SET": "pw",
    }

    validate_profile_settings(app_dir, EXTERNAL_DATABASE_PROFILE, settings)

    with pytest.raises(CustomException):
        validate_profile_settings(app_dir, EXTERNAL_DATABASE_PROFILE, {**settings, "EXTRA": "x"})


def test_materialising_drops_the_bundled_service_named_by_the_declaration(tmp_path):
    app_dir = _workspace(tmp_path)

    materialize_profile_template(app_dir, EXTERNAL_DATABASE_PROFILE)

    compose = (app_dir / "docker-compose.yml").read_text(encoding="utf-8")
    assert "mysql:" not in compose
    assert "depends_on" not in compose
    assert "wordpress:" in compose


def test_connection_values_are_written_into_the_declared_variables(tmp_path):
    app_dir = _workspace(tmp_path)

    mapping = external_database_mapping(
        app_dir,
        {
            "W9_DB_HOST_SET": "db.example.com",
            "W9_DB_PORT_SET": "3306",
            "W9_DB_NAME_SET": "blog",
            "W9_DB_USER_SET": "wp",
            "W9_DB_PASSWORD_SET": "pw",
        },
    )

    assert mapping == {
        "WORDPRESS_DB_HOST": "db.example.com:3306",
        "WORDPRESS_DB_NAME": "blog",
        "WORDPRESS_DB_USER": "wp",
        "WORDPRESS_DB_PASSWORD": "pw",
    }

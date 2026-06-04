import sys
import sqlite3
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.integration_credentials import IntegrationCredentialProvider


class FakeConfig:
    def __init__(self, values):
        self.values = values

    def get_value(self, section, key):
        return self.values[section][key]


def test_provider_prefers_runtime_credential_files(monkeypatch, tmp_path):
    gitea_path = tmp_path / "gitea.json"
    gitea_path.write_text('{"username":"gitea-user","email":"gitea@example.com","password":"gitea-pass"}', encoding="utf-8")
    portainer_path = tmp_path / "portainer.txt"
    portainer_path.write_text("portainer-pass\n", encoding="utf-8")
    npm_path = tmp_path / "npm.json"
    npm_path.write_text('{"username":"admin@example.com","password":"npm-pass","nickname":"admin"}', encoding="utf-8")

    monkeypatch.setenv("WEBSOFT9_GITEA_CREDENTIAL_PATH", str(gitea_path))
    monkeypatch.setenv("WEBSOFT9_PORTAINER_CREDENTIAL_PATH", str(portainer_path))
    monkeypatch.setenv("WEBSOFT9_NPM_CREDENTIAL_PATH", str(npm_path))
    monkeypatch.setenv("WEBSOFT9_PORTAINER_ADMIN_USER", "admin")

    provider = IntegrationCredentialProvider(
        config=FakeConfig(
            {
                "gitea": {"user_name": "fallback-user", "user_email": "fallback@example.com", "user_pwd": "fallback-pass"},
                "portainer": {"user_name": "fallback-admin", "user_pwd": "fallback-pass"},
                "nginx_proxy_manager": {"user_name": "fallback@example.com", "user_pwd": "fallback-pass", "nike_name": "fallback"},
            },
        ),
    )

    assert provider.get_gitea_credentials().username == "gitea-user"
    assert provider.get_gitea_credentials().password == "gitea-pass"
    assert provider.get_gitea_credentials().email == "gitea@example.com"
    assert provider.get_portainer_credentials().username == "admin"
    assert provider.get_portainer_credentials().password == "portainer-pass"
    assert provider.get_npm_credentials().username == "admin@example.com"
    assert provider.get_npm_credentials().password == "npm-pass"
    assert provider.get_npm_credentials().nickname == "admin"
    assert provider.get_npm_credentials().display_name == "admin"


def test_provider_falls_back_to_config_when_runtime_files_missing(monkeypatch):
    monkeypatch.delenv("WEBSOFT9_GITEA_CREDENTIAL_PATH", raising=False)
    monkeypatch.delenv("WEBSOFT9_PORTAINER_CREDENTIAL_PATH", raising=False)
    monkeypatch.delenv("WEBSOFT9_NPM_CREDENTIAL_PATH", raising=False)

    provider = IntegrationCredentialProvider(
        config=FakeConfig(
            {
                "gitea": {"user_name": "fallback-user", "user_email": "fallback@example.com", "user_pwd": "fallback-pass"},
                "portainer": {"user_name": "fallback-admin", "user_pwd": "fallback-portainer-pass"},
                "nginx_proxy_manager": {"user_name": "fallback@example.com", "user_pwd": "fallback-npm-pass", "nike_name": "fallback"},
            },
        ),
    )

    assert provider.get_gitea_credentials().username == "fallback-user"
    assert provider.get_gitea_credentials().password == "fallback-pass"
    assert provider.get_portainer_credentials().username == "fallback-admin"
    assert provider.get_portainer_credentials().password == "fallback-portainer-pass"
    assert provider.get_npm_credentials().username == "fallback@example.com"
    assert provider.get_npm_credentials().password == "fallback-npm-pass"
    assert provider.get_npm_credentials().nickname == "fallback"
    assert provider.get_npm_credentials().display_name == "fallback"


def test_provider_syncs_npm_runtime_profile_without_overriding_credential_source(monkeypatch, tmp_path):
    bcrypt = pytest.importorskip("bcrypt")

    npm_path = tmp_path / "npm.json"
    npm_path.write_text(
        '{"username":"admin@mydomain.com","password":"npm-pass","nickname":"admin","name":"Administrator"}',
        encoding="utf-8",
    )
    database_path = tmp_path / "database.sqlite"

    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            '''
            CREATE TABLE "user" (
                id INTEGER PRIMARY KEY,
                email TEXT,
                name TEXT,
                nickname TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                modified_on TEXT
            );
            CREATE TABLE auth (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                secret TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                modified_on TEXT
            );
            '''
        )
        connection.execute(
            'INSERT INTO "user" (id, email, name, nickname, is_deleted, modified_on) VALUES (?, ?, ?, ?, 0, ?)',
            (1, "admin@example.com", "Administrator", "Admin", "2024-01-01 00:00:00"),
        )
        old_secret = bcrypt.hashpw(b"old-pass", bcrypt.gensalt(rounds=4)).decode("utf-8")
        connection.execute(
            'INSERT INTO auth (id, user_id, type, secret, is_deleted, modified_on) VALUES (?, ?, ?, ?, 0, ?)',
            (1, 1, "password", old_secret, "2024-01-01 00:00:00"),
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setenv("WEBSOFT9_NPM_CREDENTIAL_PATH", str(npm_path))
    monkeypatch.setenv("WEBSOFT9_NPM_DATABASE_PATH", str(database_path))

    provider = IntegrationCredentialProvider(
        config=FakeConfig(
            {
                "gitea": {"user_name": "fallback-user", "user_email": "fallback@example.com", "user_pwd": "fallback-pass"},
                "portainer": {"user_name": "fallback-admin", "user_pwd": "fallback-portainer-pass"},
                "nginx_proxy_manager": {"user_name": "fallback@example.com", "user_pwd": "fallback-npm-pass", "nike_name": "fallback"},
            },
        ),
    )

    credentials = provider.get_npm_credentials()
    assert credentials.username == "admin@mydomain.com"
    assert provider.sync_npm_credentials(credentials) is True

    connection = sqlite3.connect(database_path)
    try:
        user_row = connection.execute('SELECT email, name, nickname FROM "user" WHERE id = 1').fetchone()
        auth_row = connection.execute("SELECT secret FROM auth WHERE id = 1").fetchone()
    finally:
        connection.close()

    assert user_row == ("admin@mydomain.com", "Administrator", "admin")
    assert auth_row is not None
    assert bcrypt.checkpw(b"npm-pass", auth_row[0].encode("utf-8"))
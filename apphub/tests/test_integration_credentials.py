import sys
from pathlib import Path


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
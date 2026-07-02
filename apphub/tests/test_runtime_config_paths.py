import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.core.config import ConfigManager
from src.services.settings_manager import SettingsManager


CONFIG_TEMPLATE = """[platform_gateway]
https_enabled = false
force_https = false
bound_domain =
ssl_cert = /tmp/platform.cert
ssl_key = /tmp/platform.key

[api_key]
key = test-api-key

[docker_mirror]
url =

[domain]
wildcard_domain = old.example.com

[initial_apps]
keys =

[product_auth]
enabled = true
protected_modules = users,files

[platform_brand]
title = Websoft9
browser_title =
logo_url = /websoft9.png
favicon_url = /favicon.ico
apple_touch_icon_url = /websoft9.png
"""


SYSTEM_TEMPLATE = """[docker_library]
path = /websoft9/library/apps
"""


def test_settings_manager_uses_runtime_config_path(tmp_path, monkeypatch):
    config_path = tmp_path / "runtime-config" / "config.ini"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_APPHUB_CONFIG_PATH", str(config_path))

    manager = SettingsManager()

    assert manager.config_file_path == str(config_path.resolve())

    section = manager.write_section("domain", "wildcard_domain", "new.example.com")

    assert section["wildcard_domain"] == "new.example.com"
    assert "wildcard_domain = new.example.com" in config_path.read_text(encoding="utf-8")


def test_config_manager_uses_runtime_system_config_path(tmp_path, monkeypatch):
    system_path = tmp_path / "runtime-config" / "system.ini"
    system_path.parent.mkdir(parents=True, exist_ok=True)
    system_path.write_text(SYSTEM_TEMPLATE, encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_APPHUB_SYSTEM_CONFIG_PATH", str(system_path))

    manager = ConfigManager("system.ini")

    assert manager.config_file_path == str(system_path.resolve())

    manager.set_value("docker_library", "path", "/persisted/library")

    assert manager.get_value("docker_library", "path") == "/persisted/library"
    assert "path = /persisted/library" in system_path.read_text(encoding="utf-8")
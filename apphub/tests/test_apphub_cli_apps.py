import json
import sys
import types
from pathlib import Path

from click.testing import CliRunner


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_service_stubs(monkeypatch, calls):
    exception_module = types.ModuleType("src.core.exception")

    class CustomException(Exception):
        def __init__(self, details=""):
            super().__init__(details)
            self.details = details
            self.message = details

    exception_module.CustomException = CustomException
    monkeypatch.setitem(sys.modules, "src.core.exception", exception_module)

    schema_module = types.ModuleType("src.schemas.appInstall")

    class Edition:
        def __init__(self, dist, version):
            self.dist = dist
            self.version = version

    class AppInstall:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    schema_module.Edition = Edition
    schema_module.appInstall = AppInstall
    monkeypatch.setitem(sys.modules, "src.schemas.appInstall", schema_module)

    check_module = types.ModuleType("src.services.common_check")
    check_module.install_validate = lambda payload, endpoint_id: calls.append(("validate", payload, endpoint_id))
    monkeypatch.setitem(sys.modules, "src.services.common_check", check_module)

    manager_module = types.ModuleType("src.services.app_manager")

    class AppManger:
        def create_installation_tracking(self, payload):
            calls.append(("track", payload))
            return "mywp_abcde", "tracking-1"

        def install_app(self, payload, endpoint_id, app_id, tracking_id):
            calls.append(("install", payload, endpoint_id, app_id, tracking_id))

    manager_module.AppManger = AppManger
    monkeypatch.setitem(sys.modules, "src.services.app_manager", manager_module)


def test_install_maps_cli_arguments_to_app_install(monkeypatch):
    from src.cli.app_commands import app_group

    calls = []
    _install_service_stubs(monkeypatch, calls)

    result = CliRunner().invoke(
        app_group,
        [
            "install",
            "wordpress",
            "--app-id",
            "mywp",
            "--version",
            "latest",
            "--domain",
            "192.0.2.10",
            "--set",
            "W9_HTTP_PORT_SET=9002",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output.splitlines()[-1]) == {"app_id": "mywp_abcde", "tracking_id": "tracking-1"}
    payload = calls[0][1]
    assert payload.settings == {"W9_HTTP_PORT_SET": "9002"}
    assert payload.proxy_enabled is True
    assert [call[0] for call in calls] == ["validate", "track", "install"]


def test_install_rejects_empty_settings_key():
    from src.cli.app_commands import app_group

    result = CliRunner().invoke(
        app_group,
        ["install", "wordpress", "--app-id", "mywp", "--version", "latest", "--domain", "192.0.2.10", "--set", "=9002"],
    )

    assert result.exit_code != 0
    assert "key cannot be empty" in result.output


def test_install_json_rejects_installation_options():
    from src.cli.app_commands import app_group

    with CliRunner().isolated_filesystem():
        with open("install.json", "w", encoding="utf-8") as handle:
            json.dump({}, handle)

        result = CliRunner().invoke(
            app_group,
            ["install", "--from-json", "install.json", "--profile", "external-db"],
        )

    assert result.exit_code != 0
    assert "profile" in result.output


def _install_local_app_store_stub(monkeypatch, refresh_local_app_store):
    local_app_store_module = types.ModuleType("src.services.local_app_store")
    local_app_store_module.refresh_local_app_store = refresh_local_app_store
    monkeypatch.setitem(sys.modules, "src.services.local_app_store", local_app_store_module)


def test_refresh_outputs_private_app_report_as_json(monkeypatch):
    from src.cli.app_commands import app_group

    _install_local_app_store_stub(
        monkeypatch,
        lambda: {"loaded": 2, "skipped": 0, "errors": []},
    )

    result = CliRunner().invoke(app_group, ["refresh", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"loaded": 2, "skipped": 0, "errors": []}


def test_refresh_returns_nonzero_when_private_apps_are_skipped(monkeypatch):
    from src.cli.app_commands import app_group

    _install_local_app_store_stub(
        monkeypatch,
        lambda: {
            "loaded": 1,
            "skipped": 1,
            "errors": [{"app": "invalid-app", "error": "missing compose file"}],
        },
    )

    result = CliRunner().invoke(app_group, ["refresh", "--json"])

    assert result.exit_code == 2
    assert json.loads(result.output) == {
        "loaded": 1,
        "skipped": 1,
        "errors": [{"app": "invalid-app", "error": "missing compose file"}],
    }


def test_refresh_surfaces_local_catalog_validation_errors(monkeypatch):
    from src.cli.app_commands import app_group

    def fail_refresh():
        raise ValueError("no valid local applications were found")

    _install_local_app_store_stub(monkeypatch, fail_refresh)

    result = CliRunner().invoke(app_group, ["refresh"])

    assert result.exit_code != 0
    assert "no valid local applications were found" in result.output
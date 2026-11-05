"""Install-time pre-checks: port conflicts, host port suggestions, and the install orchestration.

`common_check` is the last gate before an app is handed to Portainer, so a regression here either
lets two applications claim the same host port or blocks a perfectly valid install. `port_allocator`
is what the install form uses to propose ports, and it has to agree with that gate.
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.exception import CustomException
from src.services import common_check as check_module
from src.services import port_allocator as port_module
from src.services.app_status import appInstalling, appInstallingError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _clear(collection):
    for tracking_id, _payload in list(collection.items()):
        collection.pop(tracking_id)


@pytest.fixture(autouse=True)
def clean_install_state():
    # 安装状态在后端是 SQLite 集合(不是 dict),只能逐条 pop
    _clear(appInstalling)
    _clear(appInstallingError)
    yield
    _clear(appInstalling)
    _clear(appInstallingError)


def _library(tmp_path, app_name="wordpress", versions=("6.5.0", "6.4.0")):
    app_dir = tmp_path / app_name
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "variables.json").write_text(json.dumps({"edition": [{"dist": "community", "version": list(versions)}]}))
    return tmp_path


# ── template ports ────────────────────────────────────────────────────────


def test_template_ports_are_read_from_the_library_env(tmp_path, monkeypatch):
    _library(tmp_path)
    (tmp_path / "wordpress" / ".env").write_text(
        "# comment\nW9_HTTP_PORT_SET=8080\nW9_HTTPS_PORT_SET=8443\nUNRELATED=1\nbroken\n"
    )
    monkeypatch.setattr(
        check_module,
        "ConfigManager",
        lambda *args, **kwargs: SimpleNamespace(get_value=lambda section, key: str(tmp_path)),
    )

    ports = check_module._read_template_ports("wordpress")

    assert ports == {"W9_HTTP_PORT_SET": 8080, "W9_HTTPS_PORT_SET": 8443}


def test_unreadable_template_ports_are_not_fatal(monkeypatch):
    monkeypatch.setattr(
        check_module,
        "ConfigManager",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no config")),
    )

    assert check_module._read_template_ports("wordpress") == {}


def test_host_bound_ports_include_every_container_binding(monkeypatch):
    containers = [
        SimpleNamespace(attrs={"NetworkSettings": {"Ports": {"80/tcp": [{"HostPort": "9001"}]}}}),
        SimpleNamespace(
            attrs={
                "NetworkSettings": {
                    "Ports": {
                        "443/tcp": [{"HostPort": "9002"}, {"HostPort": "not-a-port"}],
                        "8080/tcp": None,
                    }
                }
            }
        ),
        SimpleNamespace(attrs={}),
    ]
    monkeypatch.setattr(
        check_module.docker,
        "from_env",
        lambda: SimpleNamespace(containers=SimpleNamespace(list=lambda: containers)),
    )

    assert check_module._get_host_bound_ports() == {9001, 9002}


def test_a_broken_docker_socket_does_not_block_an_install(monkeypatch):
    monkeypatch.setattr(
        check_module.docker,
        "from_env",
        lambda: (_ for _ in ()).throw(RuntimeError("socket gone")),
    )

    assert check_module._get_host_bound_ports() == set()


# ── port conflicts ────────────────────────────────────────────────────────


def test_no_requested_ports_means_no_conflict_check(monkeypatch):
    called = []
    monkeypatch.setattr(check_module, "_get_host_bound_ports", lambda: called.append(True) or set())

    assert check_module.check_port_conflicts({}, None) is None
    assert called == []


def test_a_port_bound_by_a_container_is_rejected(monkeypatch):
    monkeypatch.setattr(check_module, "_get_host_bound_ports", lambda: {8080})

    with pytest.raises(CustomException) as error:
        check_module.check_port_conflicts({"W9_HTTP_PORT_SET": "8080"})

    assert error.value.status_code == 400
    assert error.value.details == "Port 8080 is already in use. Please choose a different port."


def test_a_port_reserved_by_an_installing_app_is_rejected(monkeypatch):
    appInstalling["tracking-1"] = {"app_id": "wordpress_abc", "reserved_ports": {8080}}
    monkeypatch.setattr(check_module, "_get_host_bound_ports", lambda: set())

    with pytest.raises(CustomException) as error:
        check_module.check_port_conflicts({"W9_HTTP_PORT_SET": 8080})

    assert "already in use" in error.value.details


def test_settings_override_template_defaults(monkeypatch, tmp_path):
    _library(tmp_path)
    (tmp_path / "wordpress" / ".env").write_text("W9_HTTP_PORT_SET=8080\n")
    monkeypatch.setattr(
        check_module,
        "ConfigManager",
        lambda *args, **kwargs: SimpleNamespace(get_value=lambda section, key: str(tmp_path)),
    )
    monkeypatch.setattr(check_module, "_get_host_bound_ports", lambda: set())

    # 模板默认 8080 被用户改成 9090 之后,冲突检查只看 9090
    assert check_module.check_port_conflicts({"W9_HTTP_PORT_SET": "9090"}, "wordpress") is None


def test_a_non_numeric_override_is_ignored(monkeypatch):
    monkeypatch.setattr(check_module, "_get_host_bound_ports", lambda: {8080})

    assert check_module.check_port_conflicts({"W9_HTTP_PORT_SET": "auto"}) is None


# ── app name / version ────────────────────────────────────────────────────


def test_an_unknown_app_is_rejected(tmp_path):
    with pytest.raises(CustomException) as error:
        check_module.check_appName_and_appVersion("nope", "1.0.0", str(tmp_path))

    assert error.value.details == "app_name:nope not supported"


def test_an_unknown_version_is_rejected(tmp_path):
    library = _library(tmp_path)

    with pytest.raises(CustomException) as error:
        check_module.check_appName_and_appVersion("wordpress", "9.9.9", str(library))

    assert error.value.details == "app_version:9.9.9 not supported"


def test_only_exact_template_versions_are_accepted(tmp_path):
    library = _library(tmp_path)

    assert check_module.check_appName_and_appVersion("wordpress", "6.5.0", str(library)) is None
    # 版本必须与 variables.json 里的条目完全一致,前缀不算匹配
    with pytest.raises(CustomException) as error:
        check_module.check_appName_and_appVersion("wordpress", "6.5", str(library))
    assert error.value.details == "app_version:6.5 not supported"


def test_a_broken_variables_file_is_reported_as_a_server_error(tmp_path):
    app_dir = tmp_path / "wordpress"
    app_dir.mkdir()
    (app_dir / "variables.json").write_text("not json")

    with pytest.raises(CustomException) as error:
        check_module.check_appName_and_appVersion("wordpress", "1.0.0", str(tmp_path))

    assert error.value.status_code == 500
    assert error.value.details == "Internal Server Error"


# ── app id uniqueness ─────────────────────────────────────────────────────


class FakeGitea:
    def __init__(self, repo_exists=False):
        self.repo_exists = repo_exists

    def check_repo_exists(self, app_id):
        return self.repo_exists


class FakePortainer:
    def __init__(self, stack_exists=False, endpoint_exists=True):
        self.stack_exists = stack_exists
        self.endpoint_exists = endpoint_exists

    def check_stack_exists(self, app_id, endpoint_id):
        return self.stack_exists

    def check_endpoint_exists(self, endpoint_id):
        return self.endpoint_exists


def test_an_app_id_being_installed_is_rejected():
    appInstalling["tracking-1"] = {"app_id": "wordpress_abc"}

    with pytest.raises(CustomException) as error:
        check_module.check_appId("wordpress_abc", 21, FakeGitea(), FakePortainer())

    assert error.value.details == "wordpress_abc is installing"


def test_an_app_id_with_a_failed_install_is_rejected():
    # status 4 = 安装失败,`__setitem__` 默认写的是 status 3(安装中)
    appInstallingError["tracking-1"] = {"app_id": "wordpress_abc", "status": 4}

    with pytest.raises(CustomException) as error:
        check_module.check_appId("wordpress_abc", 21, FakeGitea(), FakePortainer())

    assert "already failed to install" in error.value.details


def test_an_app_id_existing_in_gitea_is_rejected():
    with pytest.raises(CustomException) as error:
        check_module.check_appId("wordpress_abc", 21, FakeGitea(repo_exists=True), FakePortainer())

    assert error.value.details == "App_id:wordpress_abc is exists(in gitea)"


def test_an_app_id_existing_in_portainer_is_rejected():
    with pytest.raises(CustomException) as error:
        check_module.check_appId("wordpress_abc", 21, FakeGitea(), FakePortainer(stack_exists=True))

    assert error.value.details == "app_id:wordpress_abc is exists(in portainer)"


def test_a_free_app_id_passes():
    assert check_module.check_appId("wordpress_abc", 21, FakeGitea(), FakePortainer()) is None


# ── endpoints and quotas ──────────────────────────────────────────────────


def test_a_missing_endpoint_is_rejected():
    with pytest.raises(CustomException) as error:
        check_module.check_endpointId(21, FakePortainer(endpoint_exists=False))

    assert error.value.details == "EndpointId Not Found"


def test_an_absent_endpoint_id_is_not_checked():
    assert check_module.check_endpointId(None, FakePortainer(endpoint_exists=False)) is None


def test_the_app_quota_counts_active_and_installing_apps(monkeypatch):
    apps = [
        SimpleNamespace(app_official=True, status=1),
        SimpleNamespace(app_official=True, status=3),
        SimpleNamespace(app_official=True, status=2),
        SimpleNamespace(app_official=False, status=1),
    ]
    monkeypatch.setattr(check_module, "read_product_edition", lambda: SimpleNamespace(max_apps=2))
    monkeypatch.setitem(
        sys.modules,
        "src.services.app_manager",
        SimpleNamespace(AppManger=lambda: SimpleNamespace(get_apps=lambda endpoint_id: apps)),
    )

    with pytest.raises(CustomException) as error:
        check_module.check_apps_number(21)

    assert error.value.details == "Exceed the maximum number of apps"


def test_an_unlimited_edition_never_checks_the_quota(monkeypatch):
    monkeypatch.setattr(check_module, "read_product_edition", lambda: SimpleNamespace(max_apps=None))

    assert check_module.check_apps_number(21) is None


# ── install orchestration ─────────────────────────────────────────────────


@pytest.fixture
def orchestration(monkeypatch, tmp_path):
    library = _library(tmp_path)
    calls = []

    monkeypatch.setattr(check_module, "PortainerManager", lambda *args, **kwargs: FakePortainer())
    monkeypatch.setattr(check_module, "GiteaManager", lambda *args, **kwargs: FakeGitea())
    monkeypatch.setattr(
        check_module,
        "ConfigManager",
        lambda *args, **kwargs: SimpleNamespace(get_value=lambda section, key: str(library)),
    )
    monkeypatch.setattr(check_module, "validate_profile_settings", lambda *args: calls.append("profile"))
    monkeypatch.setattr(check_module, "is_external_database_profile", lambda path, profile: profile == "external-db")
    monkeypatch.setattr(
        check_module,
        "validate_external_database_connection",
        lambda *args: calls.append(("external-db", args)),
    )
    monkeypatch.setattr(check_module, "get_external_database_type", lambda path: "mysql")
    monkeypatch.setattr(check_module, "get_port_check_settings", lambda *args: {"W9_HTTP_PORT_SET": 8080})
    monkeypatch.setattr(check_module, "check_port_conflicts", lambda settings, app: calls.append(("ports", settings)))
    monkeypatch.setattr(check_module, "check_domain_names", lambda domains: calls.append(("domains", domains)))
    monkeypatch.setattr(check_module, "check_appId", lambda *args: calls.append("app-id"))
    monkeypatch.setattr(check_module, "check_endpointId", lambda *args: calls.append("endpoint"))
    return SimpleNamespace(calls=calls, library=library)


def _install_payload(**overrides):
    from src.schemas.appInstall import appInstall

    payload = {
        "app_name": "wordpress",
        "edition": {"dist": "community", "version": "6.5.0"},
        "app_id": "wordpressabc",
        "proxy_enabled": True,
        "domain_names": ["wordpress.example.com"],
    }
    payload.update(overrides)
    return appInstall(**payload)


def test_install_validation_runs_every_gate(orchestration):
    check_module.install_validate(_install_payload(), 21)

    assert "profile" in orchestration.calls
    assert "app-id" in orchestration.calls
    assert "endpoint" in orchestration.calls
    assert ("domains", ["wordpress.example.com"]) in orchestration.calls
    assert ("ports", {"W9_HTTP_PORT_SET": 8080}) in orchestration.calls


def test_install_validation_skips_the_proxy_check_without_a_proxy(orchestration):
    check_module.install_validate(_install_payload(proxy_enabled=False, domain_names=["192.0.2.10"]), 21)

    assert not any(call[0] == "domains" for call in orchestration.calls if isinstance(call, tuple))


def test_install_validation_checks_the_external_database_connection(orchestration):
    check_module.install_validate(
        _install_payload(
            profile="external-db",
            settings={
                "W9_DB_HOST_SET": "db.example.com",
                "W9_DB_PORT_SET": "3306",
                "W9_DB_NAME_SET": "wordpress",
                "W9_DB_USER_SET": "wp",
                "W9_DB_PASSWORD_SET": "secret",
            },
        ),
        21,
    )

    external = [call for call in orchestration.calls if isinstance(call, tuple) and call[0] == "external-db"]
    assert external[0][1] == ("mysql", "db.example.com", "3306", "wordpress", "wp", "secret")
    # 外部数据库方案不检查模板里的本地端口
    assert ("ports", {"W9_HTTP_PORT_SET": 8080}) in orchestration.calls


def test_install_validation_propagates_a_failed_gate(orchestration, monkeypatch):
    def failing(*args, **kwargs):
        raise CustomException(400, "Invalid Request", "boom")

    monkeypatch.setattr(check_module, "check_appId", failing)

    with pytest.raises(CustomException) as error:
        check_module.install_validate(_install_payload(), 21)

    assert error.value.details == "boom"


def test_unexpected_errors_are_wrapped(orchestration, monkeypatch):
    def exploding(*args):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(check_module, "validate_profile_settings", exploding)

    with pytest.raises(CustomException) as error:
        check_module.install_validate(_install_payload(), 21)

    assert error.value.status_code == 500
    assert error.value.details == "Internal Server Error"


# ── port range configuration ──────────────────────────────────────────────


def _config_file(tmp_path, content):
    path = tmp_path / "config.ini"
    path.write_text(content)
    return path


def test_the_default_port_range_is_used_without_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(port_module, "resolve_apphub_config_path", lambda name: str(tmp_path / "missing.ini"))

    assert port_module.read_port_range() == port_module.DEFAULT_PORT_RANGE


def test_a_configured_port_range_is_used(monkeypatch, tmp_path):
    path = _config_file(tmp_path, "[port_allocation]\nrange = 12000-12100\n")
    monkeypatch.setattr(port_module, "resolve_apphub_config_path", lambda name: str(path))

    assert port_module.read_port_range() == (12000, 12100)


@pytest.mark.parametrize("value", ["12000", "12100-12000", "0-10", "1-70000", "auto"])
def test_an_invalid_port_range_falls_back_to_the_default(monkeypatch, tmp_path, value):
    path = _config_file(tmp_path, f"[port_allocation]\nrange = {value}\n")
    monkeypatch.setattr(port_module, "resolve_apphub_config_path", lambda name: str(path))

    assert port_module.read_port_range() == port_module.DEFAULT_PORT_RANGE


def test_an_unreadable_configuration_falls_back_to_the_default(monkeypatch):
    monkeypatch.setattr(
        port_module,
        "resolve_apphub_config_path",
        lambda name: (_ for _ in ()).throw(RuntimeError("no config")),
    )

    assert port_module.read_port_range() == port_module.DEFAULT_PORT_RANGE


# ── port sources ──────────────────────────────────────────────────────────


def test_container_port_sources_include_stopped_containers(monkeypatch):
    containers = [
        SimpleNamespace(attrs={"HostConfig": {"PortBindings": {"80/tcp": [{"HostPort": "9001"}]}}}),
        SimpleNamespace(attrs={"HostConfig": {"PortBindings": {"80/tcp": None}}}),
        SimpleNamespace(attrs={}),
    ]
    monkeypatch.setattr(
        port_module.docker,
        "from_env",
        lambda: SimpleNamespace(containers=SimpleNamespace(list=lambda all=False: containers)),
    )

    assert port_module._container_port_sources() == {9001: "container"}


def test_a_broken_docker_socket_yields_no_container_ports(monkeypatch):
    monkeypatch.setattr(port_module.docker, "from_env", lambda: (_ for _ in ()).throw(RuntimeError("gone")))

    assert port_module._container_port_sources() == {}


def test_installing_port_sources_come_from_the_install_tasks(monkeypatch):
    tasks = [
        ("tracking-1", {"reserved_ports": {9002, "not-a-port"}}),
        ("tracking-2", {"reserved_ports": None}),
    ]
    monkeypatch.setattr(port_module, "list_install_tasks_readonly", lambda statuses: tasks)

    assert port_module._installing_port_sources() == {9002: "installing"}


def test_an_install_task_read_failure_yields_no_ports(monkeypatch):
    monkeypatch.setattr(
        port_module,
        "list_install_tasks_readonly",
        lambda statuses: (_ for _ in ()).throw(RuntimeError("db locked")),
    )

    assert port_module._installing_port_sources() == {}


def test_installing_ports_take_precedence_over_container_ports(monkeypatch):
    monkeypatch.setattr(port_module, "_container_port_sources", lambda: {9001: "container"})
    monkeypatch.setattr(port_module, "_installing_port_sources", lambda: {9001: "installing"})

    assert port_module.collect_port_sources() == {9001: "installing"}


# ── suggestions and checks ────────────────────────────────────────────────


def test_ports_are_suggested_from_the_configured_range(monkeypatch):
    monkeypatch.setattr(port_module, "read_port_range", lambda: (9001, 9005))
    monkeypatch.setattr(port_module, "collect_port_sources", lambda: {9001: "container", 9003: "installing"})

    suggestions = port_module.suggest_ports(["A", "B", "C"])

    assert suggestions == [
        {"key": "A", "port": 9002},
        {"key": "B", "port": 9004},
        {"key": "C", "port": 9005},
    ]


def test_an_exhausted_range_suggests_no_port(monkeypatch):
    monkeypatch.setattr(port_module, "read_port_range", lambda: (9001, 9002))
    monkeypatch.setattr(port_module, "collect_port_sources", lambda: {9001: "container", 9002: "container"})

    assert port_module.suggest_ports(["A", "B"]) == [
        {"key": "A", "port": None},
        {"key": "B", "port": None},
    ]


def test_no_keys_means_no_suggestions(monkeypatch):
    monkeypatch.setattr(port_module, "read_port_range", lambda: (9001, 9002))

    assert port_module.suggest_ports([]) == []


def test_port_checks_explain_why_a_port_is_taken(monkeypatch):
    monkeypatch.setattr(port_module, "collect_port_sources", lambda: {9001: "container"})

    assert port_module.check_ports([9001, 9002]) == [
        {"port": 9001, "available": False, "reason": "container"},
        {"port": 9002, "available": True, "reason": None},
    ]


def test_the_default_range_matches_the_shipped_configuration():
    # 安装表单默认值来自 DEFAULT_PORT_RANGE_VALUE,两者必须一致
    minimum, maximum = port_module.DEFAULT_PORT_RANGE
    assert port_module.DEFAULT_PORT_RANGE_VALUE == f"{minimum}-{maximum}"
    assert os.environ.get("WEBSOFT9_PORT_RANGE_OVERRIDE") is None

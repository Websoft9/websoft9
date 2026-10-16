import sys
import json
import io
import tarfile
import pytest
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services import app_access_manager as app_access_manager_module
from src.services.app_access_manager import AppAccessManager


def test_runtime_credentials_only_discover_supported_sources_and_login_help(monkeypatch):
    template = {"credentials": {"token": {"source": "container-log"}, "password": {"source": "container-env"}}, "help": {"login": "Use setup token", "db": "Ignore database hint"}}
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps(template)))
    rules, help_text = AppAccessManager()._credential_rules("portainer_demo", SimpleNamespace(app_name="portainer"))
    assert list(rules) == ["token"]
    assert help_text == "Use setup token"
    static_only = {"credentials": {"username": {"source": "inline", "value": "admin"}, "password": {"source": "container-env", "name": "W9_LOGIN_PASSWORD"}}}
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps(static_only)))
    assert AppAccessManager()._credential_rules("static_demo", SimpleNamespace(app_name="custom")) == ({}, None)


def test_staged_initial_and_login_credentials_discover_initial_runtime_rules(monkeypatch):
    graylog_template = {
        "credentials": {
            "initial": {
                "username": {"source": "inline", "value": "admin"},
                "password": {
                    "source": "container-log",
                    "match": "regex",
                    "pattern": "username 'admin' and password '([^']+)'",
                    "group": 1,
                },
            },
            "login": {
                "username": {"source": "inline", "value": "admin"},
                "password": {"source": "container-env", "name": "W9_LOGIN_PASSWORD"},
            },
        },
        "help": {"login": "First run: read the temporary admin password from the container logs"},
    }
    app = SimpleNamespace(app_name="graylog", endpointId=1, containers=[{"Id": "main", "Names": ["/graylog_demo"]}])
    log_payload = b"Initial configuration is accessible at 0.0.0.0:9000, with username 'admin' and password 'temp-secret'.\n"
    monkeypatch.setattr(app_access_manager_module, "AppManger", lambda: SimpleNamespace(get_app_by_id=lambda *args: app))
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps(graylog_template)))
    monkeypatch.setattr(app_access_manager_module, "PortainerManager", lambda: SimpleNamespace(portainer=SimpleNamespace(read_container_output=lambda *args: log_payload)))
    manager = AppAccessManager()

    rules, help_text = manager._credential_rules("graylog_demo", app)
    assert list(rules) == ["password"]
    assert rules["password"]["source"] == "container-log"
    assert help_text == graylog_template["help"]["login"]
    result = manager.resolve_credential("graylog_demo", "password", 1)
    assert result.status == "ready"
    assert "temp-secret" in (result.content or "")


def test_runtime_log_returns_all_original_content_and_reports_missing_initialization(monkeypatch):
    app = SimpleNamespace(app_name="dsh", endpointId=7, containers=[{"Id": "owned", "Names": ["/dsh_demo"]}])
    template = {"credentials": {"token": {"source": "container-log", "match": "regex", "pattern": "token=([^\\s]+)", "group": 1}}}
    output = {"raw": b"startup\ntoken=DEMO\nlater output\n"}
    calls = []
    def read_output(*args):
        calls.append(args)
        return output["raw"]
    monkeypatch.setattr(app_access_manager_module, "AppManger", lambda: SimpleNamespace(get_app_by_id=lambda *args: app))
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps(template)))
    monkeypatch.setattr(app_access_manager_module, "PortainerManager", lambda: SimpleNamespace(portainer=SimpleNamespace(read_container_output=read_output)))
    manager = AppAccessManager()
    result = manager.resolve_credential("dsh_demo", "token", 7)
    assert result.status == "ready"
    assert result.content == output["raw"].decode()
    assert calls[0][:3] == (7, "owned", "logs")
    assert calls[0][3]["tail"] == "all"
    output["raw"] = b"only later output"
    result = manager.resolve_credential("dsh_demo", "token", 7)
    assert result.status == "unavailable"
    assert result.content is None


def test_runtime_log_decoder_preserves_order_and_handles_tty():
    def frame(stream, payload):
        return bytes([stream, 0, 0, 0]) + len(payload).to_bytes(4, "big") + payload
    assert AppAccessManager._decode_container_logs(frame(1, b"hello\n") + frame(2, b"warning\n")) == "hello\nwarning\n"
    assert AppAccessManager._decode_container_logs(b"plain tty output") == "plain tty output"


def test_runtime_file_reads_only_regular_template_file_and_rejects_other_containers(monkeypatch):
    app = SimpleNamespace(app_name="jenkins", endpointId=1, containers=[{"Id": "main", "Names": ["/jenkins_demo"]}])
    rule = {"source": "container-file", "path": "/var/jenkins_home/secrets/initialAdminPassword", "format": "text"}
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as bundle:
        member = tarfile.TarInfo("initialAdminPassword")
        member.size = len(b"DEMO-PASSWORD\n")
        bundle.addfile(member, io.BytesIO(b"DEMO-PASSWORD\n"))
    calls = []
    def read_output(*args):
        calls.append(args)
        return raw.getvalue()
    monkeypatch.setattr(app_access_manager_module, "AppManger", lambda: SimpleNamespace(get_app_by_id=lambda *args: app))
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps({"credentials": {"password": rule}})))
    monkeypatch.setattr(app_access_manager_module, "PortainerManager", lambda: SimpleNamespace(portainer=SimpleNamespace(read_container_output=read_output)))
    manager = AppAccessManager()
    assert manager.resolve_credential("jenkins_demo", "password").content == "DEMO-PASSWORD"
    assert calls[0][3] == {"path": rule["path"]}
    app.containers = [{"Id": "other", "Names": ["/unrelated"]}]
    assert manager.resolve_credential("jenkins_demo", "password").error_code == "container_unavailable"
    assert len(calls) == 1
    app.containers = [{"Id": "main", "Names": ["/jenkins_demo"]}]
    rule["path"] = "/unsafe/../secret"
    assert manager.resolve_credential("jenkins_demo", "password").error_code == "invalid_rule"
    assert len(calls) == 1


def test_runtime_errors_do_not_return_partial_content_or_exception_secrets(monkeypatch):
    app = SimpleNamespace(app_name="vault", endpointId=1, containers=[{"Id": "main", "Names": ["/vault_demo"]}])
    rule = {"source": "container-log", "match": "regex", "pattern": "Root Token:"}
    def fail_output(*args):
        raise OverflowError("SECRET MUST NOT LEAK")
    monkeypatch.setattr(app_access_manager_module, "AppManger", lambda: SimpleNamespace(get_app_by_id=lambda *args: app))
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps({"credentials": {"token": rule}})))
    monkeypatch.setattr(app_access_manager_module, "PortainerManager", lambda: SimpleNamespace(portainer=SimpleNamespace(read_container_output=fail_output)))
    result = AppAccessManager().resolve_credential("vault_demo", "token")
    assert result.error_code == "output_too_large"
    assert result.content is None
    assert "SECRET" not in result.model_dump_json()


def test_runtime_transport_limits_output_and_closes_response(monkeypatch):
    from src.external.portainer_api import PortainerAPI
    api = PortainerAPI.__new__(PortainerAPI)
    class FakeResponse:
        status_code = 200
        closed = False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.closed = True
        def iter_content(self, chunk_size):
            yield b"first"
            yield b"second"
    response = FakeResponse()
    monkeypatch.setattr(api, "_container_output_response", lambda *args: response)
    with pytest.raises(OverflowError):
        api.read_container_output(1, "owned", "logs", {}, 8)
    assert response.closed
    response = FakeResponse()
    assert api.read_container_output(1, "owned", "logs", {}, 20) == b"firstsecond"
    assert response.closed
    response.status_code = 404
    assert api.read_container_output(1, "owned", "archive", {}, 20) is None


def test_container_command_transport_uses_tty_and_bounds_output(monkeypatch):
    import sys
    from src.external.portainer_api import PortainerAPI
    class WebSocketClosed(Exception):
        pass
    websocket_stub = SimpleNamespace(WebSocketConnectionClosedException=WebSocketClosed)
    monkeypatch.setitem(sys.modules, "websocket", websocket_stub)
    api = PortainerAPI.__new__(PortainerAPI)
    api.api = SimpleNamespace(
        base_url="http://portainer/api",
        headers={},
        verify=False,
        post=lambda **kwargs: SimpleNamespace(status_code=201, json=lambda: {"Id": "exec-id"}),
    )
    monkeypatch.setattr("src.external.portainer_api.JWTManager.get_token", lambda: "test-token")
    monkeypatch.setattr("src.external.portainer_api.time.monotonic", lambda: 0)
    class FakeSocket:
        def __init__(self):
            self.sent = None
            self.closed = False
            self.chunks = iter([b"token output", WebSocketClosed()])
        def send(self, content):
            self.sent = json.loads(content)
        def recv(self):
            chunk = next(self.chunks)
            if isinstance(chunk, Exception):
                raise chunk
            return chunk
        def close(self):
            self.closed = True
    fake_socket = FakeSocket()
    calls = []
    websocket_stub.create_connection = lambda *args, **kwargs: (calls.append((args, kwargs)) or fake_socket)

    assert api.run_container_command(3, "owned", ["openclaw", "gateway", "auth-token", "--show"], 100) == "token output"
    assert calls[0][0][0] == "ws://portainer/api/websocket/exec?endpointId=3&id=exec-id"
    assert calls[0][1]["header"] == {"Authorization": "Bearer test-token"}
    assert fake_socket.sent is None
    assert fake_socket.closed


def test_runtime_route_requires_auth_and_prevents_caching(monkeypatch):
    from fastapi import Response
    from src.api.v1.routers import app as router_module
    called = []
    class FakeAuth:
        def _require_authenticated_operator(self, token):
            if token != "valid":
                raise app_access_manager_module.CustomException(401, "Authentication Required", "Login required")
    def resolve(*args):
        called.append(args)
        return {"field": "token", "source": "container-log", "status": "ready", "content": "DEMO"}
    monkeypatch.setattr(router_module, "ProductAuthService", FakeAuth)
    monkeypatch.setattr(router_module, "AppAccessManager", lambda: SimpleNamespace(resolve_credential=resolve))
    with pytest.raises(app_access_manager_module.CustomException):
        router_module.read_app_credential(Response(), "dsh_demo", "token", 1, None)
    assert not called
    response = Response()
    assert router_module.read_app_credential(response, "dsh_demo", "token", 1, "valid")["content"] == "DEMO"
    assert response.headers["cache-control"] == "no-store"
    assert called == [("dsh_demo", "token", 1)]


def test_cli_route_requires_auth_and_prevents_caching(monkeypatch):
    from fastapi import Response
    from src.api.v1.routers import app as router_module
    from src.schemas.appAccess import AppCliCommandRequest
    called = []
    class FakeAuth:
        def _require_authenticated_operator(self, token):
            if token != "valid":
                raise app_access_manager_module.CustomException(401, "Authentication Required", "Login required")
    def execute(*args):
        called.append(args)
        return {"command": args[1], "status": "ready", "output": "TOKEN"}
    monkeypatch.setattr(router_module, "ProductAuthService", FakeAuth)
    monkeypatch.setattr(router_module, "AppAccessManager", lambda: SimpleNamespace(execute_cli_command=execute))
    payload = AppCliCommandRequest(command="openclaw gateway auth-token --show")
    with pytest.raises(app_access_manager_module.CustomException):
        router_module.execute_app_cli_command(Response(), payload, "openclaw_demo", 1, None)
    assert not called
    response = Response()
    result = router_module.execute_app_cli_command(response, payload, "openclaw_demo", 1, "valid")
    assert result["output"] == "TOKEN"
    assert response.headers["cache-control"] == "no-store"
    assert called == [("openclaw_demo", payload.command, 1)]


@pytest.mark.parametrize("app_name", ["openclaw", "graylog", "ghost", "metabase", "seafile"])
def test_apps_without_runtime_credential_rules_return_empty(monkeypatch, app_name):
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: '{"credentials": {"login": {"password": {"source": "container-env", "name": "W9_LOGIN_PASSWORD"}}}}'))
    assert AppAccessManager()._credential_rules("example", SimpleNamespace(app_name=app_name)) == ({}, None)

def test_openclaw_cli_commands_are_allowlisted_and_run_fixed_argv(monkeypatch):
    app = SimpleNamespace(app_name="openclaw", endpointId=1, containers=[{"Id": "main", "Names": ["/openclaw_demo"]}])
    calls = []
    template = {"cli_commands": [
        {"id": "show-token", "command": "openclaw gateway auth-token --show", "argv": ["openclaw", "gateway", "auth-token", "--show"]},
        {"id": "generate-token", "command": "openclaw doctor --generate-gateway-token", "argv": ["openclaw", "doctor", "--generate-gateway-token"], "action": "generate"},
    ]}
    monkeypatch.setattr(app_access_manager_module, "AppManger", lambda: SimpleNamespace(get_app_by_id=lambda *args: app))
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps(template)))
    monkeypatch.setattr(app_access_manager_module, "PortainerManager", lambda: SimpleNamespace(portainer=SimpleNamespace(
        run_container_command=lambda *args, **kwargs: (calls.append((args, kwargs)) or "TOKEN"),
    )))
    manager = AppAccessManager()

    commands = manager._cli_commands("openclaw_demo", app)
    assert [item["command"] for item in commands] == [
        "openclaw gateway auth-token --show",
        "openclaw doctor --generate-gateway-token",
    ]
    assert all(item["field"] == "token" for item in commands)
    result = manager.execute_cli_command("openclaw_demo", commands[0]["command"], 1)
    assert result == {"command": commands[0]["command"], "status": "ready", "output": "TOKEN"}
    assert calls[0][0] == (1, "main", ["openclaw", "gateway", "auth-token", "--show"], app_access_manager_module.MAX_CLI_OUTPUT_BYTES)
    with pytest.raises(app_access_manager_module.CustomException):
        manager.execute_cli_command("openclaw_demo", "openclaw sh -c id", 1)


def test_openclaw_without_declared_cli_commands_has_no_initial_credentials(monkeypatch):
    app = SimpleNamespace(app_name="openclaw")
    monkeypatch.setattr(app_access_manager_module, "AppManger", lambda: SimpleNamespace(get_app_by_id=lambda *args: app))
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: '{"credentials": {}}'))
    manager = AppAccessManager()

    assert manager._cli_commands("openclaw_demo", app) == []
    assert manager._credential_rules("openclaw_demo", app) == ({}, None)
    for command in ["openclaw gateway auth-token --show", "openclaw doctor --generate-gateway-token"]:
        with pytest.raises(app_access_manager_module.CustomException):
            manager.execute_cli_command("openclaw_demo", command, 1)


def test_login_help_is_available_without_dynamic_credentials(monkeypatch):
    template = {"help": {"login": "Complete setup before signing in"}}
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps(template)))
    assert AppAccessManager()._login_help("static_demo") == template["help"]["login"]


def test_cli_output_removes_terminal_controls_without_extracting_credentials():
    raw = "\x1b[?25l\x1b[90m\x1b[2K\x1b[38;5;209mOpenClaw\x1b[39m\r\n\x1b]0;Title\x07startup\r\n\r\nDEMO-TOKEN\r\n\x1b[?25h"
    assert AppAccessManager._plain_cli_output(raw) == "OpenClaw\nstartup\n\nDEMO-TOKEN\n"
    assert AppAccessManager._plain_cli_output("first\nsecond\n") == "first\nsecond\n"


def test_cli_template_declares_password_field(monkeypatch):
    template = {"cli_commands": [{"id": "show-password", "command": "app show-password", "argv": ["app", "show-password"], "field": "password"}]}
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps(template)))
    commands = AppAccessManager()._cli_commands("jenkins_demo", SimpleNamespace(app_name="jenkins"))
    assert commands[0]["field"] == "password"


def test_credential_container_selection_uses_service_or_unique_main_container():
    main = {"Id": "main", "Names": ["/demo"], "Labels": {"com.docker.compose.service": "gateway"}}
    init = {"Id": "init", "Names": ["/demo-init"], "Labels": {"com.docker.compose.service": "init"}}
    app = SimpleNamespace(containers=[main, init])
    manager = AppAccessManager()
    assert manager._credential_containers("demo", app, {}) == [main]
    assert manager._credential_containers("demo", app, {"service": "init"}) == [init]
    assert manager._credential_containers("demo", app, {"service": "missing"}) == []
    assert manager._credential_containers("demo", app, {"service": ""}) == []
    app.containers.append(dict(init))
    assert len(manager._credential_containers("demo", app, {"service": "init"})) == 2

def test_build_candidates_supports_multi_container_and_multi_port_compose_layout():
    manager = AppAccessManager()

    containers = [
        {
            "Names": ["/gateway"],
            "Ports": [
                {"PrivatePort": 80, "PublicPort": 18080},
                {"PrivatePort": 443, "PublicPort": 18443},
                {"PrivatePort": 9001, "PublicPort": 19001},
            ],
        },
        {
            "Names": ["/app"],
            "Ports": [
                {"PrivatePort": 8080, "PublicPort": 18081},
            ],
        },
        {
            "Names": ["/redis"],
            "Ports": [
                {"PrivatePort": 6379},
            ],
        },
    ]

    candidates = manager._build_candidates(containers)

    assert [(candidate.container_name, candidate.forward_port) for candidate in candidates] == [
        ("gateway", 80),
        ("gateway", 443),
        ("gateway", 9001),
        ("app", 8080),
        ("redis", 6379),
    ]
    assert candidates[0].published_ports == ["18080:80", "18443:443", "19001:9001"]
    assert candidates[3].published_ports == ["18081:8080"]


def test_save_domain_binding_updates_existing_single_builtin_proxy_without_proxy_id(monkeypatch):
    manager = AppAccessManager()
    called = {}

    class FakeAppManager:
        def get_app_by_id(self, app_id, endpoint_id=None):
            return SimpleNamespace(app_dist='community', env={'W9_HTTP_PORT': '80'})

        def update_proxy_by_app(self, proxy_id, domains, endpoint_id=None, certificate_id=None, ssl_forced=None):
            called['proxy_id'] = proxy_id
            called['domains'] = domains
            called['certificate_id'] = certificate_id
            called['ssl_forced'] = ssl_forced
            return {
                'proxy_id': proxy_id,
                'domain_names': domains,
                'certificate_id': certificate_id,
                'ssl_forced': ssl_forced,
            }

        def create_proxy_by_app(self, *args, **kwargs):
            raise AssertionError('create_proxy_by_app should not be called when a single proxy already exists')

    monkeypatch.setattr(app_access_manager_module, 'AppManger', lambda: FakeAppManager())
    monkeypatch.setattr(manager, '_resolve_profile', lambda app_id, app: SimpleNamespace(enabled=True, forward_host='wordpress_us3f2', forward_port=80, forward_scheme='http', locked=True))
    monkeypatch.setattr(manager, '_resolve_builtin_profile', lambda app_id, app: SimpleNamespace(enabled=True, forward_host='wordpress_us3f2', forward_port=80, forward_scheme='http', locked=True))
    monkeypatch.setattr(manager, '_get_proxy_hosts', lambda app_id, profile: [{'id': 7, 'domain_names': ['wp.create.websoft9.cn'], 'forward_host': 'wordpress_us3f2'}])

    result = manager.save_domain_binding('wordpress_us3f2', ['wp.create.websoft9.cn'], None, False, None, None)

    assert called['proxy_id'] == 7
    assert called['domains'] == ['wp.create.websoft9.cn']
    assert result['proxy_id'] == 7


def test_save_domain_binding_rejects_domains_used_by_other_proxy(monkeypatch):
    manager = AppAccessManager()

    class FakeAppManager:
        def get_app_by_id(self, app_id, endpoint_id=None):
            return SimpleNamespace(app_dist='community', env={'W9_HTTP_PORT': '80'})

    class FakeProxyManager:
        @staticmethod
        def to_proxy_host_response(proxy_host):
            return proxy_host

        def check_proxy_host_exists(self, domains, exclude_proxy_id=None):
            raise app_access_manager_module.CustomException(400, 'Invalid Request', "['wp.create.websoft9.cn'] already used")

    monkeypatch.setattr(app_access_manager_module, 'AppManger', lambda: FakeAppManager())
    monkeypatch.setattr(app_access_manager_module, 'ProxyManager', FakeProxyManager)
    monkeypatch.setattr(manager, '_resolve_profile', lambda app_id, app: SimpleNamespace(enabled=True, forward_host='wordpress_us3f2', forward_port=80, forward_scheme='http', locked=True))
    monkeypatch.setattr(manager, '_resolve_builtin_profile', lambda app_id, app: SimpleNamespace(enabled=True, forward_host='wordpress_us3f2', forward_port=80, forward_scheme='http', locked=True))
    monkeypatch.setattr(manager, '_get_proxy_hosts', lambda app_id, profile: [])

    try:
        manager.save_domain_binding('wordpress_us3f2', ['wp.create.websoft9.cn'], None, False, None, None)
    except app_access_manager_module.CustomException as exc:
        assert exc.status_code == 400
        assert exc.details == "['wp.create.websoft9.cn'] already used"
    else:
        raise AssertionError('Expected duplicate-domain validation to reject the binding')


def test_resolve_profile_reads_access_default_scheme_https(monkeypatch):
    manager = AppAccessManager()
    template = {"access": {"defaultScheme": "https", "web": {"port": 8080, "path": "/"}}}
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps(template)))
    app = SimpleNamespace(app_dist="community", env={"W9_HTTP_PORT": "8080"})

    profile = manager._resolve_profile("rancher_demo", app)

    assert profile.default_scheme == "https"
    assert profile.require_https is True
    assert profile.forward_scheme == "http"
    assert profile.forward_port == 8080


def test_https_required_app_enforces_inner_cert_fallback_and_ssl_forced(monkeypatch):
    manager = AppAccessManager()
    template = {"access": {"defaultScheme": "https"}}
    monkeypatch.setattr(app_access_manager_module, "GiteaManager", lambda: SimpleNamespace(get_file_raw_from_repo=lambda *args: json.dumps(template)))
    created_calls = []
    updated_calls = []

    class FakeAppManager:
        def get_app_by_id(self, app_id, endpoint_id=None):
            return SimpleNamespace(app_dist="community", env={"W9_HTTP_PORT": "8080"})

        def create_proxy_by_app(self, app_id, domains, endpoint_id=None, certificate_id=None, ssl_forced=False):
            created_calls.append((app_id, domains, certificate_id, ssl_forced))
            return {"id": 11, "domain_names": domains, "certificate_id": certificate_id, "ssl_forced": ssl_forced}

    class FakeProxyManager:
        @staticmethod
        def to_proxy_host_response(proxy_host):
            return proxy_host

        def check_proxy_host_exists(self, domains, exclude_proxy_id=None):
            return False

        def ensure_inner_certificate(self):
            return {"id": 99, "nice_name": "websoft9-inner", "provider": "other"}

        def request_letsencrypt_certificate(self, email, domain_names, proxy_id=None, ssl_forced=None):
            raise app_access_manager_module.CustomException(400, "Invalid Request", "DNS lookup failed")

        def update_proxy_by_app(self, proxy_id, domain_names, certificate_id=None, ssl_forced=None):
            updated_calls.append((proxy_id, domain_names, certificate_id, ssl_forced))
            return {"id": proxy_id, "domain_names": domain_names, "certificate_id": certificate_id, "ssl_forced": ssl_forced}

    monkeypatch.setattr(app_access_manager_module, "AppManger", lambda: FakeAppManager())
    monkeypatch.setattr(app_access_manager_module, "ProxyManager", FakeProxyManager)
    monkeypatch.setattr(manager, "_get_proxy_hosts", lambda app_id, profile: [{"id": 11, "domain_names": ["rancher.example.com"], "forward_host": "rancher_demo"}])

    binding = manager.save_domain_binding("rancher_demo", ["new.example.com"], None, False, None, None)
    assert created_calls == [("rancher_demo", ["new.example.com"], 99, True)]
    assert binding["certificate_id"] == 99
    assert binding["ssl_forced"] is True

    cert = manager.issue_letsencrypt_certificate("rancher_demo", "admin@example.com", ["rancher.example.com"], 11, None)
    assert cert["id"] == 99
    assert cert["fallback"] is True
    assert updated_calls == [(11, ["rancher.example.com"], 99, True)]


def test_proxy_manager_provision_https_prefers_letsencrypt_and_falls_back_to_inner():
    from src.services.proxy_manager import ProxyManager

    pm = ProxyManager.__new__(ProxyManager)
    updated = []
    pm.update_proxy_by_app = lambda proxy_id, domains, certificate_id=None, ssl_forced=None: (
        updated.append((proxy_id, domains, certificate_id, ssl_forced))
        or {"id": proxy_id, "domain_names": domains, "certificate_id": certificate_id, "ssl_forced": ssl_forced}
    )
    pm.ensure_inner_certificate = lambda: {"id": 42, "nice_name": "websoft9-inner"}
    pm.request_letsencrypt_certificate = lambda email, domains, proxy_id=None, ssl_forced=None: {"id": 77, "nice_name": domains[0]}

    res1 = pm.provision_https_for_proxy_host(5, ["app.example.com"], email="ops@example.com")
    assert res1["certificate_id"] == 77
    assert res1["ssl_forced"] is True

    def fail_le(email, domains, proxy_id=None, ssl_forced=None):
        raise RuntimeError("ACME challenge failed")

    pm.request_letsencrypt_certificate = fail_le
    res2 = pm.provision_https_for_proxy_host(6, ["intranet.local"], email="ops@example.com")
    assert res2["certificate_id"] == 42
    assert res2["ssl_forced"] is True


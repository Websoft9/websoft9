import sys
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services import app_access_manager as app_access_manager_module
from src.services.app_access_manager import AppAccessManager


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

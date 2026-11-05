"""Validator coverage for the request schemas that guard install / access / runtime endpoints.

Each schema carries hand-written `@field_validator`s (pydantic v2), and those rules are the first line
of defence for the API: they decide which requests reach Portainer, Gitea and the proxy. The cases
below pin the accept/reject boundary for every validator rather than only the happy path.
"""

import pytest

from src.core.exception import CustomException
from src.schemas.appAccess import (
    AppAccessCertificateRequest,
    AppAccessCustomCertificateRequest,
    AppAccessDomainBindingRequest,
    AppAccessProfileUpdateRequest,
    AppAccessRootUrlRequest,
)
from src.schemas.appInstall import Edition, appInstall
from src.schemas.appRuntimeInstall import RuntimeInstallRequest
from src.schemas.domainNames import DomainNames
from src.schemas.proxyHosts import ProxyHost


def _install_payload(**overrides):
    payload = {
        "app_name": "wordpress",
        "edition": {"dist": "community", "version": "6.5.0"},
        "app_id": "wordpress",
        "proxy_enabled": True,
        "domain_names": ["wordpress.example.com"],
    }
    payload.update(overrides)
    return payload


# ── domain_names: shared by DomainNames, ProxyHost and appInstall ────────────


@pytest.mark.parametrize("value", ["", "   "])
def test_domain_names_rejects_blank_entries(value):
    with pytest.raises(CustomException) as error:
        DomainNames(domain_names=[value])
    assert error.value.status_code == 400
    assert "cannot be empty string" in error.value.details


@pytest.mark.parametrize("value", ["http://example.com", "https://example.com"])
def test_domain_names_rejects_scheme_prefix(value):
    with pytest.raises(CustomException) as error:
        ProxyHost(proxy_id=1, domain_names=[value])
    assert "cannot start with" in error.value.details


def test_domain_names_rejects_empty_list():
    with pytest.raises(CustomException) as error:
        DomainNames(domain_names=[])
    assert error.value.details == "domain_names' cannot be empty."


def test_domain_names_rejects_duplicates():
    with pytest.raises(CustomException) as error:
        DomainNames(domain_names=["a.example.com", "a.example.com"])
    assert "must be unique" in error.value.details


def test_proxy_host_rejects_blank_entry():
    with pytest.raises(CustomException) as error:
        ProxyHost(proxy_id=1, domain_names=["  "])
    assert "cannot be empty string" in error.value.details


def test_proxy_host_rejects_empty_list():
    with pytest.raises(CustomException) as error:
        ProxyHost(proxy_id=1, domain_names=[])
    assert error.value.details == "domain_names' cannot be empty."


def test_proxy_host_rejects_duplicates():
    with pytest.raises(CustomException) as error:
        ProxyHost(proxy_id=1, domain_names=["a.example.com", "a.example.com"])
    assert "must be unique" in error.value.details


def test_proxy_host_accepts_distinct_domains():
    host = ProxyHost(proxy_id=1, domain_names=["a.example.com", "b.example.com"], ssl_forced=True)
    assert host.domain_names == ["a.example.com", "b.example.com"]
    assert host.ssl_forced is True


def test_domain_names_accepts_distinct_hosts():
    assert DomainNames(domain_names=["a.example.com", "192.0.2.10"]).domain_names == [
        "a.example.com",
        "192.0.2.10",
    ]


# ── Edition / appInstall ────────────────────────────────────────────────────


@pytest.mark.parametrize("dist", ["enterprise", "", "COMMUNITY"])
def test_edition_requires_community(dist):
    with pytest.raises(CustomException) as error:
        Edition(dist=dist, version="1.0.0")
    assert "'dist' must be 'community'" in error.value.details


def test_edition_rejects_blank_version():
    with pytest.raises(CustomException) as error:
        Edition(dist="community", version="  ")
    assert "'version' cannot be empty" in error.value.details


def test_install_rejects_blank_app_name():
    with pytest.raises(CustomException) as error:
        appInstall(**_install_payload(app_name="  "))
    assert "'app_name' cannot be empty" in error.value.details


@pytest.mark.parametrize("app_id", ["1wordpress", "Wordpress", "a", "a" * 21, "word_press", "中文id"])
def test_install_rejects_invalid_app_id(app_id):
    with pytest.raises(CustomException) as error:
        appInstall(**_install_payload(app_id=app_id))
    assert error.value.status_code == 400


@pytest.mark.parametrize("app_id", ["ab", "wordpress", "a1b2c3d4e5f6g7h8i9j0"])
def test_install_accepts_valid_app_id(app_id):
    assert appInstall(**_install_payload(app_id=app_id)).app_id == app_id


@pytest.mark.parametrize("profile", ["external-db", "a", "9-profile"])
def test_install_accepts_valid_profile(profile):
    assert appInstall(**_install_payload(profile=profile)).profile == profile


@pytest.mark.parametrize("profile", ["External-DB", "-leading", "with space", "中文"])
def test_install_rejects_invalid_profile(profile):
    with pytest.raises(CustomException) as error:
        appInstall(**_install_payload(profile=profile))
    assert "Invalid installation profile" in error.value.details


def test_install_allows_missing_profile():
    assert appInstall(**_install_payload()).profile is None


def test_install_rejects_multiple_domains_when_proxy_disabled():
    with pytest.raises(CustomException) as error:
        appInstall(
            **_install_payload(
                proxy_enabled=False,
                domain_names=["192.0.2.10", "192.0.2.11"],
            )
        )
    assert "only provide one IP address" in error.value.details


def test_install_rejects_duplicate_domains():
    with pytest.raises(CustomException) as error:
        appInstall(**_install_payload(domain_names=["a.example.com", "a.example.com"]))
    assert "must be unique" in error.value.details


def test_install_rejects_blank_domain_entry():
    with pytest.raises(CustomException) as error:
        appInstall(**_install_payload(domain_names=["  "]))
    assert "cannot be empty string" in error.value.details


def test_install_accepts_single_domain_when_proxy_disabled():
    payload = appInstall(**_install_payload(proxy_enabled=False, domain_names=["192.0.2.10"]))
    assert payload.domain_names == ["192.0.2.10"]


# ── App access requests ─────────────────────────────────────────────────────


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_access_profile_update_rejects_out_of_range_port(port):
    with pytest.raises(CustomException) as error:
        AppAccessProfileUpdateRequest(forward_port=port)
    assert "between 1 and 65535" in error.value.details


@pytest.mark.parametrize("port", [1, 8080, 65535, None])
def test_access_profile_update_accepts_valid_port(port):
    assert AppAccessProfileUpdateRequest(forward_port=port).forward_port == port


def test_domain_binding_normalises_and_deduplicates():
    request = AppAccessDomainBindingRequest(domain_names=["  a.example.com  ", "b.example.com"])
    assert request.domain_names == ["a.example.com", "b.example.com"]


def test_domain_binding_rejects_duplicates_after_normalisation():
    with pytest.raises(CustomException) as error:
        AppAccessDomainBindingRequest(domain_names=["a.example.com", " a.example.com "])
    assert "must be unique" in error.value.details


def test_domain_binding_rejects_only_blank_entries():
    with pytest.raises(CustomException) as error:
        AppAccessDomainBindingRequest(domain_names=["   "])
    assert error.value.details == "domain_names cannot be empty"


def test_root_url_request_strips_whitespace():
    assert AppAccessRootUrlRequest(domain_name="  app.example.com ").domain_name == "app.example.com"


def test_root_url_request_rejects_blank():
    with pytest.raises(CustomException) as error:
        AppAccessRootUrlRequest(domain_name="   ")
    assert "domain_name cannot be empty" in error.value.details


@pytest.mark.parametrize("email", ["not-an-email", "", "   "])
def test_certificate_request_rejects_email_without_at(email):
    with pytest.raises(CustomException) as error:
        AppAccessCertificateRequest(email=email, domain_names=["app.example.com"])
    assert "email is invalid" in error.value.details


@pytest.mark.parametrize("email", ["admin@", "@example.com", "@"])
def test_certificate_request_current_contract_only_requires_an_at_sign(email):
    # 现状：校验只检查 "@" 是否存在，`admin@` 这类形式会被放行，直到 Let's Encrypt 注册时才失败。
    # 这里把当前契约固定下来；如果要收紧（本地部分非空 + 域名含点），应作为独立改动并同步前端提示。
    assert "@" in AppAccessCertificateRequest(email=email, domain_names=["a.example.com"]).email


def test_certificate_request_accepts_valid_email():
    request = AppAccessCertificateRequest(email=" admin@example.com ", domain_names=["app.example.com"])
    assert request.email == "admin@example.com"


def test_certificate_request_normalises_domains():
    request = AppAccessCertificateRequest(email="admin@example.com", domain_names=["  app.example.com  ", "www.example.com"])
    assert request.domain_names == ["app.example.com", "www.example.com"]


def test_custom_certificate_rejects_blank_nice_name():
    with pytest.raises(CustomException) as error:
        AppAccessCustomCertificateRequest(nice_name="  ", certificate_pem="x", key_pem="y")
    assert "nice_name cannot be empty" in error.value.details


def test_custom_certificate_rejects_pem_without_certificate_block():
    with pytest.raises(CustomException) as error:
        AppAccessCustomCertificateRequest(
            nice_name="my-cert",
            certificate_pem="not a certificate",
            key_pem="-----BEGIN PRIVATE KEY-----",
        )
    assert "PEM-encoded certificate" in error.value.details


def test_custom_certificate_rejects_key_without_private_key_block():
    with pytest.raises(CustomException) as error:
        AppAccessCustomCertificateRequest(
            nice_name="my-cert",
            certificate_pem="-----BEGIN CERTIFICATE-----",
            key_pem="nothing useful",
        )
    assert "PEM-encoded private key" in error.value.details


def test_custom_certificate_accepts_valid_material_and_strips():
    request = AppAccessCustomCertificateRequest(
        nice_name="  my-cert  ",
        certificate_pem="  -----BEGIN CERTIFICATE-----\nMIIB\n  ",
        key_pem="  -----BEGIN PRIVATE KEY-----\nMIIB\n  ",
    )
    assert request.nice_name == "my-cert"
    assert request.certificate_pem.startswith("-----BEGIN CERTIFICATE-----")
    assert request.key_pem.startswith("-----BEGIN PRIVATE KEY-----")


# ── Runtime install ────────────────────────────────────────────────────────


def _runtime_payload(**overrides):
    payload = {
        "runtime_key": "php",
        "app_id": "phpsite",
        "version": "8.3-apache",
        "host_port": 9011,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("runtime_key", ["ruby", "", "PHP"])
def test_runtime_rejects_unknown_key(runtime_key):
    with pytest.raises(CustomException) as error:
        RuntimeInstallRequest(**_runtime_payload(runtime_key=runtime_key))
    assert "Unsupported runtime" in error.value.details


@pytest.mark.parametrize("app_id", ["1site", "Site", "s", "s" * 21])
def test_runtime_rejects_invalid_app_id(app_id):
    with pytest.raises(CustomException) as error:
        RuntimeInstallRequest(**_runtime_payload(app_id=app_id))
    assert error.value.status_code == 400


def test_runtime_rejects_blank_version():
    with pytest.raises(CustomException) as error:
        RuntimeInstallRequest(**_runtime_payload(version="   "))
    assert "'version' cannot be empty" in error.value.details


def test_runtime_rejects_template_from_another_runtime():
    with pytest.raises(CustomException) as error:
        RuntimeInstallRequest(**_runtime_payload(runtime_key="php", template_app_name="tomcat"))
    assert "Unsupported template 'tomcat' for runtime 'php'" in error.value.details


def test_runtime_accepts_template_of_same_runtime():
    request = RuntimeInstallRequest(**_runtime_payload(runtime_key="php", template_app_name="phpfpmnginx"))
    assert request.template_app_name == "phpfpmnginx"


def test_runtime_requires_app_port_for_nodejs():
    # `validate_default=True` keeps the check running even though `app_port` has a default.
    with pytest.raises(CustomException) as error:
        RuntimeInstallRequest(**_runtime_payload(runtime_key="nodejs", version="22"))
    assert "requires an internal application port" in error.value.details


def test_runtime_accepts_nodejs_with_app_port():
    request = RuntimeInstallRequest(**_runtime_payload(runtime_key="nodejs", version="22", app_port=3000))
    assert request.app_port == 3000


def test_runtime_php_does_not_require_app_port():
    assert RuntimeInstallRequest(**_runtime_payload()).app_port is None

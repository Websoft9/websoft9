"""`SettingsManager`: the single writer of `config.ini` and the platform certificate files.

Almost everything here is operator-facing state that is hard to recover from: the gateway domain,
whether HTTPS is enforced, the certificate paths and the branding. The tests therefore focus on the
rules that stop an edit from producing an unusable platform (force-HTTPS without HTTPS, a certificate
without its key, an unknown section silently created) plus the two certificate flows, which shell out
to `openssl` / `certbot`.
"""

import os
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.exception import CustomException
from src.services import settings_manager as settings_module
from src.services.settings_manager import SettingsManager

BASE_CONFIG = """\
[api_key]
key = secret-key

[domain]
wildcard_domain = .example.com

[platform_gateway]
bound_domain = gateway.example.com
https_enabled = false
force_https = false
ssl_cert = /existing/cert
ssl_key = /existing/key

[platform_brand]
title = Acme
"""


@pytest.fixture
def settings(monkeypatch, tmp_path):
    config_path = tmp_path / "config.ini"
    restarts = []
    monkeypatch.setattr(settings_module, "resolve_apphub_config_path", lambda name: str(config_path))
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH", str(tmp_path / "ssl" / "gateway.crt"))
    monkeypatch.setenv("WEBSOFT9_PLATFORM_GATEWAY_KEY_PATH", str(tmp_path / "ssl" / "gateway.key"))
    monkeypatch.setenv("WEBSOFT9_PLATFORM_GATEWAY_DEFAULT_CONF", str(tmp_path / "gateway" / "default.conf"))
    # 真实实现会 fork 一个 supervisorctl 重启;测试里只记录调用
    real_restart = SettingsManager._restart_platform_gateway
    monkeypatch.setattr(SettingsManager, "_restart_platform_gateway", lambda self: restarts.append(True))
    manager = SettingsManager()
    state = SimpleNamespace(
        manager=manager,
        path=config_path,
        restarts=restarts,
        real_restart=real_restart,
        tmp=tmp_path,
        cert=Path(os.environ["WEBSOFT9_PLATFORM_GATEWAY_CERT_PATH"]),
        key=Path(os.environ["WEBSOFT9_PLATFORM_GATEWAY_KEY_PATH"]),
    )
    return state


def _write_config(settings, text):
    settings.path.write_text(textwrap.dedent(text))


def _openssl(monkeypatch, *, returncode=0, stdout="", stderr=""):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(settings_module.subprocess, "run", fake_run)
    return calls


# ── read / write ──────────────────────────────────────────────────────────


def test_read_all_returns_the_typed_settings(settings):
    _write_config(settings, BASE_CONFIG)

    data = settings.manager.read_all()

    assert data.api_key.key == "secret-key"
    assert data.domain.wildcard_domain == ".example.com"
    assert data.platform_gateway.https_enabled == "false"


def test_read_all_wraps_an_invalid_configuration(settings):
    _write_config(settings, "[api_key]\nkey = only-half\n")

    with pytest.raises(CustomException) as error:
        settings.manager.read_all()

    # 缺少 domain 段 → pydantic 校验失败,对外是 500
    assert error.value.status_code == 500


def test_write_all_persists_every_section(settings):
    from src.schemas.appSettings import (
        ApiKeySetting,
        AppSettings,
        Domain,
        PlatformGatewaySetting,
        ProductAuthSetting,
    )

    _write_config(settings, BASE_CONFIG)
    data = AppSettings(
        api_key=ApiKeySetting(key="rotated"),
        domain=Domain(wildcard_domain=".new.example.com"),
        platform_gateway=PlatformGatewaySetting(https_enabled="true", ssl_cert="/c", ssl_key="/k"),
        product_auth=ProductAuthSetting(enabled="false", protected_modules=""),
    )

    settings.manager.write_all(data)

    assert settings.manager.read_key("api_key", "key") == "rotated"
    assert settings.manager.read_key("domain", "wildcard_domain") == ".new.example.com"
    assert settings.manager.read_key("platform_gateway", "ssl_cert") == "/c"
    assert settings.manager.read_key("product_auth", "enabled") == "false"


def test_write_all_skips_sections_that_were_not_supplied(settings):
    from src.schemas.appSettings import ApiKeySetting, AppSettings, Domain

    _write_config(settings, BASE_CONFIG)
    # platform_gateway / product_auth 是 Optional,这里故意都不传
    data = AppSettings(api_key=ApiKeySetting(key="rotated"), domain=Domain(wildcard_domain=".x"))

    settings.manager.write_all(data)

    assert settings.manager.read_key("api_key", "key") == "rotated"
    assert settings.manager.read_key("domain", "wildcard_domain") == ".x"
    # 未提供的段保持原样,不会被写成空段或丢掉
    assert settings.manager.read_key("platform_gateway", "bound_domain") == "gateway.example.com"


def test_write_all_keeps_existing_values_for_null_fields(settings):
    from src.schemas.appSettings import ApiKeySetting, AppSettings, Domain, PlatformGatewaySetting, ProductAuthSetting

    _write_config(settings, BASE_CONFIG)
    # Domain.wildcard_domain 是 Optional[str],None 表示"没给值",不能把已有配置抹掉
    data = AppSettings(
        api_key=ApiKeySetting(key="rotated"),
        domain=Domain(),
        platform_gateway=PlatformGatewaySetting(https_enabled="true", ssl_cert="/c", ssl_key="/k"),
        product_auth=ProductAuthSetting(enabled="false", protected_modules=""),
    )

    settings.manager.write_all(data)

    assert settings.manager.read_key("domain", "wildcard_domain") == ".example.com"
    assert settings.manager.read_key("platform_gateway", "ssl_cert") == "/c"


def test_read_section_returns_the_section(settings):
    _write_config(settings, BASE_CONFIG)

    assert settings.manager.read_section("domain") == {"wildcard_domain": ".example.com"}


def test_read_section_rejects_an_unknown_section(settings):
    _write_config(settings, BASE_CONFIG)

    with pytest.raises(CustomException) as error:
        settings.manager.read_section("nope")

    assert error.value.status_code == 400
    assert error.value.details == "Section:nope does not exist"


def test_read_section_of_the_brand_always_answers_with_defaults(settings):
    _write_config(settings, BASE_CONFIG)

    brand = settings.manager.read_section("platform_brand")

    assert set(brand) == {
        "title",
        "browser_title",
        "logo_url",
        "favicon_url",
        "apple_touch_icon_url",
        "login_background",
        "copyright_text",
    }
    assert brand["title"] == "Acme"
    assert brand["logo_url"] == settings_module.DEFAULT_PLATFORM_BRAND_LOGO_URL


def test_read_key_requires_section_and_key(settings):
    _write_config(settings, BASE_CONFIG)

    assert settings.manager.read_key("api_key", "key") == "secret-key"
    with pytest.raises(CustomException) as missing_section:
        settings.manager.read_key("nope", "key")
    assert missing_section.value.details == "Section:nope does not exist"
    with pytest.raises(CustomException) as missing_key:
        settings.manager.read_key("api_key", "nope")
    assert missing_key.value.details == "Key:nope does not exist"


def test_write_section_updates_and_returns_the_section(settings):
    _write_config(settings, BASE_CONFIG)

    result = settings.manager.write_section("domain", "wildcard_domain", ".other.example.com")

    assert result == {"wildcard_domain": ".other.example.com"}
    assert "wildcard_domain = .other.example.com" in settings.path.read_text()


def test_write_section_never_creates_unknown_sections_or_keys(settings):
    _write_config(settings, BASE_CONFIG)

    with pytest.raises(CustomException) as unknown_section:
        settings.manager.write_section("nope", "key", "value")
    assert unknown_section.value.details == "Section:nope does not exist"

    with pytest.raises(CustomException) as unknown_key:
        settings.manager.write_section("api_key", "nope", "value")
    assert unknown_key.value.details == "Key:nope does not exist"


# ── summary ───────────────────────────────────────────────────────────────


def test_read_summary_exposes_the_editable_settings(settings, monkeypatch):
    _write_config(settings, BASE_CONFIG)
    monkeypatch.setattr(settings_module, "read_product_metadata", lambda readonly=False: {"version": "2.1.0"})
    monkeypatch.setattr(
        settings_module,
        "read_product_edition",
        lambda readonly=False: SimpleNamespace(key="community", name="Community", names={}),
    )

    summary = settings.manager.read_summary()

    groups = {group["id"]: group for group in summary["groups"]}
    assert list(groups) == ["network", "application", "version", "branding"]
    network = {item["key"]: item for item in groups["network"]["items"]}
    assert network["bound_domain"]["value"] == "gateway.example.com"
    assert network["https_enabled"]["value"] == "false"
    assert network["https_enabled"]["metadata"]["default_certificate"] == "true"
    assert groups["version"]["items"][0]["value"] == "Community 2.1.0"
    # 端口范围为空时回落到默认值,前端不必自己兜底
    assert groups["application"]["items"][0]["value"] == settings_module.DEFAULT_PORT_RANGE_VALUE


def test_summary_items_describe_editable_masked_and_sensitive(settings):
    item = settings.manager._build_item("section", "key", "value", sensitive=True, editable=False, metadata={"a": "b"})
    masked = settings.manager._build_item("section", "key", "abcdefghij", masked=True)

    assert item == {
        "group": "section",
        "key": "key",
        "value": "value",
        "sensitive": True,
        "masked": False,
        "editable": False,
        "metadata": {"a": "b"},
    }
    assert masked["value"] == "ab******ij"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", "Not configured"),
        ("abc", "***"),
        ("abcdef", "******"),
        ("abcdefghij", "ab******ij"),
    ],
)
def test_secrets_are_masked_without_leaking_the_middle(value, expected):
    assert SettingsManager()._mask_value(value) == expected


# ── booleans and defaults ─────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on", " on "])
def test_truthy_values(settings, value):
    assert settings.manager._parse_bool(value) is True


@pytest.mark.parametrize("value", ["false", "0", "no", "off"])
def test_falsy_values(settings, value):
    assert settings.manager._parse_bool(value) is False


@pytest.mark.parametrize("value", ["", "maybe", "2"])
def test_anything_else_is_rejected(settings, value):
    with pytest.raises(CustomException) as error:
        settings.manager._parse_bool(value)

    assert error.value.status_code == 400
    assert error.value.details == "https_enabled must be a boolean value"


def test_booleans_are_written_lowercase(settings):
    assert settings.manager._bool_to_string(True) == "true"
    assert settings.manager._bool_to_string(False) == "false"


def test_certificate_paths_come_from_the_environment(settings):
    assert settings.manager._default_ssl_cert_path() == str(settings.cert)
    assert settings.manager._default_ssl_key_path() == str(settings.key)


# ── platform gateway toggles ──────────────────────────────────────────────


def test_enabling_https_writes_the_default_certificate_paths(settings):
    _write_config(settings, BASE_CONFIG)

    section = settings.manager.write_section("platform_gateway", "https_enabled", "true")

    assert section["https_enabled"] == "true"
    assert section["ssl_cert"] == str(settings.cert)
    assert section["ssl_key"] == str(settings.key)
    assert settings.restarts == [True]


def test_disabling_https_also_disables_force_https(settings):
    _write_config(settings, BASE_CONFIG.replace("force_https = false", "force_https = true"))

    section = settings.manager.write_section("platform_gateway", "https_enabled", "false")

    assert section["force_https"] == "false"


def test_force_https_requires_https(settings):
    _write_config(settings, BASE_CONFIG)

    with pytest.raises(CustomException) as error:
        settings.manager.write_section("platform_gateway", "force_https", "true")

    assert error.value.status_code == 400
    assert error.value.details == "Platform HTTPS must be enabled before force HTTPS can be enabled"


def test_bound_domain_is_trimmed(settings):
    _write_config(settings, BASE_CONFIG)

    section = settings.manager.write_section("platform_gateway", "bound_domain", "  app.example.com  ")

    assert section["bound_domain"] == "app.example.com"
    assert settings.restarts == [True]


def test_batch_update_rejects_force_https_without_https(settings):
    _write_config(settings, BASE_CONFIG)

    with pytest.raises(CustomException) as error:
        settings.manager.write_platform_gateway_settings(
            bound_domain="app.example.com", https_enabled="false", force_https="true"
        )

    assert "must be enabled before force HTTPS" in error.value.details


def test_batch_update_requires_certificate_and_key_together(settings):
    _write_config(settings, BASE_CONFIG)

    with pytest.raises(CustomException) as error:
        settings.manager.write_platform_gateway_settings(
            bound_domain="app.example.com", https_enabled="true", force_https="false", ssl_cert="/only/cert"
        )

    assert error.value.details == "Platform certificate and key paths must be provided together"


def test_batch_update_keeps_the_existing_certificate_when_none_is_sent(settings):
    _write_config(settings, BASE_CONFIG)

    section = settings.manager.write_platform_gateway_settings(
        bound_domain="app.example.com", https_enabled="true", force_https="true"
    )

    assert section["ssl_cert"] == "/existing/cert"
    assert section["ssl_key"] == "/existing/key"
    assert section["force_https"] == "true"
    assert section["https_enabled"] == "true"


def test_batch_update_accepts_an_explicit_certificate(settings):
    _write_config(settings, BASE_CONFIG)

    section = settings.manager.write_platform_gateway_settings(
        bound_domain="app.example.com",
        https_enabled="true",
        force_https="false",
        ssl_cert="/custom/cert",
        ssl_key="/custom/key",
        restart_gateway=False,
    )

    assert (section["ssl_cert"], section["ssl_key"]) == ("/custom/cert", "/custom/key")
    # restart_gateway=False 由调用方自己重启(例如连着做多步修改)
    assert settings.restarts == []


def test_batch_update_disabling_https_clears_force_https(settings):
    _write_config(settings, BASE_CONFIG.replace("https_enabled = false", "https_enabled = true"))

    section = settings.manager.write_platform_gateway_settings(bound_domain="", https_enabled="off", force_https="false")

    assert section["https_enabled"] == "false"
    assert section["force_https"] == "false"


def test_https_state_falls_back_to_the_gateway_configuration(settings):
    _write_config(settings, BASE_CONFIG.replace("https_enabled = false\n", ""))
    settings.manager.config.read(settings.path)
    gateway_conf = settings.tmp / "gateway" / "default.conf"

    assert settings.manager._is_platform_https_enabled() is False

    gateway_conf.parent.mkdir(parents=True, exist_ok=True)
    gateway_conf.write_text("server { listen 9000 default_server ssl; }\n")
    assert settings.manager._is_platform_https_enabled() is True

    gateway_conf.write_text("server { listen 9000 default_server; }\n")
    assert settings.manager._is_platform_https_enabled() is False


def test_explicit_https_state_wins_over_the_gateway_configuration(settings):
    _write_config(settings, BASE_CONFIG)
    # 这两个方法读的是 self.config;生产路径(read_summary / write_section)都会先 read
    settings.manager.config.read(settings.path)
    gateway_conf = settings.tmp / "gateway" / "default.conf"
    gateway_conf.parent.mkdir(parents=True, exist_ok=True)
    gateway_conf.write_text("listen 9000 default_server ssl\n")

    assert settings.manager._is_platform_https_enabled() is False


def test_force_https_reading(settings):
    _write_config(settings, BASE_CONFIG.replace("force_https = false", "force_https = ON"))
    settings.manager.config.read(settings.path)

    assert settings.manager._is_force_https_enabled() is True


# ── certificate inspection ────────────────────────────────────────────────


def test_certificate_expiry_is_formatted(settings, monkeypatch):
    settings.cert.parent.mkdir(parents=True, exist_ok=True)
    settings.cert.write_text("cert")
    calls = _openssl(monkeypatch, stdout="notAfter=Jun  4 10:00:00 2026 GMT\n")

    assert settings.manager._read_cert_expiry() == "2026-06-04 10:00"
    assert calls[0][:2] == ["openssl", "x509"]


def test_certificate_expiry_is_blank_without_a_certificate(settings, monkeypatch):
    _openssl(monkeypatch, stdout="notAfter=Jun  4 10:00:00 2026 GMT\n")

    assert settings.manager._read_cert_expiry() == ""


def test_certificate_expiry_is_blank_when_openssl_fails(settings, monkeypatch):
    settings.cert.parent.mkdir(parents=True, exist_ok=True)
    settings.cert.write_text("cert")
    _openssl(monkeypatch, returncode=1, stderr="bad file")

    assert settings.manager._read_cert_expiry() == ""


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("subject=CN=app.example.com\n", "app.example.com"),
        ("subject=CN=app.example.com, O=Acme, C=US\n", "app.example.com"),
        ("CN=app.example.com\n", "app.example.com"),
        ("subject=O=Acme\n", ""),
    ],
)
def test_subject_cn_is_extracted(settings, monkeypatch, stdout, expected):
    settings.cert.parent.mkdir(parents=True, exist_ok=True)
    settings.cert.write_text("cert")
    _openssl(monkeypatch, stdout=stdout)

    assert settings.manager._read_cert_subject_cn() == expected


def test_a_certificate_from_an_issuer_is_not_the_default_one(settings, monkeypatch):
    settings.cert.parent.mkdir(parents=True, exist_ok=True)
    settings.cert.write_text("cert")

    _openssl(monkeypatch, stdout="subject=CN=app.example.com\nissuer=C=US, O=Let's Encrypt\n")

    assert settings.manager._is_default_platform_certificate() is False


def test_a_self_signed_certificate_is_detected(settings, monkeypatch):
    settings.cert.parent.mkdir(parents=True, exist_ok=True)
    settings.cert.write_text("cert")

    # openssl 输出的是 "subject=..." / "issuer=...",判定必须比较 DN 本身而不是整行
    _openssl(monkeypatch, stdout="subject=CN=Websoft9\nissuer=CN=Websoft9\n")

    assert settings.manager._is_default_platform_certificate() is True


def test_a_wrapped_self_signed_subject_is_still_detected(settings, monkeypatch):
    settings.cert.parent.mkdir(parents=True, exist_ok=True)
    settings.cert.write_text("cert")

    _openssl(
        monkeypatch,
        stdout="subject=CN=Websoft9\nsubject=O=Websoft9\nissuer=CN=Websoft9\nissuer=O=Websoft9\n",
    )

    assert settings.manager._is_default_platform_certificate() is True


def test_a_missing_certificate_counts_as_the_default_one(settings, monkeypatch):
    _openssl(monkeypatch)

    assert settings.manager._is_default_platform_certificate() is True


# ── certificate provisioning ──────────────────────────────────────────────


def test_self_signed_generation_writes_the_certificate_and_config(settings, monkeypatch):
    _write_config(settings, BASE_CONFIG)
    calls = _openssl(monkeypatch)

    result = settings.manager.generate_self_signed_cert(domain="app.example.com", validity_days=30)

    assert result == {"ssl_cert": str(settings.cert), "ssl_key": str(settings.key)}
    command = calls[0]
    assert command[:2] == ["openssl", "req"]
    assert "/CN=app.example.com" in command
    assert "30" in command
    assert settings.manager.read_key("platform_gateway", "ssl_cert") == str(settings.cert)
    assert settings.restarts == [True]


def test_self_signed_generation_defaults_the_common_name(settings, monkeypatch):
    _write_config(settings, BASE_CONFIG)
    calls = _openssl(monkeypatch)

    settings.manager.generate_self_signed_cert()

    assert "/CN=Websoft9" in calls[0]


def test_a_failed_openssl_run_is_reported(settings, monkeypatch):
    _write_config(settings, BASE_CONFIG)
    _openssl(monkeypatch, returncode=1, stderr="cannot write private key")

    with pytest.raises(CustomException) as error:
        settings.manager.generate_self_signed_cert()

    assert error.value.status_code == 500
    assert error.value.details == "cannot write private key"


def test_letsencrypt_requires_a_domain_and_an_email(settings):
    with pytest.raises(CustomException) as no_domain:
        settings.manager.apply_letsencrypt_cert("  ")
    assert no_domain.value.details == "Domain is required for Let's Encrypt certificate"

    with pytest.raises(CustomException) as no_email:
        settings.manager.apply_letsencrypt_cert("app.example.com", " ")
    assert no_email.value.details == "Contact email is required for Let's Encrypt certificate"


def test_letsencrypt_reports_certbot_failures(settings, monkeypatch):
    _write_config(settings, BASE_CONFIG)
    _openssl(monkeypatch, returncode=1, stderr="DNS problem")

    with pytest.raises(CustomException) as error:
        settings.manager.apply_letsencrypt_cert("app.example.com", "ops@example.com")

    assert error.value.status_code == 500
    assert error.value.message == "Let's Encrypt Certificate Failed"
    assert error.value.details == "DNS problem"


def test_letsencrypt_requires_the_issued_files(settings, monkeypatch):
    _write_config(settings, BASE_CONFIG)
    _openssl(monkeypatch)

    with pytest.raises(CustomException) as error:
        settings.manager.apply_letsencrypt_cert("app.example.com", "ops@example.com")

    assert error.value.details == "Certificate files not found after successful certbot run"


def test_letsencrypt_copies_the_issued_certificate(settings, monkeypatch, tmp_path):
    _write_config(settings, BASE_CONFIG)
    _openssl(monkeypatch)
    live = tmp_path / "live"
    live.mkdir()
    for name in ("fullchain.pem", "privkey.pem"):
        (live / name).write_text(name)
    real_isfile = os.path.isfile
    monkeypatch.setattr(
        settings_module.os.path,
        "isfile",
        lambda value: str(value).startswith("/etc/letsencrypt/live/") or real_isfile(value),
    )
    monkeypatch.setattr(
        settings_module.shutil,
        "copy2",
        lambda source, destination: Path(destination).write_text(Path(source).name),
    )

    result = settings.manager.apply_letsencrypt_cert("app.example.com", "ops@example.com")

    assert result == {"ssl_cert": str(settings.cert), "ssl_key": str(settings.key)}
    assert settings.cert.read_text() == "fullchain.pem"
    assert settings.key.read_text() == "privkey.pem"
    assert settings.restarts == [True]


def test_certbot_runs_without_the_bundled_python_path(settings, monkeypatch):
    _write_config(settings, BASE_CONFIG)
    monkeypatch.setenv("PYTHONPATH", "/opt/websoft9-pydeps")
    captured = {}

    def fake_run(command, **kwargs):
        captured["env"] = kwargs.get("env")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(settings_module.subprocess, "run", fake_run)
    monkeypatch.setattr(settings_module.os.path, "isfile", lambda value: False)

    with pytest.raises(CustomException):
        settings.manager.apply_letsencrypt_cert("app.example.com", "ops@example.com")

    # certbot 必须用系统 Python 的依赖,PYTHONPATH 不能带过去
    assert "PYTHONPATH" not in captured["env"]


def test_uploaded_certificates_are_written_and_recorded(settings):
    _write_config(settings, BASE_CONFIG)

    result = settings.manager.upload_cert("CERT", "KEY")

    assert result == {"ssl_cert": str(settings.cert), "ssl_key": str(settings.key)}
    assert settings.cert.read_text() == "CERT\n"
    assert settings.key.read_text() == "KEY\n"
    assert settings.manager.read_key("platform_gateway", "ssl_cert") == str(settings.cert)


def test_an_intermediate_chain_is_written_next_to_the_certificate(settings):
    _write_config(settings, BASE_CONFIG)

    settings.manager.upload_cert("CERT", "KEY", intermediate_pem="CHAIN")

    assert (settings.cert.parent / (settings.cert.name + ".chain")).read_text() == "CHAIN\n"


def test_upload_requires_both_parts(settings):
    with pytest.raises(CustomException) as error:
        settings.manager.upload_cert("CERT", "   ")

    assert error.value.details == "Certificate and key PEM content are required"


def test_a_gateway_restart_that_cannot_be_scheduled_is_reported(settings, monkeypatch):
    def failing_popen(*args, **kwargs):
        raise OSError("supervisorctl not found")

    monkeypatch.setattr(settings_module.subprocess, "Popen", failing_popen)

    # 这里测的是真实实现:fixture 保存了补丁前的函数
    with pytest.raises(CustomException) as error:
        settings.real_restart(settings.manager)

    assert error.value.status_code == 500
    assert error.value.details == "Failed to apply the platform HTTPS change"


# ── branding ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/websoft9.png", True),
        ("http://cdn.example.com/logo.png", True),
        ("https://cdn.example.com/logo.png", True),
        ("", False),
        ("logo.png", False),
        ("ftp://example.com/logo.png", False),
    ],
)
def test_brand_urls_must_be_absolute_or_root_relative(settings, value, expected):
    assert settings.manager._is_valid_brand_logo_url(value) is expected


def test_brand_defaults_are_used_for_empty_values(settings):
    _write_config(settings, "[api_key]\nkey = k\n[domain]\nwildcard_domain = d\n[platform_brand]\n")

    brand = settings.manager.read_section("platform_brand")

    assert brand["title"] == settings_module.DEFAULT_PLATFORM_BRAND_TITLE
    assert brand["logo_url"] == settings_module.DEFAULT_PLATFORM_BRAND_LOGO_URL
    assert brand["favicon_url"] == settings_module.DEFAULT_PLATFORM_BRAND_FAVICON_URL
    assert brand["copyright_text"] == settings_module.DEFAULT_PLATFORM_BRAND_COPYRIGHT_TEXT
    assert brand["browser_title"] == ""


def test_brand_write_normalizes_empty_values_to_defaults(settings):
    _write_config(settings, BASE_CONFIG)

    brand = settings.manager.write_section("platform_brand", "title", "   ")

    assert brand["title"] == settings_module.DEFAULT_PLATFORM_BRAND_TITLE


def test_brand_write_rejects_an_invalid_logo(settings):
    _write_config(settings, BASE_CONFIG)

    with pytest.raises(CustomException) as error:
        settings.manager.write_section("platform_brand", "logo_url", "logo.png")

    assert "must be an absolute http(s) URL or a root-relative path" in error.value.details


def test_brand_write_rejects_an_invalid_login_background(settings):
    _write_config(settings, BASE_CONFIG)

    with pytest.raises(CustomException) as error:
        settings.manager.write_section("platform_brand", "login_background", "bg.png")

    assert "login_background" in error.value.details


def test_an_empty_login_background_is_allowed(settings):
    _write_config(settings, BASE_CONFIG)

    brand = settings.manager.write_section("platform_brand", "login_background", "")

    assert brand["login_background"] == ""


def test_brand_rejects_unknown_keys(settings):
    _write_config(settings, BASE_CONFIG)

    with pytest.raises(CustomException) as error:
        settings.manager.write_section("platform_brand", "nope", "x")

    assert error.value.details == "Key:nope does not exist"


# ── docker mirror compatibility path ──────────────────────────────────────


def test_a_legacy_accelerator_list_is_stored_in_the_registry(settings, monkeypatch):
    _write_config(settings, BASE_CONFIG)
    stored = []

    class FakeRegistry:
        def __init__(self):
            self.store = SimpleNamespace(replace_entries=lambda entries: stored.extend(entry.url for entry in entries))

        def export_host_visible_list(self):
            stored.append("exported")

    monkeypatch.setattr(settings_module, "MirrorRegistry", FakeRegistry)
    monkeypatch.setattr(settings_module, "parse_mirror_entries", lambda value: ["a.example.com", "b.example.com"])
    monkeypatch.setattr(settings_module, "is_mirror_list_url", lambda value: False)

    result = settings.manager.write_section("docker_mirror", "url", "a.example.com\nb.example.com")

    assert stored == ["a.example.com", "b.example.com", "exported"]
    assert result == {"url": "a.example.com\nb.example.com"}
    # 同时写回 config.ini,数据库丢失时还有账可查
    assert "docker_mirror" in settings.path.read_text()


def test_a_list_url_is_not_treated_as_an_accelerator(settings, monkeypatch):
    _write_config(settings, BASE_CONFIG)

    class ExplodingRegistry:
        def __init__(self):
            raise AssertionError("a list URL must not be stored as an accelerator")

    monkeypatch.setattr(settings_module, "MirrorRegistry", ExplodingRegistry)
    monkeypatch.setattr(settings_module, "parse_mirror_entries", lambda value: [])
    monkeypatch.setattr(settings_module, "is_mirror_list_url", lambda value: True)

    assert settings.manager.write_section("docker_mirror", "url", "https://mirrors.example.com/list.json") == {"url": ""}

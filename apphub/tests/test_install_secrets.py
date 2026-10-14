import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.exception import CustomException
from src.services.install_secrets import forget_install_secrets, generate_secret, initialize_install_secrets


def _template(tmp_path, monkeypatch, values, fields=None, name="template"):
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "data"))
    directory = tmp_path / name
    directory.mkdir()
    (directory / ".env").write_text("# retained comment\n" + "\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    (directory / "variables.json").write_text(json.dumps({"env": {"secrets": list(values) if fields is None else fields}}))
    return directory


@pytest.mark.parametrize("template,pattern", [
    ("a1" * 32, r"[0-9a-f]{64}"),
    ("A1" * 16, r"[0-9A-F]{32}"),
    ("sk-" + "a1" * 32, r"sk-[0-9a-f]{64}"),
    ("1234-45687-12312", r"[0-9]{4}-[0-9]{5}-[0-9]{5}"),
    ("AbZ19x" * 6, r"[A-Za-z0-9]{36}"),
    ("abcdef12-abcdef12", r"[0-9a-f]{8}-[0-9a-f]{8}"),
])
def test_generate_preserves_format(template, pattern):
    generated = generate_secret("SECRET", template)
    assert generated != template
    assert re.fullmatch(pattern, generated)


@pytest.mark.parametrize("template", ["tiny", "abc-1234567890123456", "longprefix-1234567890123456", "sk-", "eyJhbGc.eyJzdWI.signature", "123e4567-e89b-12d3-a456-426614174000", "-----BEGIN PRIVATE KEY-----", "YWJjZGVmZ2hpamtsbW5vcA=="])
def test_generate_rejects_unknown_or_short_formats(template):
    with pytest.raises(CustomException) as error:
        generate_secret("SECRET", template)
    assert "SECRET" in error.value.details
    assert template not in error.value.details


def test_initialize_reuses_values_without_changing_template(tmp_path, monkeypatch):
    values = {"KEY": "a1" * 32, "IV": "b2" * 16, "W9_POWER_PASSWORD": "", "ALIAS": "${W9_POWER_PASSWORD}"}
    first = _template(tmp_path, monkeypatch, values)
    second = _template(tmp_path, monkeypatch, values, name="retry")
    third = _template(tmp_path, monkeypatch, values, name="other")
    initialize_install_secrets(first, "app-one", "demo")
    initialize_install_secrets(second, "app-one", "demo")
    initialize_install_secrets(third, "app-two", "demo")
    result = dotenv_values(first / ".env", interpolate=False)
    assert result == dotenv_values(second / ".env", interpolate=False)
    assert result["KEY"] != dotenv_values(third / ".env")["KEY"]
    assert result["ALIAS"] == "${W9_POWER_PASSWORD}"
    assert len(result["W9_POWER_PASSWORD"]) == 16
    assert "# retained comment" in (first / ".env").read_text()
    assert (first / ".env").stat().st_mode & 0o777 == 0o600
    storage = tmp_path / "data/config/apphub/install-secrets"
    assert storage.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in storage.iterdir())


def test_explicit_settings_win_and_survive_retry(tmp_path, monkeypatch):
    directory = _template(tmp_path, monkeypatch, {"KEY": "a1" * 32})
    override = "f9" * 32
    initialize_install_secrets(directory, "app", "demo", {"KEY": override})
    retry = _template(tmp_path, monkeypatch, {"KEY": "a1" * 32}, name="retry")
    initialize_install_secrets(retry, "app", "demo")
    assert dotenv_values(retry / ".env")["KEY"] == override


@pytest.mark.parametrize("values,fields", [
    ({"OTHER": "a1" * 32}, ["MISSING"]),
    ({"KEY": ""}, ["KEY"]),
    ({"KEY": "${MISSING}"}, ["KEY"]),
    ({"KEY": "${OTHER}", "OTHER": "${KEY}"}, ["KEY"]),
    ({"KEY": "${OTHER:-fallback}"}, ["KEY"]),
    ({"KEY": "a1" * 32}, "KEY"),
    ({"KEY": "a1" * 32}, [123]),
])
def test_invalid_declaration_or_reference_leaves_env_unchanged(tmp_path, monkeypatch, values, fields):
    directory = _template(tmp_path, monkeypatch, values, fields)
    original = (directory / ".env").read_bytes()
    with pytest.raises(CustomException):
        initialize_install_secrets(directory, "app", "demo")
    assert (directory / ".env").read_bytes() == original


def test_concurrent_retries_get_same_values(tmp_path, monkeypatch):
    directories = [_template(tmp_path, monkeypatch, {"KEY": "a1" * 32}, name=f"copy-{index}") for index in range(4)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda directory: initialize_install_secrets(directory, "app", "demo"), directories))
    assert len({dotenv_values(directory / ".env")["KEY"] for directory in directories}) == 1


def test_failed_write_is_atomic_and_retry_reuses_saved_value(tmp_path, monkeypatch):
    import src.services.install_secrets as module

    directory = _template(tmp_path, monkeypatch, {"KEY": "a1" * 32, "OTHER": "b2" * 16})
    original = (directory / ".env").read_bytes()
    real_set_key = module.set_key
    calls = []

    def fail_write(path, field, value):
        calls.append(value)
        if field == "OTHER":
            raise OSError(value)
        return real_set_key(path, field, value)

    monkeypatch.setattr(module, "set_key", fail_write)
    with pytest.raises(CustomException) as error:
        initialize_install_secrets(directory, "app", "demo")
    assert (directory / ".env").read_bytes() == original
    assert all(value not in error.value.details for value in calls)
    monkeypatch.setattr(module, "set_key", real_set_key)
    initialize_install_secrets(directory, "app", "demo")
    assert dotenv_values(directory / ".env")["KEY"] == calls[0]


def test_env_helper_resolves_forward_and_partial_references(tmp_path):
    from src.core.envHelper import EnvHelper

    env_path = tmp_path / ".env"
    env_path.write_text("FIRST=prefix-${SECOND}\nSECOND=$THIRD\nTHIRD=resolved\n")
    assert EnvHelper(str(env_path)).get_value("FIRST") == "prefix-resolved"


@pytest.mark.parametrize("content", ["KEY=${OTHER}\nOTHER=${KEY}\n", "KEY=$MISSING\n"])
def test_env_helper_rejects_invalid_references(tmp_path, content):
    from src.core.envHelper import EnvHelper

    env_path = tmp_path / ".env"
    env_path.write_text(content)
    with pytest.raises(CustomException):
        EnvHelper(str(env_path)).get_value("KEY")


def test_env_helper_write_error_does_not_log_value(tmp_path, monkeypatch):
    import src.core.envHelper as module

    env_path = tmp_path / ".env"
    env_path.write_text("KEY=existing\n")
    messages = []
    value = "private-value-not-for-logs"

    def fail_write(*args):
        raise OSError(value)

    monkeypatch.setattr(module, "set_key", fail_write)
    monkeypatch.setattr(module.logger, "error", messages.append)
    with pytest.raises(CustomException) as error:
        module.EnvHelper(str(env_path)).set_value("KEY", value)
    assert messages and all(value not in message for message in messages)
    assert value not in error.value.details


def test_explicit_deletion_starts_a_fresh_installation(tmp_path, monkeypatch):
    directory = _template(tmp_path, monkeypatch, {"KEY": "a1" * 32})
    initialize_install_secrets(directory, "app", "demo")
    previous = dotenv_values(directory / ".env")["KEY"]
    forget_install_secrets("app")
    forget_install_secrets("app")
    fresh = _template(tmp_path, monkeypatch, {"KEY": "a1" * 32}, name="fresh")
    initialize_install_secrets(fresh, "app", "demo")
    assert dotenv_values(fresh / ".env")["KEY"] != previous


def test_duplicate_declarations_do_not_generate_twice(tmp_path, monkeypatch):
    import src.services.install_secrets as module

    directory = _template(tmp_path, monkeypatch, {"KEY": "a1" * 32}, ["KEY", "KEY"])
    generated = []
    original = module.generate_secret

    def record(field, template):
        generated.append(field)
        return original(field, template)

    monkeypatch.setattr(module, "generate_secret", record)
    initialize_install_secrets(directory, "app", "demo")
    assert generated == ["KEY"]


def test_forward_partial_reference_preserves_raw_template(tmp_path, monkeypatch):
    from src.core.envHelper import EnvHelper

    directory = _template(tmp_path, monkeypatch, {"ALIAS": "prefix-${KEY}", "KEY": "a1" * 32})
    initialize_install_secrets(directory, "app", "demo")
    assert dotenv_values(directory / ".env", interpolate=False)["ALIAS"] == "prefix-${KEY}"
    helper = EnvHelper(str(directory / ".env"))
    assert helper.get_value("ALIAS") == "prefix-" + helper.get_value("KEY")


@pytest.mark.parametrize("override", ["wrong-format-value", "f9" * 32 + "\nINJECTED=yes", ""])
def test_invalid_override_does_not_write_values(tmp_path, monkeypatch, override):
    directory = _template(tmp_path, monkeypatch, {"KEY": "a1" * 32})
    original = (directory / ".env").read_bytes()
    with pytest.raises(CustomException) as error:
        initialize_install_secrets(directory, "app", "demo", {"KEY": override})
    assert (directory / ".env").read_bytes() == original
    if override:
        assert override not in error.value.details


def test_platform_password_is_initialized_without_secret_declaration(tmp_path, monkeypatch):
    directory = _template(tmp_path, monkeypatch, {"W9_POWER_PASSWORD": "", "W9_RCODE": ""}, [])
    (directory / "variables.json").unlink()
    initialize_install_secrets(directory, "app", "demo")
    values = dotenv_values(directory / ".env")
    assert len(values["W9_POWER_PASSWORD"]) == 16
    assert len(values["W9_RCODE"]) == 13


def test_changed_template_reference_does_not_use_stale_literal(tmp_path, monkeypatch):
    directory = _template(tmp_path, monkeypatch, {"KEY": "a1" * 32})
    initialize_install_secrets(directory, "app", "demo")
    retry = _template(tmp_path, monkeypatch, {"KEY": "${W9_POWER_PASSWORD}", "W9_POWER_PASSWORD": ""}, name="retry")
    initialize_install_secrets(retry, "app", "demo")
    assert dotenv_values(retry / ".env", interpolate=False)["KEY"] == "${W9_POWER_PASSWORD}"
    later_retry = _template(tmp_path, monkeypatch, {"KEY": "${W9_POWER_PASSWORD}", "W9_POWER_PASSWORD": ""}, name="later-retry")
    initialize_install_secrets(later_retry, "app", "demo")
    assert dotenv_values(later_retry / ".env", interpolate=False)["KEY"] == "${W9_POWER_PASSWORD}"


def test_explicit_reference_override_survives_retry(tmp_path, monkeypatch):
    values = {"KEY": "${W9_POWER_PASSWORD}", "W9_POWER_PASSWORD": ""}
    directory = _template(tmp_path, monkeypatch, values)
    override = "chosen-password-value"
    initialize_install_secrets(directory, "app", "demo", {"KEY": override})
    retry = _template(tmp_path, monkeypatch, values, name="retry")
    initialize_install_secrets(retry, "app", "demo")
    assert dotenv_values(retry / ".env", interpolate=False)["KEY"] == override


@pytest.mark.parametrize("extra,ambient,expected", [
    ("", None, "fallback"),
    ("OTHER=\n", None, ""),
    ("OTHER=defined\n", None, "defined"),
    ("", "ambient", "ambient"),
])
def test_env_helper_preserves_non_secret_default_expressions(tmp_path, monkeypatch, extra, ambient, expected):
    from src.core.envHelper import EnvHelper

    monkeypatch.delenv("OTHER", raising=False)
    if ambient is not None:
        monkeypatch.setenv("OTHER", ambient)
    env_path = tmp_path / ".env"
    env_path.write_text("KEY=${OTHER:-fallback}\n" + extra)
    assert EnvHelper(str(env_path)).get_value("KEY") == expected
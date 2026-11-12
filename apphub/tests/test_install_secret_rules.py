"""Rule-based ``env.secrets`` declarations (``base64`` / ``fernet`` / ``jwt``).

The library publishes ``metadata/secret-rules.json`` and declares keys as single-key objects. The
platform must implement the published profiles, reject unknown ones, and never fall back to a
built-in copy when the dictionary is unavailable.
"""

import base64
import hashlib
import hmac
import json
import re
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.exception import CustomException
from src.services.install_secrets import initialize_install_secrets
from src.services.secret_rules import (
    generate_rule_secret,
    load_secret_rules,
    matches_rule,
    parse_secret_rule,
    validate_secret_rules,
)

RULES = {
    "base64": {
        "generator": "random_bytes",
        "encoding": "base64",
        "description": "Generate random bytes of the same decoded length and encode as Base64.",
    },
    "fernet": {
        "generator": "random_bytes",
        "encoding": "base64url",
        "bytes": 32,
        "description": "Generate 32 random bytes and encode as URL-safe Base64.",
    },
    "jwt": {
        "generator": "jwt",
        "algorithm": "HS256",
        "description": "Update iat/exp on the default JWT payload and sign with the referenced secret.",
    },
}

# 32 raw bytes -> 44 character standard Base64 default value.
BASE64_TEMPLATE = base64.b64encode(b"\x01" * 32).decode()
JWT_TEMPLATE_PAYLOAD = {"iss": "supabase", "role": "anon", "iat": 1700000000, "exp": 2015360000}
JWT_TEMPLATE = ".".join(
    [
        base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("="),
        base64.urlsafe_b64encode(json.dumps(JWT_TEMPLATE_PAYLOAD).encode()).decode().rstrip("="),
        "template-signature",
    ]
)


def _rules_file(tmp_path: Path, rules: dict | None = None) -> Path:
    path = tmp_path / "secret-rules.json"
    path.write_text(json.dumps(rules or RULES), encoding="utf-8")
    return path


def _instance(tmp_path, monkeypatch, values, declarations, rules: dict | None = None) -> Path:
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("WEBSOFT9_SECRET_RULES_PATH", str(_rules_file(tmp_path, rules)))
    directory = tmp_path / "instance"
    directory.mkdir(exist_ok=True)
    (directory / ".env").write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    (directory / "variables.json").write_text(json.dumps({"env": {"secrets": declarations}}), encoding="utf-8")
    return directory


def _decoded(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), validate=True)


# ── dictionary validation ───────────────────────────────────────────


def test_the_published_dictionary_is_accepted():
    assert validate_secret_rules(RULES) == {
        "base64": {"generator": "random_bytes", "encoding": "base64", "bytes": None},
        "fernet": {"generator": "random_bytes", "encoding": "base64url", "bytes": 32},
        "jwt": {"generator": "jwt", "algorithm": "HS256"},
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rules: rules.pop("jwt"),
        lambda rules: rules["base64"].update(encoding="base64url"),
        lambda rules: rules["fernet"].update(bytes=16),
        lambda rules: rules["jwt"].update(algorithm="RS256"),
        lambda rules: rules["base64"].update(generator="uuid4"),
        lambda rules: rules["base64"].update(extra=True),
        lambda rules: rules["base64"].update(description=""),
        lambda rules: rules.update({"custom": rules["base64"]}),
    ],
)
def test_an_invalid_dictionary_is_rejected(mutate):
    rules = json.loads(json.dumps(RULES))
    mutate(rules)

    with pytest.raises(CustomException) as error:
        validate_secret_rules(rules)

    assert error.value.status_code == 400
    assert "secret rules" in error.value.details


def test_a_missing_dictionary_is_an_error_rather_than_a_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSOFT9_SECRET_RULES_PATH", str(tmp_path / "absent.json"))

    with pytest.raises(CustomException) as error:
        load_secret_rules()

    assert "missing" in error.value.details


@pytest.mark.parametrize(
    "rule,expected",
    [("base64", ("base64", "")), ("fernet", ("fernet", "")), ("jwt:JWT_SECRET", ("jwt", "JWT_SECRET"))],
)
def test_a_rule_declaration_is_parsed(rule, expected):
    assert parse_secret_rule(rule) == expected


@pytest.mark.parametrize("rule", ["jwt", "jwt:", "jwt:1BAD", "base64:KEY", "aes", ""])
def test_an_unsupported_rule_is_rejected(rule):
    with pytest.raises(CustomException):
        parse_secret_rule(rule)


# ── generation ──────────────────────────────────────────────────────


def test_a_base64_secret_matches_the_template_byte_length():
    value = generate_rule_secret("SECRET_KEY", "base64", BASE64_TEMPLATE, validate_secret_rules(RULES), lambda _: "")

    assert value != BASE64_TEMPLATE
    assert len(_decoded(value)) == 32
    assert re.fullmatch(r"[A-Za-z0-9+/]{43}=", value)


def test_a_fernet_secret_is_32_url_safe_bytes_with_padding():
    value = generate_rule_secret("AIRFLOW__CORE__FERNET_KEY", "fernet", "ignored", validate_secret_rules(RULES), lambda _: "")

    assert len(value) == 44
    assert value.endswith("=")
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}=", value)
    assert len(base64.urlsafe_b64decode(value)) == 32


def test_a_jwt_secret_is_signed_with_the_declared_key_and_keeps_its_lifetime():
    profiles = validate_secret_rules(RULES)

    value = generate_rule_secret("ANON_KEY", "jwt:JWT_SECRET", JWT_TEMPLATE, profiles, lambda name: "signing-secret")

    header_text, payload_text, signature_text = value.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_text + "=" * (-len(payload_text) % 4)))
    assert json.loads(base64.urlsafe_b64decode(header_text + "=" * (-len(header_text) % 4)))["alg"] == "HS256"
    assert payload["role"] == "anon"
    assert payload["exp"] - payload["iat"] == JWT_TEMPLATE_PAYLOAD["exp"] - JWT_TEMPLATE_PAYLOAD["iat"]
    assert payload["iat"] > JWT_TEMPLATE_PAYLOAD["iat"]
    expected = hmac.new(b"signing-secret", f"{header_text}.{payload_text}".encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4)) == expected


def test_a_value_that_moved_from_plain_to_rule_is_not_reused():
    profiles = validate_secret_rules(RULES)

    assert matches_rule("SECRET_KEY", "base64", BASE64_TEMPLATE, profiles)
    assert not matches_rule("SECRET_KEY", "base64", "not/base64 value!", profiles)
    # Structure alone is not enough once the signing key is known.
    assert matches_rule("SECRET_KEY", "jwt:JWT_SECRET", JWT_TEMPLATE, profiles, None)
    assert not matches_rule("SECRET_KEY", "jwt:JWT_SECRET", JWT_TEMPLATE, profiles, lambda _: "other-secret")


# ── install pipeline ────────────────────────────────────────────────


FERNET_TEMPLATE = base64.urlsafe_b64encode(b"\x02" * 32).decode()


def test_object_declarations_are_written_to_the_instance_env(tmp_path, monkeypatch):
    directory = _instance(
        tmp_path,
        monkeypatch,
        {"JWT_SECRET": "a1" * 32, "ANON_KEY": JWT_TEMPLATE, "SECRET_KEY": BASE64_TEMPLATE, "FERNET": FERNET_TEMPLATE},
        ["JWT_SECRET", {"ANON_KEY": "jwt:JWT_SECRET"}, {"SECRET_KEY": "base64"}, {"FERNET": "fernet"}],
    )

    initialize_install_secrets(directory, "app", "supabase")

    values = dotenv_values(directory / ".env")
    assert values["JWT_SECRET"] != "a1" * 32
    assert len(_decoded(values["SECRET_KEY"])) == 32
    assert len(values["FERNET"]) == 44
    assert values["FERNET"] != FERNET_TEMPLATE
    assert values["ANON_KEY"].count(".") == 2
    # The JWT is signed with the generated signing secret, not the template placeholder.
    header, payload, signature = values["ANON_KEY"].split(".")
    expected = hmac.new(values["JWT_SECRET"].encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)) == expected


def test_a_retry_reuses_rule_values_and_a_rule_change_regenerates(tmp_path, monkeypatch):
    # ``a1`` repeated is both a valid plain template and a decodable Base64 value.
    values = {"SECRET_KEY": "a1" * 32}
    first = _instance(tmp_path, monkeypatch, values, ["SECRET_KEY"])
    initialize_install_secrets(first, "app", "dify")
    generated = dotenv_values(first / ".env")["SECRET_KEY"]

    retry = _instance(tmp_path, monkeypatch, values, ["SECRET_KEY"])
    initialize_install_secrets(retry, "app", "dify")
    assert dotenv_values(retry / ".env")["SECRET_KEY"] == generated

    changed = _instance(tmp_path, monkeypatch, values, [{"SECRET_KEY": "base64"}])
    initialize_install_secrets(changed, "app", "dify")
    assert dotenv_values(changed / ".env")["SECRET_KEY"] != generated


def test_a_comma_separated_declaration_regenerates_each_item(tmp_path, monkeypatch):
    template = ",".join(["k9M2pQ7vN4xT8bL1sP5dH3cF6wY0zEaR"] * 4)
    directory = _instance(tmp_path, monkeypatch, {"APP_KEYS": template}, ["APP_KEYS"])

    initialize_install_secrets(directory, "app", "strapi")

    items = dotenv_values(directory / ".env")["APP_KEYS"].split(",")
    assert len(items) == 4
    assert all(len(item) == 32 and item.isalnum() for item in items)
    assert len(set(items)) == 4


def test_a_missing_dictionary_leaves_the_instance_env_untouched(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("WEBSOFT9_SECRET_RULES_PATH", str(tmp_path / "absent.json"))
    directory = tmp_path / "instance"
    directory.mkdir()
    original = f"SECRET_KEY={BASE64_TEMPLATE}\n"
    (directory / ".env").write_text(original, encoding="utf-8")
    (directory / "variables.json").write_text(json.dumps({"env": {"secrets": [{"SECRET_KEY": "base64"}]}}))

    with pytest.raises(CustomException) as error:
        initialize_install_secrets(directory, "app", "dify")

    assert "secret rules" in error.value.details
    assert (directory / ".env").read_text(encoding="utf-8") == original


@pytest.mark.parametrize("override", [False, True])
def test_jwt_signer_resolves_nested_final_values_and_retry_preserves_raw_references(tmp_path, monkeypatch, override):
    template = {"JWT_SECRET": "${ALIAS}", "ALIAS": "prefix-$SEED", "SEED": "a1" * 32, "ANON_KEY": JWT_TEMPLATE}
    declarations = [{"ANON_KEY": "jwt:JWT_SECRET"}, "JWT_SECRET", "SEED"]
    directory = _instance(tmp_path, monkeypatch, template, declarations)
    settings = {"SEED": "b2" * 32} if override else {}
    initialize_install_secrets(directory, "app", "supabase", settings)
    values = dotenv_values(directory / ".env", interpolate=False)
    assert values["JWT_SECRET"] == "${ALIAS}"
    assert values["ALIAS"] == "prefix-$SEED"
    seed = settings.get("SEED", values["SEED"])
    assert matches_rule(
        "ANON_KEY", "jwt:JWT_SECRET", values["ANON_KEY"], validate_secret_rules(RULES), lambda _: f"prefix-{seed}"
    )
    retry = _instance(tmp_path, monkeypatch, template, declarations)
    initialize_install_secrets(retry, "app", "supabase", settings)
    assert dotenv_values(retry / ".env", interpolate=False) == values


@pytest.mark.parametrize(
    "references",
    [
        {"JWT_SECRET": "${ALIAS}", "ALIAS": "$JWT_SECRET"},
        {"JWT_SECRET": "${MISSING}"},
        {"JWT_SECRET": "${EMPTY}", "EMPTY": ""},
        {"JWT_SECRET": "${SEED:-fallback}", "SEED": "synthetic"},
        {"JWT_SECRET": "$$SEED", "SEED": "synthetic"},
    ],
)
def test_invalid_jwt_signer_references_do_not_write_env_or_secret_cache(tmp_path, monkeypatch, references):
    directory = _instance(tmp_path, monkeypatch, {**references, "ANON_KEY": JWT_TEMPLATE}, [{"ANON_KEY": "jwt:JWT_SECRET"}])
    original = (directory / ".env").read_bytes()
    with pytest.raises(CustomException):
        initialize_install_secrets(directory, "app", "supabase")
    assert (directory / ".env").read_bytes() == original
    assert not list((tmp_path / "data/config/apphub/install-secrets").glob("*.json"))

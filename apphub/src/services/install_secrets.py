from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import string
import tempfile
from pathlib import Path

from dotenv import dotenv_values, set_key

from src.core.exception import CustomException
from src.services.secret_rules import generate_rule_secret, load_secret_rules, matches_rule, parse_secret_rule
from src.utils.password_generator import PasswordGenerator

_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
_VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PLATFORM_FIELDS = {"W9_POWER_PASSWORD", "W9_RCODE"}


def _invalid(field: str, reason: str) -> CustomException:
    return CustomException(400, "Invalid installation secret", f"{field}: {reason}")


def _parts(field: str, value: str) -> tuple[str, list[tuple[str, str]]]:
    prefix = "sk-" if value.startswith("sk-") else ""
    body = value[len(prefix) :]
    if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", body):
        raise _invalid(field, "UUID requires an explicit generation algorithm")
    segments = body.split("-")
    if not prefix and len(segments) > 1 and re.fullmatch(r"[A-Za-z]+", segments[0]):
        raise _invalid(field, "ambiguous prefix")
    result = []
    for segment in segments:
        if re.fullmatch(r"[0-9]+", segment):
            alphabet = string.digits
        elif re.fullmatch(r"[0-9a-fA-F]+", segment):
            letters = ""
            if any(character.islower() for character in segment):
                letters += "abcdef"
            if any(character.isupper() for character in segment):
                letters += "ABCDEF"
            alphabet = string.digits + letters
        elif re.fullmatch(r"[A-Za-z0-9]+", segment):
            alphabet = ""
            if any(character.islower() for character in segment):
                alphabet += string.ascii_lowercase
            if any(character.isupper() for character in segment):
                alphabet += string.ascii_uppercase
            if any(character.isdigit() for character in segment):
                alphabet += string.digits
        else:
            raise _invalid(field, "unsupported format")
        result.append((segment, alphabet))
    if sum(len(segment) for segment, _ in result) < 12:
        raise _invalid(field, "random portion is too short")
    return prefix, result


def _matches(field: str, template: str, value: str) -> bool:
    if "," in template:
        # Comma-separated declarations (for example Strapi ``APP_KEYS``) regenerate each item
        # independently, so validation has to compare item by item.
        expected = template.split(",")
        segments = value.split(",")
        return len(expected) == len(segments) and all(
            _matches_item(field, original, segment) for original, segment in zip(expected, segments, strict=False)
        )
    return _matches_item(field, template, value)


def _matches_item(field: str, template: str, value: str) -> bool:
    prefix, parts = _parts(field, template)
    if not value.startswith(prefix):
        return False
    segments = value[len(prefix) :].split("-")
    return len(segments) == len(parts) and all(
        len(segment) == len(original) and all(character in alphabet for character in segment)
        for segment, (original, alphabet) in zip(segments, parts, strict=False)
    )


def generate_secret(field: str, template: str) -> str:
    if "," in template:
        items = template.split(",")
        if any(not item.strip() for item in items):
            raise _invalid(field, "unsupported format")
        return ",".join(generate_secret_item(field, item) for item in items)
    return generate_secret_item(field, template)


def generate_secret_item(field: str, template: str) -> str:
    prefix, parts = _parts(field, template)
    for _ in range(128):
        segments = []
        for original, alphabet in parts:
            required = []
            for category in (string.ascii_lowercase, string.ascii_uppercase, string.digits):
                if any(character in category for character in original):
                    required.append(secrets.choice("".join(character for character in alphabet if character in category)))
            characters = required + [secrets.choice(alphabet) for _ in range(len(original) - len(required))]
            secrets.SystemRandom().shuffle(characters)
            segments.append("".join(characters))
        generated = prefix + "-".join(segments)
        if generated != template:
            return generated
    raise _invalid(field, "unable to generate a distinct value")


def _resolve_reference_value(values: dict, field: str, visiting: frozenset[str] = frozenset()) -> str:
    if field in visiting:
        raise _invalid(field, "circular variable reference")
    value = values.get(field)
    if not isinstance(value, str) or not value:
        raise _invalid(field, "missing or empty value")
    resolved = _REFERENCE.sub(
        lambda match: _resolve_reference_value(values, match.group(1) or match.group(2), visiting | {field}), value
    )
    if "$" in resolved:
        raise _invalid(field, "unsupported variable reference")
    return resolved


def _validate_references(values: dict, fields: list[str]) -> None:
    for field in fields:
        _resolve_reference_value(values, field)


def _secret_declarations(directory: Path) -> dict[str, str]:
    """Map every declared key to its rule, using ``""`` for shape-based generation.

    ``env.secrets`` accepts plain variable names and single-key objects naming a
    published rule (``base64``, ``fernet``, ``jwt:<SIGNING_KEY>``).
    """
    metadata_path = directory / "variables.json"
    if not metadata_path.is_file():
        return {}
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        items = metadata.get("env", {}).get("secrets", [])
    except (ValueError, AttributeError, OSError):
        raise _invalid("env.secrets", "invalid template declaration") from None
    if not isinstance(items, list):
        raise _invalid("env.secrets", "expected a list of declarations")

    declarations: dict[str, str] = {}
    for item in items:
        if isinstance(item, str):
            key, rule = item, ""
        elif isinstance(item, dict) and len(item) == 1:
            key, rule = next(iter(item.items()))
            if not isinstance(rule, str):
                raise _invalid("env.secrets", "expected a rule name")
            # Validates the profile and its argument shape before anything is generated.
            parse_secret_rule(rule)
        else:
            raise _invalid("env.secrets", "expected variable names or single-key rule objects")
        if not isinstance(key, str) or not _VARIABLE.fullmatch(key):
            raise _invalid("env.secrets", "expected a list of variable names")
        declarations.setdefault(key, rule)
    return declarations


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def forget_install_secrets(app_id: str) -> None:
    data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
    storage = Path(data_root) / "config/apphub/install-secrets"
    if not storage.exists():
        return
    try:
        if storage.is_symlink():
            raise OSError("Invalid secret storage")
        identity = hashlib.sha256(app_id.encode("utf-8")).hexdigest()
        descriptor = os.open(storage / f"{identity}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            (storage / f"{identity}.json").unlink(missing_ok=True)
    except Exception:
        raise CustomException(
            500, "Installation secret cleanup failed", "Unable to safely remove installation secrets."
        ) from None


def initialize_install_secrets(directory: str | Path, app_id: str, app_name: str, settings: dict | None = None) -> None:
    directory = Path(directory)
    settings = settings or {}
    env_path = directory / ".env"
    declarations = _secret_declarations(directory)
    # dotenv returns `str | None` for keys without a value; treat those as empty so the format
    # checks below never index or search a None.
    templates: dict[str, str] = {key: value or "" for key, value in dotenv_values(env_path, interpolate=False).items()}
    for field in declarations:
        if field not in templates:
            raise _invalid(field, "missing from template")
        if not templates[field] and field not in _PLATFORM_FIELDS:
            raise _invalid(field, "empty template value")
    targets = list(dict.fromkeys([*declarations, *(field for field in _PLATFORM_FIELDS if field in templates)]))
    if not targets:
        return
    # The published dictionary is loaded once and only when a rule declaration exists: a
    # missing or invalid dictionary must fail instead of falling back to a built-in copy.
    profiles: dict[str, dict[str, object]] | None = None

    def secret_profiles() -> dict[str, dict[str, object]]:
        nonlocal profiles
        if profiles is None:
            profiles = load_secret_rules()
        return profiles

    data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
    storage = Path(data_root) / "config/apphub/install-secrets"
    temporary = None
    try:
        storage.mkdir(parents=True, mode=0o700, exist_ok=True)
        if storage.is_symlink():
            raise OSError("Invalid secret storage")
        storage.chmod(0o700)
        identity = hashlib.sha256(app_id.encode("utf-8")).hexdigest()
        cache_path = storage / f"{identity}.json"
        lock_descriptor = os.open(storage / f"{identity}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock_descriptor, "a") as lock:
            os.fchmod(lock.fileno(), 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            cached: dict[str, str] = {}
            cached_templates: dict[str, str] = {}
            cached_rules: dict[str, str] = {}
            if cache_path.exists():
                descriptor = os.open(cache_path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor) as handle:
                    os.fchmod(handle.fileno(), 0o600)
                    payload = json.load(handle)
                if payload.get("app_name") != app_name or not isinstance(payload.get("values"), dict):
                    raise _invalid("env.secrets", "stored installation identity does not match")
                cached = dict(payload["values"])
                cached_templates = dict(payload.get("templates") or {})
                if not isinstance(cached_templates, dict):
                    raise _invalid("env.secrets", "invalid stored template format")
                cached_rules = dict(payload.get("rules") or {})
                if not isinstance(cached_rules, dict):
                    raise _invalid("env.secrets", "invalid stored rule format")
            final: dict[str, str] = {**templates, **settings}
            updates: dict[str, str] = {}

            def resolve(name: str) -> str:
                return _resolve_reference_value(final, name)

            def decide(field: str) -> str | None:
                """Value for ``field``; ``None`` means the template only references another key."""
                rule = declarations.get(field, "")
                template = templates[field]
                if field in settings:
                    supplied = settings[field]
                    return supplied if isinstance(supplied, str) else ""
                if (
                    field not in _PLATFORM_FIELDS
                    and _REFERENCE.search(template)
                    and (field not in cached or cached_templates.get(field) != template)
                ):
                    cached.pop(field, None)
                    return None
                if field in cached and cached_rules.get(field, "") == rule:
                    return cached[field]
                if field == "W9_POWER_PASSWORD":
                    return str(PasswordGenerator.generate_strong_password())
                if field == "W9_RCODE":
                    return str(PasswordGenerator.generate_random_string_with_rules(12))
                if rule:
                    return generate_rule_secret(field, rule, template, secret_profiles(), resolve)
                return generate_secret(field, template)

            # JWT declarations depend on their signing key, which may itself be generated, so they
            # are produced once every other value is known instead of relying on declaration order.
            ordered = [field for field in targets if not declarations.get(field, "").startswith("jwt")]
            ordered += [field for field in targets if declarations.get(field, "").startswith("jwt")]
            for field in ordered:
                value = decide(field)
                if value is None:
                    continue
                rule = declarations.get(field, "")
                template = templates[field]
                if not isinstance(value, str) or not value or any(character in value for character in "\r\n\x00"):
                    raise _invalid(field, "invalid supplied or stored value")
                if field not in settings and any(character in value for character in "$ \t#"):
                    # Generated values must survive Compose interpolation and .env parsing verbatim.
                    raise _invalid(field, "generated value is not safe for the environment file")
                if field in _PLATFORM_FIELDS or _REFERENCE.search(template):
                    pass
                elif rule:
                    if not matches_rule(field, rule, value, secret_profiles(), resolve):
                        raise _invalid(field, "supplied or stored value does not match the declared rule")
                elif not _matches(field, template, value):
                    raise _invalid(field, "supplied or stored value does not match template format")
                updates[field] = value
                final[field] = value
            _validate_references(final, targets)
            _atomic_json(
                cache_path,
                {
                    "app_name": app_name,
                    "values": {**cached, **updates},
                    "templates": {field: templates[field] for field in targets},
                    "rules": {field: declarations.get(field, "") for field in targets},
                },
            )
            with tempfile.NamedTemporaryFile(dir=directory, delete=False) as scratch:
                temporary = Path(scratch.name)
            shutil.copyfile(env_path, temporary)
            for field, value in updates.items():
                set_key(str(temporary), field, value)
            with temporary.open("rb") as staged:
                os.fsync(staged.fileno())
            temporary.chmod(0o600)
            os.replace(temporary, env_path)
    except CustomException:
        raise
    except Exception:
        raise CustomException(
            500, "Installation secret initialization failed", "Unable to safely read or save installation secrets."
        ) from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

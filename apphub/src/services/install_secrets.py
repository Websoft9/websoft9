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
from src.utils.password_generator import PasswordGenerator


_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
_VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PLATFORM_FIELDS = {"W9_POWER_PASSWORD", "W9_RCODE"}


def _invalid(field: str, reason: str) -> CustomException:
    return CustomException(400, "Invalid installation secret", f"{field}: {reason}")


def _parts(field: str, value: str) -> tuple[str, list[tuple[str, str]]]:
    prefix = "sk-" if value.startswith("sk-") else ""
    body = value[len(prefix):]
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
    prefix, parts = _parts(field, template)
    if not value.startswith(prefix):
        return False
    segments = value[len(prefix):].split("-")
    return len(segments) == len(parts) and all(
        len(segment) == len(original) and all(character in alphabet for character in segment)
        for segment, (original, alphabet) in zip(segments, parts)
    )


def generate_secret(field: str, template: str) -> str:
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


def _validate_references(values: dict, fields: list[str]) -> None:
    def resolve(field: str, visiting: set[str]) -> str:
        if field in visiting:
            raise _invalid(field, "circular variable reference")
        value = values.get(field)
        if not isinstance(value, str) or not value:
            raise _invalid(field, "missing or empty value")
        visiting = visiting | {field}
        resolved = _REFERENCE.sub(lambda match: resolve(match.group(1) or match.group(2), visiting), value)
        if "$" in resolved:
            raise _invalid(field, "unsupported variable reference")
        return resolved

    for field in fields:
        resolve(field, set())


def _secret_fields(directory: Path) -> list[str]:
    metadata_path = directory / "variables.json"
    if not metadata_path.is_file():
        return []
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        fields = metadata.get("env", {}).get("secrets", [])
    except (ValueError, AttributeError, OSError):
        raise _invalid("env.secrets", "invalid template declaration") from None
    if not isinstance(fields, list) or any(not isinstance(field, str) or not _VARIABLE.fullmatch(field) for field in fields):
        raise _invalid("env.secrets", "expected a list of variable names")
    return list(dict.fromkeys(fields))


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
        raise CustomException(500, "Installation secret cleanup failed", "Unable to safely remove installation secrets.") from None


def initialize_install_secrets(directory: str | Path, app_id: str, app_name: str, settings: dict | None = None) -> None:
    directory = Path(directory)
    env_path = directory / ".env"
    fields = _secret_fields(directory)
    templates = dict(dotenv_values(env_path, interpolate=False))
    for field in fields:
        if field not in templates:
            raise _invalid(field, "missing from template")
        if not templates[field] and field not in _PLATFORM_FIELDS:
            raise _invalid(field, "empty template value")
    targets = list(dict.fromkeys(fields + [field for field in _PLATFORM_FIELDS if field in templates]))
    if not targets:
        return
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
            cached = {}
            cached_templates = {}
            if cache_path.exists():
                descriptor = os.open(cache_path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor) as handle:
                    os.fchmod(handle.fileno(), 0o600)
                    payload = json.load(handle)
                if payload.get("app_name") != app_name or not isinstance(payload.get("values"), dict):
                    raise _invalid("env.secrets", "stored installation identity does not match")
                cached = payload["values"]
                cached_templates = payload.get("templates", {})
                if not isinstance(cached_templates, dict):
                    raise _invalid("env.secrets", "invalid stored template format")
            final = {**templates, **(settings or {})}
            updates = {}
            for field in targets:
                template = templates[field]
                if field in (settings or {}):
                    value = settings[field]
                elif field not in _PLATFORM_FIELDS and _REFERENCE.search(template) and (
                    field not in cached or cached_templates.get(field) != template
                ):
                    cached.pop(field, None)
                    continue
                elif field in cached:
                    value = cached[field]
                elif field == "W9_POWER_PASSWORD":
                    value = PasswordGenerator.generate_strong_password()
                elif field == "W9_RCODE":
                    value = PasswordGenerator.generate_random_string_with_rules(12)
                else:
                    value = generate_secret(field, template)
                if not isinstance(value, str) or not value or any(character in value for character in "\r\n\x00"):
                    raise _invalid(field, "invalid supplied or stored value")
                if field not in _PLATFORM_FIELDS and not _REFERENCE.search(template) and not _matches(field, template, value):
                    raise _invalid(field, "supplied or stored value does not match template format")
                updates[field] = value
                final[field] = value
            _validate_references(final, targets)
            _atomic_json(cache_path, {
                "app_name": app_name,
                "values": {**cached, **updates},
                "templates": {field: templates[field] for field in targets},
            })
            with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
                temporary = Path(handle.name)
            shutil.copyfile(env_path, temporary)
            for field, value in updates.items():
                set_key(str(temporary), field, value)
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            temporary.chmod(0o600)
            os.replace(temporary, env_path)
    except CustomException:
        raise
    except Exception:
        raise CustomException(500, "Installation secret initialization failed", "Unable to safely read or save installation secrets.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
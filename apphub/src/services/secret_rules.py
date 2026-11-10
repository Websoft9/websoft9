"""Shared secret generation profiles published with the App Store library.

``variables.json`` declares ``env.secrets`` entries either as plain variable names
(shape-based generation) or as single-key objects naming a profile from
``metadata/secret-rules.json``. The dictionary ships next to
``metadata/database-types.json``; when it is missing or invalid the platform must
fail instead of falling back to built-in copies or ordinary random strings.

Everything here is pure: no instance state, no file writes.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any, Callable

from src.core.config import ConfigManager
from src.core.exception import CustomException

SECRET_RULES_FILENAME = "secret-rules.json"
SECRET_RULES_ENV = "WEBSOFT9_SECRET_RULES_PATH"
REQUIRED_PROFILES = ("base64", "fernet", "jwt")

_RULE = re.compile(r"^(?P<profile>base64|fernet|jwt)(?::(?P<signing>[A-Za-z_][A-Za-z0-9_]*))?$")
_PROFILE_OPTIONS = {"generator", "encoding", "bytes", "algorithm", "description"}


def _invalid(detail: str) -> CustomException:
    return CustomException(400, "Invalid installation secret", f"secret rules: {detail}")


def _candidates() -> list[Path]:
    """Where the published dictionary may live, most specific first."""
    candidates: list[Path] = []
    override = os.getenv(SECRET_RULES_ENV)
    if override:
        candidates.append(Path(override))
    try:
        library_path = ConfigManager("system.ini").get_value("docker_library", "path")
    except Exception:  # pragma: no cover - configuration failures fall through
        return candidates
    if library_path:
        # The shared dictionaries are published next to the library, not inside it.
        candidates.append(Path(library_path).parent / "metadata" / SECRET_RULES_FILENAME)
        candidates.append(Path(library_path) / "metadata" / SECRET_RULES_FILENAME)
    return candidates


def validate_secret_rules(payload: Any) -> dict[str, dict[str, Any]]:
    """Validate the dictionary and return the machine parameters per profile."""
    if not isinstance(payload, dict):
        raise _invalid("expected an object")

    profiles: dict[str, dict[str, Any]] = {}
    for name, profile in payload.items():
        if name not in REQUIRED_PROFILES:
            raise _invalid(f"unknown profile {name!r}")
        if not isinstance(profile, dict):
            raise _invalid(f"{name}: expected an object")
        unknown = set(profile) - _PROFILE_OPTIONS
        if unknown:
            raise _invalid(f"{name}: unsupported option {sorted(unknown)[0]!r}")
        description = profile.get("description")
        if not isinstance(description, str) or not description.strip():
            raise _invalid(f"{name}: description is required")

        if name == "jwt":
            if profile.get("generator") != "jwt" or profile.get("algorithm") != "HS256":
                raise _invalid("jwt: generator and algorithm must be jwt/HS256")
            profiles[name] = {"generator": "jwt", "algorithm": "HS256"}
            continue

        if profile.get("generator") != "random_bytes":
            raise _invalid(f"{name}: generator must be random_bytes")
        encoding = "base64" if name == "base64" else "base64url"
        if profile.get("encoding") != encoding:
            raise _invalid(f"{name}: encoding must be {encoding}")

        raw_bytes = profile.get("bytes")
        if name == "fernet":
            if raw_bytes != 32:
                raise _invalid("fernet: bytes must be 32")
            raw_bytes = 32
        elif raw_bytes is not None and (isinstance(raw_bytes, bool) or not isinstance(raw_bytes, int) or raw_bytes < 1):
            raise _invalid("base64: bytes must be a positive integer")
        profiles[name] = {"generator": "random_bytes", "encoding": encoding, "bytes": raw_bytes}

    missing = [name for name in REQUIRED_PROFILES if name not in profiles]
    if missing:
        raise _invalid(f"missing profile {missing[0]!r}")
    return profiles


def load_secret_rules() -> dict[str, dict[str, Any]]:
    """Read and validate the published dictionary; never fall back to a built-in copy."""
    for candidate in _candidates():
        try:
            raw = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            raise _invalid(f"{candidate} is not valid JSON") from None
        return validate_secret_rules(payload)
    raise _invalid("the published dictionary is missing")


def parse_secret_rule(rule: str) -> tuple[str, str]:
    """Split a declaration rule into its profile and optional signing-key name."""
    match = _RULE.fullmatch(rule or "")
    if not match:
        raise _invalid(f"unsupported declaration {rule!r}")
    profile = match.group("profile")
    signing = match.group("signing") or ""
    if profile == "jwt" and not signing:
        raise _invalid("jwt declarations require a signing-key variable")
    if profile != "jwt" and signing:
        raise _invalid(f"{profile} declarations take no argument")
    return profile, signing


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError):
        raise _invalid("value is not url-safe base64") from None


def _template_bytes(field: str, encoding: str, template: str) -> bytes:
    """Decode the ``.env`` default to learn the byte length the value must have."""
    text = (template or "").strip()
    if not text:
        raise _invalid(f"{field}: a nonempty default value is required")
    if encoding == "base64":
        try:
            return base64.b64decode(text + "=" * (-len(text) % 4), validate=True)
        except (binascii.Error, ValueError):
            raise _invalid(f"{field}: default value is not standard base64") from None
    return _b64url_decode(text)


def _sign_jwt(field: str, template: str, signing: str, signing_value: str) -> str:
    parts = (template or "").strip().split(".")
    if len(parts) != 3:
        raise _invalid(f"{field}: default value is not a JWT")
    try:
        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
    except ValueError:
        raise _invalid(f"{field}: default JWT header or payload is not JSON") from None
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise _invalid(f"{field}: default JWT header or payload is not an object")
    if header.get("alg") != "HS256":
        raise _invalid(f"{field}: only HS256 JWTs can be generated")
    if not signing or not signing_value:
        raise _invalid(f"{field}: signing key {signing or '<missing>'} has no value")

    now = int(time.time())
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    payload["iat"] = now
    if isinstance(issued_at, int) and isinstance(expires_at, int) and expires_at > issued_at:
        # Preserve the template's lifetime instead of inventing a new policy.
        payload["exp"] = now + (expires_at - issued_at)

    header_text = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_text = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_text}.{payload_text}"
    signature = hmac.new(signing_value.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def generate_rule_secret(
    field: str,
    rule: str,
    template: str,
    profiles: dict[str, dict[str, Any]],
    resolve: Callable[[str], str],
) -> str:
    """Produce one value for a rule declaration."""
    profile_name, signing = parse_secret_rule(rule)
    profile = profiles.get(profile_name)
    if profile is None:
        raise _invalid(f"{field}: rule {profile_name!r} is not published")

    if profile["generator"] == "jwt":
        return _sign_jwt(field, template, signing, resolve(signing))

    raw_bytes = profile.get("bytes")
    if raw_bytes is None:
        raw_bytes = len(_template_bytes(field, profile["encoding"], template))
    raw = secrets.token_bytes(int(raw_bytes))
    if profile["encoding"] == "base64":
        return base64.b64encode(raw).decode("ascii")
    # URL-safe output keeps ``=`` padding: Fernet keys are 44 characters, not 43.
    return base64.urlsafe_b64encode(raw).decode("ascii")


def matches_rule(
    field: str,
    rule: str,
    value: str,
    profiles: dict[str, dict[str, Any]],
    resolve: Callable[[str], str] | None = None,
) -> bool:
    """Whether an existing value still satisfies its declaration.

    Cached values must keep matching: a declaration that moved from a plain name
    to a rule (or the reverse) cannot silently reuse the previous value.
    """
    profile_name, signing = parse_secret_rule(rule)
    profile = profiles.get(profile_name)
    if profile is None:
        raise _invalid(f"{field}: rule {profile_name!r} is not published")

    if profile["generator"] == "jwt":
        parts = (value or "").split(".")
        if len(parts) != 3:
            return False
        try:
            header = json.loads(_b64url_decode(parts[0]))
        except (CustomException, ValueError):
            return False
        if not isinstance(header, dict) or header.get("alg") != "HS256":
            return False
        if resolve is None:
            return True
        signing_value = resolve(signing)
        if not signing_value:
            return True
        expected = hmac.new(signing_value.encode("utf-8"), f"{parts[0]}.{parts[1]}".encode("ascii"), hashlib.sha256).digest()
        try:
            actual = _b64url_decode(parts[2])
        except CustomException:
            return False
        return hmac.compare_digest(expected, actual)

    try:
        if profile["encoding"] == "base64":
            decoded = base64.b64decode(value + "=" * (-len(value) % 4), validate=True)
        else:
            decoded = _b64url_decode(value)
    except (binascii.Error, ValueError, CustomException):
        return False
    raw_bytes = profile.get("bytes")
    return raw_bytes is None or len(decoded) == int(raw_bytes)

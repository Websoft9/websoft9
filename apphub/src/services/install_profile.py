from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.core.exception import CustomException


_PROFILE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PROFILE_COMPOSE_PATTERN = re.compile(r"^docker-compose\.([a-z0-9][a-z0-9-]*)\.yml$")
EXTERNAL_DATABASE_CONNECTION_SETTING_KEYS = frozenset({
    "W9_DB_HOST_SET",
    "W9_DB_PORT_SET",
    "W9_DB_NAME_SET",
    "W9_DB_USER_SET",
    "W9_DB_PASSWORD_SET",
})


@dataclass(frozen=True)
class ExternalDatabaseConnection:
    database_type: str
    version: tuple[int, ...]


def get_port_check_settings(profile: str | None, settings: dict | None, app_directory: str | Path | None = None) -> dict:
    if not is_external_database_profile(app_directory, profile):
        return settings or {}
    return {
        key: value
        for key, value in (settings or {}).items()
        if key not in EXTERNAL_DATABASE_CONNECTION_SETTING_KEYS
    }


def _load_template_settings(env_path: Path) -> set[str]:
    settings: set[str] = set()
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key.startswith("W9_") and key.endswith("_SET"):
            settings.add(key)
    return settings


def get_profile_template(app_directory: str | Path, profile: str) -> tuple[Path, Path]:
    if not isinstance(profile, str) or not _PROFILE_NAME_PATTERN.fullmatch(profile):
        raise CustomException(400, "Invalid Request", "Invalid installation profile.")

    app_path = Path(app_directory)
    compose_path = app_path / f"docker-compose.{profile}.yml"
    env_path = app_path / f".env.{profile}"
    if not compose_path.is_file() or not env_path.is_file():
        raise CustomException(400, "Invalid Request", "The selected installation profile is not available locally.")
    return compose_path, env_path


def is_external_database_profile(app_directory: str | Path | None, profile: str | None) -> bool:
    if app_directory is None or profile is None:
        return False

    _, env_path = get_profile_template(app_directory, profile)
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "W9_DATABASE_MODE":
            return value.strip().strip("\"'") == "external"
    return False


def validate_profile_settings(app_directory: str | Path, profile: str | None, settings: dict | None) -> None:
    if profile is None:
        return

    _, env_path = get_profile_template(app_directory, profile)
    expected_keys = _load_template_settings(env_path)
    supplied_settings = settings or {}
    if set(supplied_settings) != expected_keys:
        raise CustomException(400, "Invalid Request", "Profile settings do not match the selected installation profile.")
    if any(not isinstance(value, str) for value in supplied_settings.values()):
        raise CustomException(400, "Invalid Request", "Profile settings must be strings.")


def validate_external_database_connection(host: str, port: int | str, database_name: str, username: str, password: str) -> ExternalDatabaseConnection:
    if not all(isinstance(value, str) and value.strip() for value in (host, database_name, username, password)):
        raise CustomException(400, "Invalid Request", "External database connection information is required.")
    if "://" in host or any(character.isspace() for character in host):
        raise CustomException(400, "Invalid Request", "External database host is invalid.")

    try:
        normalized_port = int(port)
    except (TypeError, ValueError) as exc:
        raise CustomException(400, "Invalid Request", "External database port is invalid.") from exc
    if normalized_port < 1 or normalized_port > 65535:
        raise CustomException(400, "Invalid Request", "External database port is invalid.")

    try:
        import pymysql
    except ImportError as exc:
        raise CustomException(503, "External Database Connection Unavailable", "The database connection test is not available.") from exc

    try:
        connection = pymysql.connect(
            host=host,
            port=normalized_port,
            user=username,
            password=password,
            database=database_name,
            connect_timeout=8,
            read_timeout=8,
            write_timeout=8,
            autocommit=True,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.execute("SELECT VERSION()")
                version_row = cursor.fetchone()
        finally:
            connection.close()
    except pymysql.MySQLError:
        return _validate_postgresql_connection(host, normalized_port, database_name, username, password)

    version_text = str(version_row[0] if isinstance(version_row, (tuple, list)) else version_row or "").lower()
    actual_type = "mariadb" if "mariadb" in version_text else "mysql"
    version_numbers = re.findall(r"\d+(?:\.\d+)*", version_text)
    version = version_numbers[-1] if actual_type == "mariadb" else version_numbers[0] if version_numbers else ""
    return ExternalDatabaseConnection(actual_type, tuple(int(part) for part in version.split(".") if part))


def _validate_postgresql_connection(host: str, port: int | str, database_name: str, username: str, password: str) -> ExternalDatabaseConnection:
    if not all(isinstance(value, str) and value.strip() for value in (host, database_name, username, password)):
        raise CustomException(400, "Invalid Request", "External database connection information is required.")
    if "://" in host or any(character.isspace() for character in host):
        raise CustomException(400, "Invalid Request", "External database host is invalid.")
    try:
        normalized_port = int(port)
    except (TypeError, ValueError) as exc:
        raise CustomException(400, "Invalid Request", "External database port is invalid.") from exc
    if normalized_port < 1 or normalized_port > 65535:
        raise CustomException(400, "Invalid Request", "External database port is invalid.")

    try:
        import psycopg2
    except ImportError as exc:
        raise CustomException(503, "External Database Connection Unavailable", "The database connection test is not available.") from exc

    try:
        connection = psycopg2.connect(
            host=host,
            port=normalized_port,
            user=username,
            password=password,
            dbname=database_name,
            connect_timeout=8,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.execute("SHOW server_version_num")
                version_row = cursor.fetchone()
        finally:
            connection.close()
    except psycopg2.Error as exc:
        raise CustomException(400, "External Database Connection Failed", "Unable to connect to the specified database.") from exc
    version_number = int(version_row[0] if isinstance(version_row, (tuple, list)) else version_row)
    return ExternalDatabaseConnection("postgresql", (version_number // 10000, (version_number // 100) % 100, version_number % 100))


def matches_external_database_version(actual_version: tuple[int, ...], compatibility: list) -> bool | None:
    parsed_rules = 0
    for rule in compatibility:
        if not isinstance(rule, str):
            continue
        versions = [tuple(int(part) for part in value.split(".")) for value in re.findall(r"\d+(?:\.\d+)*", rule)]
        if not versions:
            continue
        parsed_rules += 1
        if "+" in rule and _compare_versions(actual_version, versions[0]) >= 0:
            return True
        if "+" not in rule and any(_version_matches_prefix(actual_version, version) for version in versions):
            return True
    return False if parsed_rules else None


def _compare_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    length = max(len(left), len(right))
    normalized_left = left + (0,) * (length - len(left))
    normalized_right = right + (0,) * (length - len(right))
    return (normalized_left > normalized_right) - (normalized_left < normalized_right)


def _version_matches_prefix(actual: tuple[int, ...], expected: tuple[int, ...]) -> bool:
    return len(actual) >= len(expected) and actual[:len(expected)] == expected


def materialize_profile_template(workspace_directory: str | Path, profile: str | None) -> None:
    if profile is None:
        return

    workspace_path = Path(workspace_directory)
    compose_path, env_path = get_profile_template(workspace_path, profile)
    shutil.copyfile(compose_path, workspace_path / "docker-compose.yml")
    shutil.copyfile(env_path, workspace_path / ".env")

    profile_names = []
    for candidate in workspace_path.iterdir():
        match = _PROFILE_COMPOSE_PATTERN.fullmatch(candidate.name)
        if match and candidate.is_file():
            profile_names.append(match.group(1))
            candidate.unlink()
    for profile_name in profile_names:
        candidate = workspace_path / f".env.{profile_name}"
        if candidate.is_file():
            candidate.unlink()
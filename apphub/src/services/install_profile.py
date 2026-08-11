from __future__ import annotations

import re
import shutil
from pathlib import Path

from src.core.exception import CustomException


_PROFILE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PROFILE_COMPOSE_PATTERN = re.compile(r"^docker-compose\.([a-z0-9][a-z0-9-]*)\.yml$")
EXTERNAL_MYSQL_CONNECTION_SETTING_KEYS = frozenset({
    "W9_DB_HOST_SET",
    "W9_DB_PORT_SET",
    "W9_DB_NAME_SET",
    "W9_DB_USER_SET",
    "W9_DB_PASSWORD_SET",
})


def get_port_check_settings(profile: str | None, settings: dict | None) -> dict:
    if profile != "external-mysql":
        return settings or {}
    return {
        key: value
        for key, value in (settings or {}).items()
        if key not in EXTERNAL_MYSQL_CONNECTION_SETTING_KEYS
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


def test_external_mysql_connection(host: str, port: int | str, database_name: str, username: str, password: str) -> None:
    if not all(isinstance(value, str) and value.strip() for value in (host, database_name, username, password)):
        raise CustomException(400, "Invalid Request", "External MySQL connection information is required.")
    if "://" in host or any(character.isspace() for character in host):
        raise CustomException(400, "Invalid Request", "External MySQL host is invalid.")

    try:
        normalized_port = int(port)
    except (TypeError, ValueError) as exc:
        raise CustomException(400, "Invalid Request", "External MySQL port is invalid.") from exc
    if normalized_port < 1 or normalized_port > 65535:
        raise CustomException(400, "Invalid Request", "External MySQL port is invalid.")

    try:
        import pymysql
    except ImportError as exc:
        raise CustomException(503, "External MySQL Connection Unavailable", "The MySQL connection test is not available.") from exc

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
        finally:
            connection.close()
    except pymysql.MySQLError as exc:
        raise CustomException(400, "External MySQL Connection Failed", "Unable to connect to the specified MySQL database.") from exc


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
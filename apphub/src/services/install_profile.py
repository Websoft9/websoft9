from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

from src.core.exception import CustomException


_COMPOSE_YAML = YAML()
_COMPOSE_YAML.preserve_quotes = True
_COMPOSE_YAML.width = 4096
_COMPOSE_YAML.indent(mapping=2, sequence=4, offset=2)


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

    base_port_settings: dict[str, str] = {}
    if app_directory is not None:
        base_env_path = Path(app_directory) / ".env"
        if base_env_path.is_file():
            base_port_settings = {
                key: value
                for key, value in _read_env_values(base_env_path).items()
                if "PORT_SET" in key
            }

    external_profile_settings = {
        key: value
        for key, value in (settings or {}).items()
        if key not in EXTERNAL_DATABASE_CONNECTION_SETTING_KEYS
    }
    return {**base_port_settings, **external_profile_settings}


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
    env_path = app_path / f".env.{profile}"
    if not env_path.is_file():
        raise CustomException(400, "Invalid Request", "The selected installation profile is not available locally.")
    return app_path / "docker-compose.yml", env_path


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


def _read_env_values(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value
    return values


def get_external_database_type(app_directory: str | Path) -> str:
    database_type = _read_env_values(Path(app_directory) / ".env").get("W9_DB_EXPOSE", "")
    database_type = database_type.split(",", 1)[0].strip().strip("\"'").lower()
    if database_type not in {"mysql", "postgresql"}:
        raise CustomException(400, "Invalid Request", "The application does not support an external database connection.")
    return database_type


def _merge_env_profile(base_env_path: Path, profile_env_path: Path) -> None:
    overrides = _read_env_values(profile_env_path)
    merged_lines: list[str] = []
    seen_keys: set[str] = set()

    for raw_line in base_env_path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw_line or raw_line.lstrip().startswith("#"):
            merged_lines.append(raw_line)
            continue
        key, _ = raw_line.split("=", 1)
        key = key.strip()
        if key in overrides:
            merged_lines.append(f"{key}={overrides[key]}")
            seen_keys.add(key)
        else:
            merged_lines.append(raw_line)

    for key, value in overrides.items():
        if key not in seen_keys:
            merged_lines.append(f"{key}={value}")

    base_env_path.write_text("\n".join(merged_lines) + "\n", encoding="utf-8")


def _service_named_volumes(service: dict, declared_volumes: set[str]) -> set[str]:
    named_volumes: set[str] = set()
    for volume in service.get("volumes") or []:
        source = volume.split(":", 1)[0] if isinstance(volume, str) else volume.get("source") if isinstance(volume, dict) else None
        if isinstance(source, str) and source in declared_volumes:
            named_volumes.add(source)
    return named_volumes


def _remove_external_services(compose_path: Path, excluded_services: set[str]) -> None:
    if not excluded_services:
        return

    compose = _COMPOSE_YAML.load(compose_path.read_text(encoding="utf-8")) or {}
    services = compose.get("services") or {}
    declared_volumes = set((compose.get("volumes") or {}).keys())
    removed_volumes: set[str] = set()

    for service_name in excluded_services:
        service = services.pop(service_name, None)
        if isinstance(service, dict):
            removed_volumes.update(_service_named_volumes(service, declared_volumes))

    used_volumes: set[str] = set()
    for service in services.values():
        if not isinstance(service, dict):
            continue
        depends_on = service.get("depends_on")
        if isinstance(depends_on, list):
            service["depends_on"] = [name for name in depends_on if name not in excluded_services]
            if not service["depends_on"]:
                service.pop("depends_on")
        elif isinstance(depends_on, dict):
            service["depends_on"] = {name: config for name, config in depends_on.items() if name not in excluded_services}
            if not service["depends_on"]:
                service.pop("depends_on")
        used_volumes.update(_service_named_volumes(service, declared_volumes))

    volumes = compose.get("volumes")
    if isinstance(volumes, dict):
        for volume_name in removed_volumes - used_volumes:
            volumes.pop(volume_name, None)
        if not volumes:
            compose.pop("volumes")

    _COMPOSE_YAML.dump(compose, compose_path)


def validate_profile_settings(app_directory: str | Path, profile: str | None, settings: dict | None) -> None:
    if profile is None:
        return

    app_path = Path(app_directory)
    _, env_path = get_profile_template(app_path, profile)
    expected_keys = _load_template_settings(app_path / ".env") | _load_template_settings(env_path)
    supplied_settings = settings or {}
    if set(supplied_settings) != expected_keys:
        raise CustomException(400, "Invalid Request", "Profile settings do not match the selected installation profile.")
    if any(not isinstance(value, str) for value in supplied_settings.values()):
        raise CustomException(400, "Invalid Request", "Profile settings must be strings.")


def validate_external_database_connection(database_type: str, host: str, port: int | str, database_name: str | None, username: str, password: str) -> ExternalDatabaseConnection:
    if not all(isinstance(value, str) and value.strip() for value in (host, username, password)):
        raise CustomException(400, "Invalid Request", "External database connection information is required.")
    if "://" in host or any(character.isspace() for character in host):
        raise CustomException(400, "Invalid Request", "External database host is invalid.")

    try:
        normalized_port = int(port)
    except (TypeError, ValueError) as exc:
        raise CustomException(400, "Invalid Request", "External database port is invalid.") from exc
    if normalized_port < 1 or normalized_port > 65535:
        raise CustomException(400, "Invalid Request", "External database port is invalid.")

    if database_type == "postgresql":
        return _validate_postgresql_connection(host, normalized_port, database_name or "postgres", username, password)
    if database_type != "mysql":
        raise CustomException(400, "Invalid Request", "The application does not support this external database type.")
    if not isinstance(database_name, str) or not database_name.strip():
        raise CustomException(400, "Invalid Request", "External database connection information is required.")

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
    except pymysql.MySQLError as exc:
        raise CustomException(400, "External Database Connection Failed", "Unable to connect to the specified database.") from exc

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
    _merge_env_profile(workspace_path / ".env", env_path)

    profile_values = _read_env_values(env_path)
    if profile_values.get("W9_DATABASE_MODE", "").strip().strip("\"'") == "external":
        excluded_services = {
            service.strip()
            for service in profile_values.get("W9_COMPOSE_EXCLUDE_SERVICES", "").split(",")
            if service.strip()
        }
        _remove_external_services(compose_path, excluded_services)

    profile_names = []
    for candidate in workspace_path.iterdir():
        match = _PROFILE_COMPOSE_PATTERN.fullmatch(candidate.name)
        if match and candidate.is_file():
            profile_names.append(match.group(1))
            candidate.unlink()
    if profile not in profile_names:
        profile_names.append(profile)
    for profile_name in profile_names:
        candidate = workspace_path / f".env.{profile_name}"
        if candidate.is_file():
            candidate.unlink()
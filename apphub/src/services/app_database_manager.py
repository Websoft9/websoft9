"""Resolve the database declaration of an installed application.

The application package declares *where* its database information lives
(``variables.json`` -> ``database[]``).  The values always come from the same
installation: the container environment of the declared service, its static
Compose environment and the project ``.env`` kept in the app repository.

Nothing here writes to the instance.  Unresolvable values stay ``None`` so the
caller can show "unknown" instead of a guess.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from src.core.config import ConfigManager
from src.core.logger import logger
from src.schemas.appDatabase import (
    AppDatabaseAccount,
    AppDatabaseComponent,
    AppDatabasesResponse,
    AppDatabaseTool,
)
from src.services.external_database import read_datasource
from src.services.gitea_manager import GiteaManager
from src.services.portainer_manager import PortainerManager

USAGE_VALUES = ("application", "initialization", "administration")
USAGE_SET = set(USAGE_VALUES)

_EXPANSION = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)(?:(:-|-)([^}]*))?\}|([A-Za-z_][A-Za-z0-9_]*))")

_BUNDLED_TYPES = Path(__file__).with_name("database-types.json")
_TYPES_ENV = "WEBSOFT9_DATABASE_TYPES_PATH"

_TOOLS: dict[str, list[dict[str, str]]] = {
    "mysql": [{"label": "phpMyAdmin", "app_key": "phpmyadmin"}, {"label": "CloudBeaver", "app_key": "cloudbeaver"}],
    "mariadb": [{"label": "phpMyAdmin", "app_key": "phpmyadmin"}, {"label": "CloudBeaver", "app_key": "cloudbeaver"}],
    "postgresql": [{"label": "pgAdmin", "app_key": "pgadmin"}, {"label": "CloudBeaver", "app_key": "cloudbeaver"}],
    "mongodb": [{"label": "MongoCompass", "app_key": "mongocompass"}],
    "oracle": [{"label": "CloudBeaver", "app_key": "cloudbeaver"}],
    "sqlserver": [{"label": "CloudBeaver", "app_key": "cloudbeaver"}],
    "redis": [{"label": "RedisInsight", "app_key": "redisinsight"}],
}


def parse_env_text(text: str | None) -> dict[str, str]:
    """Parse dotenv content, keeping the raw (unexpanded) values."""
    values: dict[str, str] = {}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def expand_value(
    expression: str, values: dict[str, str], stack: frozenset[str] = frozenset(), strict: bool = True
) -> tuple[str, bool]:
    """Expand ``${VAR}`` / ``${VAR:-default}`` / ``$VAR`` against ``values``.

    Returns the expanded text and whether a *top level* reference could not be
    resolved.  Nested references are expanded once more (templates write
    ``W9_LOGIN_PASSWORD=${W9_POWER_PASSWORD}``) but an unknown name inside an
    already resolved value is kept literally, so passwords that contain a ``$``
    are not silently truncated.  A doubled ``$$`` is a literal dollar sign.
    """
    missing = False

    def replace(match: re.Match[str]) -> str:
        nonlocal missing
        name = match.group(1) or match.group(4) or ""
        operator = match.group(2)
        default = match.group(3) or ""
        if name and name not in stack and name in values:
            text, _ = expand_value(values[name] or "", values, stack | {name}, strict=False)
            return text
        if operator is not None:
            return default
        if strict:
            missing = True
            return ""
        return match.group(0)

    protected = expression.replace("$$", "\x00")
    expanded = _EXPANSION.sub(replace, protected)
    return expanded.replace("\x00", "$"), missing


class EnvironmentResolver:
    """Resolve declaration references against one instance.

    Lookup order follows the contract: the service's effective environment
    (container value first, then Compose ``environment``, then ``env_file``),
    and finally the project ``.env`` for values that Compose interpolates away.
    Other services are never scanned.
    """

    def __init__(self, project_env: dict[str, str], compose_env: dict[str, str], container_env: dict[str, str]):
        self._project_env = project_env
        self._compose_env = compose_env
        self._container_env = container_env

    @property
    def merged(self) -> dict[str, str]:
        merged = dict(self._project_env)
        merged.update(self._compose_env)
        merged.update(self._container_env)
        return merged

    def resolve(self, expression: str) -> str | None:
        value, missing = expand_value(expression, self.merged)
        if missing:
            return None
        value = value.strip()
        return value or None


class ContainerProbe:
    """Read the stack containers once and only the env of declared services."""

    def __init__(self, app_id: str, endpoint_id: int | None = None):
        self._app_id = app_id
        self._endpoint_id = endpoint_id
        self._containers: list[dict[str, Any]] | None = None
        self._env: dict[str, dict[str, str]] = {}

    def _stack_containers(self) -> list[dict[str, Any]]:
        if self._containers is not None:
            return self._containers
        try:
            portainer = PortainerManager()
            endpoint = self._endpoint_id if self._endpoint_id is not None else portainer.get_local_endpoint_id()
            self._containers = portainer.get_containers_by_stack_name(self._app_id, endpoint) or []
            self._endpoint = endpoint
        except Exception as exc:
            logger.warning(f"Failed to list containers for {self._app_id}: {exc}")
            self._containers = []
        return self._containers

    def env_for(self, service: str | None) -> dict[str, str]:
        if not service:
            return {}
        if service in self._env:
            return self._env[service]
        resolved: dict[str, str] = {}
        container = self._container_for(service)
        if container is not None and container.get("Id"):
            try:
                info = PortainerManager().get_container_by_id(getattr(self, "_endpoint", 0), container["Id"])
                for entry in (info.get("Config") or {}).get("Env") or []:
                    if isinstance(entry, str) and "=" in entry:
                        key, value = entry.split("=", 1)
                        resolved[key.strip()] = value
            except Exception as exc:
                logger.warning(f"Failed to read container env for {self._app_id}/{service}: {exc}")
                resolved = {}
        self._env[service] = resolved
        return resolved

    def name_for(self, service: str | None) -> str | None:
        """Actual container name of a declared service, when it is running.

        A compose service name repeats across applications (`mysql`, `db`),
        so the panel shows the container name instead.
        """
        container = self._container_for(service)
        names = (container or {}).get("Names") or []
        for name in names:
            if isinstance(name, str) and name.strip():
                return name.strip().lstrip("/")
        return None

    def _container_for(self, service: str | None) -> dict[str, Any] | None:
        if not service:
            return None
        matched = [
            container
            for container in self._stack_containers()
            if (container.get("Labels") or {}).get("com.docker.compose.service") == service
        ]
        return matched[0] if len(matched) == 1 else None


class AppDatabaseManager:
    """Read ``database[]`` from the app repository and resolve it for display."""

    def get_databases(self, app_id: str, endpoint_id: int | None = None) -> AppDatabasesResponse:
        variables = self._read_variables(app_id)
        declaration, mode = self._extract_declaration(variables)
        if mode != "v2":
            return AppDatabasesResponse(app_id=app_id, declaration=mode, components=[])

        project_env = self._project_env(app_id)
        external_active = (project_env.get("W9_DATABASE_MODE") or "").strip().lower() == "external"
        dictionary = self._type_dictionary()
        compose_services = self._compose_services(app_id)
        probe = ContainerProbe(app_id, endpoint_id)

        components: list[AppDatabaseComponent] = []
        for item in declaration:
            component = self._resolve_component(
                app_id=app_id,
                raw=item,
                dictionary=dictionary,
                compose_services=compose_services,
                project_env=project_env,
                external_active=external_active,
                probe=probe,
            )
            if component is not None:
                components.append(component)

        return AppDatabasesResponse(
            app_id=app_id,
            declaration="v2",
            external_active=external_active,
            components=components,
        )

    # ── declaration ──────────────────────────────────────────────────────

    def _read_variables(self, app_id: str) -> dict[str, Any] | None:
        try:
            raw = GiteaManager().get_file_raw_from_repo(app_id, "variables.json")
        except Exception as exc:  # pragma: no cover - transport failures only
            logger.warning(f"Failed to read variables.json for {app_id}: {exc}")
            return None
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(f"variables.json of {app_id} is not valid JSON: {exc}")
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _extract_declaration(variables: dict[str, Any] | None) -> tuple[list[dict[str, Any]], str]:
        if not variables or "database" not in variables:
            return [], "missing"
        raw = variables.get("database")
        if isinstance(raw, list):
            components = [item for item in raw if isinstance(item, dict)]
            return components, "v2" if components else "missing"
        if isinstance(raw, dict):
            return [], "legacy"
        return [], "missing"

    # ── instance configuration ───────────────────────────────────────────

    def _project_env(self, app_id: str) -> dict[str, str]:
        try:
            return parse_env_text(GiteaManager().get_file_raw_from_repo(app_id, ".env"))
        except Exception as exc:  # pragma: no cover - transport failures only
            logger.warning(f"Failed to read .env for {app_id}: {exc}")
            return {}

    def _repo_file(self, app_id: str, path: str) -> str:
        try:
            return GiteaManager().get_file_raw_from_repo(app_id, path) or ""
        except Exception:
            return ""

    def _compose_services(self, app_id: str) -> dict[str, Any]:
        for name in ("docker-compose.yml", "docker-compose.yaml"):
            try:
                raw = GiteaManager().get_file_raw_from_repo(app_id, name)
            except Exception:  # pragma: no cover - transport failures only
                continue
            if not raw:
                continue
            try:
                document = yaml.safe_load(raw) or {}
            except yaml.YAMLError as exc:
                logger.warning(f"{name} of {app_id} is not valid YAML: {exc}")
                return {}
            services = document.get("services") if isinstance(document, dict) else None
            return services if isinstance(services, dict) else {}
        return {}

    def _compose_env(self, app_id: str, services: dict[str, Any], service: str | None) -> dict[str, str]:
        """Merge the service's ``env_file`` entries and its ``environment``."""
        if not service:
            return {}
        definition = services.get(service)
        if not isinstance(definition, dict):
            return {}

        env: dict[str, str] = {}
        env_files = definition.get("env_file")
        if isinstance(env_files, (str, dict)):
            env_files = [env_files]
        for entry in env_files or []:
            path = entry.get("path") if isinstance(entry, dict) else entry
            if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
                continue
            env.update(parse_env_text(self._repo_file(app_id, path)))

        environment = definition.get("environment")
        if isinstance(environment, dict):
            for key, value in environment.items():
                env[str(key)] = "" if value is None else str(value)
        elif isinstance(environment, list):
            for item in environment:
                if not isinstance(item, str):
                    continue
                key, _, value = item.partition("=")
                env[key.strip()] = value
        return env

    # ── type dictionary ──────────────────────────────────────────────────

    def _type_dictionary(self) -> dict[str, Any]:
        for candidate in self._type_dictionary_candidates():
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                return payload
        logger.warning("Database type dictionary is unavailable; only declared fields will be shown")
        return {}

    @staticmethod
    def _type_dictionary_candidates() -> list[Path]:
        candidates: list[Path] = []
        override = os.getenv(_TYPES_ENV)
        if override:
            candidates.append(Path(override))
        try:
            library_path = ConfigManager("system.ini").get_value("docker_library", "path")
            candidates.append(Path(library_path).parent / "metadata" / "database-types.json")
        except Exception:
            pass
        candidates.append(_BUNDLED_TYPES)
        return candidates

    # ── components ───────────────────────────────────────────────────────

    def _resolve_component(
        self,
        *,
        app_id: str,
        raw: dict[str, Any],
        dictionary: dict[str, Any],
        compose_services: dict[str, Any],
        project_env: dict[str, str],
        external_active: bool,
        probe: ContainerProbe,
    ) -> AppDatabaseComponent | None:
        component_id = str(raw.get("id") or "").strip()
        providers = [item for item in raw.get("providers") or [] if isinstance(item, dict)]
        if not component_id or not providers:
            return None

        internal = next((item for item in providers if item.get("type") == "internal"), None)
        has_external = any(item.get("type") == "external" for item in providers)
        service = str(internal.get("service") or "").strip() if internal else ""

        driver = ""
        if internal:
            driver = str(internal.get("driver") or "").strip()
        if not driver:
            external = next((item for item in providers if item.get("type") == "external"), None)
            drivers = (external or {}).get("drivers") or []
            driver = str(drivers[0]).strip() if drivers else ""

        if has_external and external_active:
            return _resolve_external_component(
                raw=raw, component_id=component_id, driver=driver, service=service, project_env=project_env
            )
        if internal is None:
            # External-only component that the instance has not configured yet.
            return None

        declared_type = dictionary.get(driver) if driver else None
        type_definition: dict[str, Any] = declared_type if isinstance(declared_type, dict) else {}
        resolver = EnvironmentResolver(
            project_env=project_env,
            compose_env=self._compose_env(app_id, compose_services, service or None),
            container_env=probe.env_for(service or None),
        )

        unknown_fields: list[str] = []
        names = _resolve_names(raw, type_definition, resolver)
        accounts, auth = _resolve_accounts(raw, type_definition, resolver)

        port = type_definition.get("port")
        if not isinstance(port, int):
            port = None
            unknown_fields.append("port")

        host = probe.name_for(service or None)
        if not host:
            # A stopped app has no container, so fall back to the name the
            # template pins for it (`container_name: ${W9_ID}-<service>`).
            host = _compose_container_name(compose_services, service or None, resolver.merged)
        if not host:
            unknown_fields.append("host")

        return AppDatabaseComponent(
            id=component_id,
            driver=driver or "unknown",
            service=service or None,
            mode="internal",
            host=host,
            port=port,
            port_from_dictionary=True,
            names=names,
            accounts=accounts,
            auth=auth,
            unknown_fields=unknown_fields,
            tools=_tools_for(driver),
        )


def _tools_for(driver: str) -> list[AppDatabaseTool]:
    return [AppDatabaseTool(label=item["label"], app_key=item["app_key"]) for item in _TOOLS.get(driver, [])]


def _resolve_external_component(
    *,
    raw: dict[str, Any],
    component_id: str,
    driver: str,
    service: str,
    project_env: dict[str, str],
) -> AppDatabaseComponent:
    """Read the connection an external installation actually uses.

    The declaration says *where* the values went (``datasource``), so they are
    reversed out of the instance configuration. Instances installed before the
    declaration existed stored the same connection under platform-owned keys,
    which are used as a fallback instead of being reported as unknown.
    """
    datasource = raw.get("datasource")
    mapped = read_datasource(datasource, project_env) if isinstance(datasource, dict) else {}

    def value(semantic: str, legacy_key: str) -> str:
        return (mapped.get(semantic) or "").strip() or (project_env.get(legacy_key) or "").strip()

    host = value("host", "W9_DB_HOST_SET")
    raw_port = value("port", "W9_DB_PORT_SET")
    name = value("name", "W9_DB_NAME_SET")
    user = value("user", "W9_DB_USER_SET")
    password = value("password", "W9_DB_PASSWORD_SET")

    unknown_fields: list[str] = []
    port: int | None = None
    if raw_port.isdigit():
        port = int(raw_port)
    else:
        unknown_fields.append("port")
    if not host:
        unknown_fields.append("host")

    accounts: list[AppDatabaseAccount] = []
    auth = "unknown"
    if user:
        accounts.append(AppDatabaseAccount(user=user, usage=[], password=password or None))
        auth = "password" if password else "unknown"

    return AppDatabaseComponent(
        id=component_id,
        driver=driver or "unknown",
        service=service or None,
        mode="external",
        host=host or None,
        port=port,
        port_from_dictionary=False,
        names=[name] if name else [],
        accounts=accounts,
        auth=auth,
        unknown_fields=unknown_fields,
        tools=_tools_for(driver),
    )


def _compose_container_name(services: dict[str, Any], service: str | None, values: dict[str, str]) -> str | None:
    """Read ``container_name`` of a service, interpolated like Compose would."""
    if not service:
        return None
    definition = services.get(service)
    if not isinstance(definition, dict):
        return None
    declared = definition.get("container_name")
    if not isinstance(declared, str) or not declared.strip():
        return None
    expanded, missing = expand_value(declared, values)
    expanded = expanded.strip()
    return None if missing or not expanded else expanded


def _declared(raw: dict[str, Any], key: str, fallback: Any) -> Any:
    """Inheritance is per field: a declared field replaces the dictionary one."""
    return raw[key] if key in raw else fallback


def _resolve_names(raw: dict[str, Any], type_definition: dict[str, Any], resolver: EnvironmentResolver) -> list[str]:
    declared = _declared(raw, "name", type_definition.get("name") or [])
    names: list[str] = []
    for item in declared or []:
        if not isinstance(item, str):
            continue
        value = resolver.resolve(item)
        if value and value not in names:
            names.append(value)
    return names


def _resolve_accounts(
    raw: dict[str, Any], type_definition: dict[str, Any], resolver: EnvironmentResolver
) -> tuple[list[AppDatabaseAccount], str]:
    declared = _declared(raw, "users", type_definition.get("users") or [])
    accounts: list[AppDatabaseAccount] = []
    for item in declared or []:
        if not isinstance(item, dict):
            continue
        user = resolver.resolve(str(item.get("user") or ""))
        if not user:
            continue
        password: str | None = None
        raw_password = item.get("password")
        if isinstance(raw_password, str) and raw_password:
            password = resolver.resolve(raw_password)
        usage = [value for value in item.get("usage") or [] if isinstance(value, str) and value in USAGE_SET]
        accounts.append(AppDatabaseAccount(user=user, usage=usage, password=password))

    if not declared:
        return [], "none"
    if not accounts:
        # The declaration asks for accounts but none of their sources resolve.
        # That is "unknown", not "no authentication".
        return [], "unknown"
    if any(account.password for account in accounts):
        return accounts, "password"
    return accounts, "unknown"

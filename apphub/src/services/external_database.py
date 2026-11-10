"""External database support declared by ``database[]`` in an app repository.

The library used to express "this application can connect to an external
database" through a ``.env.external-db`` installation profile. That file is being
retired in favour of the ``database[]`` declaration, which already carries the
three facts the platform needs:

* ``providers[].type == "external"`` and ``providers[].drivers`` - supported
  engines,
* ``providers[].internal.service`` - the bundled service to drop,
* ``datasource`` - the native application variables that receive the connection.

Both shapes stay supported: a profile file wins when present (old library), and
the declaration is used when it is absent (new library). Everything here is pure
parsing so it can be tested without a docker runtime.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

EXTERNAL_DATABASE_PROFILE = "external-db"
# Only applications whose external database installation has been verified end
# to end may publish the profile. Adding a key here requires validating its
# ``datasource`` mapping and bundled-service removal first.
EXTERNAL_DATABASE_ALLOWED_APPS = frozenset({"wordpress", "odoo"})
EXTERNAL_DATABASE_CONNECTION_SETTING_KEYS = (
    "W9_DB_HOST_SET",
    "W9_DB_PORT_SET",
    "W9_DB_NAME_SET",
    "W9_DB_USER_SET",
    "W9_DB_PASSWORD_SET",
)

# Only engines the platform can validate a connection for. Mirrors the guards in
# ``validate_external_database_connection`` and keeps the list in one place.
SUPPORTED_EXTERNAL_DRIVERS = ("mysql", "mariadb", "postgresql")

DEFAULT_DRIVER_PORTS = {"mysql": 3306, "mariadb": 3306, "postgresql": 5432}

_PLACEHOLDER_SEMANTICS = {
    "${host}": "host",
    "${port}": "port",
    "${name}": "name",
    "${users[*].user}": "user",
    "${users[*].password}": "password",
}
_UNRESOLVED_PLACEHOLDER = re.compile(r"\$\{[^}]+\}")


def _read_variables(app_directory: str | Path) -> dict[str, Any] | None:
    try:
        raw = (Path(app_directory) / "variables.json").read_text(encoding="utf-8")
        variables = json.loads(raw)
    except (OSError, ValueError):
        return None
    return variables if isinstance(variables, dict) else None


def external_database_allowed(app_directory: str | Path | None) -> bool:
    """Whether this application may offer an external database installation."""
    if app_directory is None:
        return False
    return Path(app_directory).name.strip().lower() in EXTERNAL_DATABASE_ALLOWED_APPS


def filter_external_database_profiles(apps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove ``external-db`` from unverified applications before they reach the console.

    The catalog keeps the capability declaration for every application; this
    policy is applied only when the platform serves it. Copying the entries
    keeps a cached catalog reusable across requests.
    """
    filtered: list[dict[str, Any]] = []
    for app in apps:
        key = app.get("key")
        profiles = app.get("profiles")
        if (
            (isinstance(key, str) and key.strip().lower() in EXTERNAL_DATABASE_ALLOWED_APPS)
            or not isinstance(profiles, dict)
            or EXTERNAL_DATABASE_PROFILE not in profiles
        ):
            filtered.append(app)
            continue

        remaining = {name: value for name, value in profiles.items() if name != EXTERNAL_DATABASE_PROFILE}
        copy = dict(app)
        if remaining:
            copy["profiles"] = remaining
        else:
            copy.pop("profiles", None)
        filtered.append(copy)
    return filtered


def external_database_declaration(app_directory: str | Path) -> dict[str, Any] | None:
    """Return the declaration found in an application directory."""
    return external_database_declaration_from_variables(_read_variables(app_directory))


def external_database_declaration_from_variables(variables: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the first component that declares a writable external provider.

    A component only counts when it also declares ``datasource``: the contract
    marks that field required for external support, and without it the platform
    has nowhere to write the connection. Components that merely list
    ``external.drivers`` (optional runtime scaffolds) are therefore ignored.

    Parsed ``variables.json`` payloads are accepted directly so callers holding
    a repository document do not need a working tree.
    """
    if not isinstance(variables, dict):
        return None

    for component in variables.get("database") or []:
        if not isinstance(component, dict):
            continue
        providers = [item for item in component.get("providers") or [] if isinstance(item, dict)]
        external = next((item for item in providers if item.get("type") == "external"), None)
        if external is None:
            continue
        datasource = component.get("datasource")
        if not isinstance(datasource, dict) or not datasource:
            continue
        drivers = [item.strip().lower() for item in external.get("drivers") or [] if isinstance(item, str) and item.strip()]
        drivers = [item for item in drivers if item in SUPPORTED_EXTERNAL_DRIVERS]
        if not drivers:
            continue
        services = [
            item["service"].strip()
            for item in providers
            if item.get("type") == "internal" and isinstance(item.get("service"), str) and item["service"].strip()
        ]
        return {
            "id": str(component.get("id") or "database"),
            "drivers": drivers,
            "internal_services": services,
            "datasource": {key: value for key, value in datasource.items() if isinstance(key, str) and isinstance(value, str)},
        }
    return None


def external_database_profile_settings(declaration: dict[str, Any] | None) -> dict[str, str]:
    """Form defaults for a profile synthesised from a declaration."""
    settings = {key: "" for key in EXTERNAL_DATABASE_CONNECTION_SETTING_KEYS}
    drivers = (declaration or {}).get("drivers") or []
    port = DEFAULT_DRIVER_PORTS.get(str(drivers[0]), "") if drivers else ""
    settings["W9_DB_PORT_SET"] = str(port)
    return settings


def apply_datasource(datasource: dict[str, str], values: dict[str, str]) -> dict[str, str]:
    """Render ``datasource`` targets from semantic connection values.

    Returns only fully resolved targets: a template that still contains a
    placeholder after substitution is dropped so a half-written connection is
    never produced (``${url}`` needs a driver template the caller may not have).
    """
    rendered: dict[str, str] = {}
    for target, template in datasource.items():
        if not isinstance(target, str) or not isinstance(template, str) or not target.strip():
            continue
        resolved = template
        for placeholder, semantic in _PLACEHOLDER_SEMANTICS.items():
            if placeholder in resolved:
                resolved = resolved.replace(placeholder, str(values.get(semantic) or ""))
        if _UNRESOLVED_PLACEHOLDER.search(resolved) or not resolved.strip():
            continue
        rendered[target.strip()] = resolved
    return rendered


def read_datasource(datasource: dict[str, str], env: dict[str, str]) -> dict[str, str]:
    """Reverse the ``datasource`` mapping against an instance configuration.

    Only the shapes the contract allows are understood. Anything else is left
    out rather than guessed, matching the "unknown stays unknown" rule the rest
    of the database panel follows.
    """
    values: dict[str, str] = {}
    for target, template in datasource.items():
        configured = (env.get(target) or "").strip()
        if not configured:
            continue
        semantics = [semantic for placeholder, semantic in _PLACEHOLDER_SEMANTICS.items() if placeholder in template]
        if semantics == ["host", "port"]:
            host, _, port = configured.rpartition(":")
            if host and port.isdigit():
                values.setdefault("host", host)
                values.setdefault("port", port)
            else:
                values.setdefault("host", configured)
        elif semantics == ["host"]:
            values.setdefault("host", configured)
        elif semantics == ["port"]:
            values.setdefault("port", configured)
        elif semantics == ["name"]:
            values.setdefault("name", configured)
        elif semantics == ["user"]:
            values.setdefault("user", configured)
        elif semantics == ["password"]:
            values.setdefault("password", configured)
    return values

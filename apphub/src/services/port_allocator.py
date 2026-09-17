"""Host port suggestion and availability checks for app installation."""

from __future__ import annotations

import configparser
import re

import docker

from src.core.logger import logger
from src.core.runtime_paths import resolve_apphub_config_path
from src.services.app_status import appInstalling


DEFAULT_PORT_RANGE = (9001, 9999)
DEFAULT_PORT_RANGE_VALUE = "9001-9999"
_PORT_RANGE_PATTERN = re.compile(r"^\s*(\d{1,5})\s*-\s*(\d{1,5})\s*$")


def read_port_range() -> tuple[int, int]:
    """Read the configurable host port range from config.ini, falling back to the default."""
    try:
        config = configparser.ConfigParser()
        config.read(resolve_apphub_config_path("config.ini"), encoding="utf-8")
        raw_value = config.get("port_allocation", "range", fallback="")
        match = _PORT_RANGE_PATTERN.match(raw_value or "")
        if match:
            minimum, maximum = int(match.group(1)), int(match.group(2))
            if 1 <= minimum <= maximum <= 65535:
                return minimum, maximum
            logger.warning(f"Configured port range is out of bounds: {raw_value}")
    except Exception as exc:
        logger.warning(f"Could not read the configured port range: {exc}")

    return DEFAULT_PORT_RANGE


def _container_port_sources() -> dict[int, str]:
    """Host ports configured by any container, including stopped ones.

    Stopped applications keep their port bindings, so their ports must not be
    handed out to another application even while they are not running.
    """
    sources: dict[int, str] = {}
    try:
        client = docker.from_env()
        for container in client.containers.list(all=True):
            bindings = (container.attrs.get("HostConfig") or {}).get("PortBindings") or {}
            for rules in bindings.values():
                if not rules:
                    continue
                for rule in rules:
                    host_port = rule.get("HostPort")
                    if host_port and str(host_port).isdigit():
                        sources[int(host_port)] = "container"
    except Exception as exc:
        logger.warning(f"Could not scan container port bindings: {exc}")
    return sources


def _installing_port_sources() -> dict[int, str]:
    """Ports reserved by applications that are currently being installed."""
    sources: dict[int, str] = {}
    try:
        for entry in appInstalling.values():
            for port in entry.get("reserved_ports") or set():
                try:
                    sources[int(port)] = "installing"
                except (TypeError, ValueError):
                    continue
    except Exception as exc:
        logger.warning(f"Could not scan installing app ports: {exc}")
    return sources


def collect_port_sources() -> dict[int, str]:
    """Return the host ports that are not available, mapped to the claiming source."""
    return {**_container_port_sources(), **_installing_port_sources()}


def suggest_ports(keys: list[str]) -> list[dict]:
    """Assign one free host port per install setting key, in the given order.

    Every port comes from the configured range: template defaults are ignored
    so install forms never suggest ports that fall outside the range. Ports
    already claimed (containers, installing apps) or assigned earlier in this
    batch are skipped. When the range is exhausted the suggested port is None
    so the UI can ask the operator for a manual value.
    """
    minimum, maximum = read_port_range()
    used = set(collect_port_sources())
    assigned: set[int] = set()
    suggestions: list[dict] = []

    for key in keys:
        suggested: int | None = None
        for candidate in range(minimum, maximum + 1):
            if candidate not in used and candidate not in assigned:
                suggested = candidate
                break
        if suggested is not None:
            assigned.add(suggested)
        suggestions.append(
            {
                "key": key,
                "port": suggested,
            }
        )

    return suggestions


def check_ports(ports: list[int]) -> list[dict]:
    """Check whether each host port is currently free."""
    sources = collect_port_sources()
    results: list[dict] = []
    for port in ports:
        reason = sources.get(port)
        results.append(
            {
                "port": port,
                "available": reason is None,
                "reason": reason,
            }
        )
    return results

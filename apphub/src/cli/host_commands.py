from __future__ import annotations

import re
from typing import Any

import click

from src.cli.cli_output import CLIError, run_cli_action


_PORT_RANGE_PATTERN = re.compile(r"^\s*(\d{1,5})\s*-\s*(\d{1,5})\s*$")


@click.group(name="host")
def host_group():
    """Inspect port availability, local environment, and SSH profile metadata.

    This is not a general-purpose remote host administration interface.
    """


@host_group.group(name="ports")
def host_ports_group():
    """Check and suggest available host ports."""


def _parse_port_tokens(tokens: tuple[str, ...]) -> list[int]:
    ports: list[int] = []
    seen: set[int] = set()
    for raw_token in tokens:
        for part in str(raw_token).split(","):
            piece = part.strip()
            if not piece:
                continue
            range_match = _PORT_RANGE_PATTERN.match(piece)
            if range_match:
                start_port, end_port = int(range_match.group(1)), int(range_match.group(2))
                if not (1 <= start_port <= end_port <= 65535):
                    raise CLIError("INVALID_ARGUMENT", f"Invalid port range '{piece}'", exit_code=2)
                if end_port - start_port > 200:
                    raise CLIError("INVALID_ARGUMENT", f"Port range '{piece}' exceeds 200 ports", exit_code=2)
                for candidate in range(start_port, end_port + 1):
                    if candidate not in seen:
                        seen.add(candidate)
                        ports.append(candidate)
                continue
            if not piece.isdigit():
                raise CLIError("INVALID_ARGUMENT", f"Invalid port value '{piece}'", exit_code=2)
            port = int(piece)
            if not (1 <= port <= 65535):
                raise CLIError("INVALID_ARGUMENT", f"Port '{port}' must be between 1 and 65535", exit_code=2)
            if port not in seen:
                seen.add(port)
                ports.append(port)
    if not ports:
        raise CLIError("INVALID_ARGUMENT", "At least one port is required", exit_code=2)
    return ports


@host_ports_group.command(name="check")
@click.argument("ports", nargs=-1, required=True)
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def check_ports_command(ports: tuple[str, ...], as_json: bool) -> None:
    """Check whether one or more host ports are free."""
    def action() -> dict[str, Any]:
        from src.services.port_allocator import check_ports, read_port_range

        parsed_ports = _parse_port_tokens(ports)
        items = check_ports(parsed_ports)
        min_port, max_port = read_port_range()
        return {
            "items": items,
            "all_available": all(bool(item.get("available")) for item in items),
            "configured_range": {"min": min_port, "max": max_port},
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        lines = []
        for item in items:
            state = "available" if item.get("available") else f"used ({item.get('reason') or 'occupied'})"
            lines.append(f"- {item.get('port')}: {state}")
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@host_ports_group.command(name="suggest")
@click.option("--key", "keys", multiple=True, help="Setting key to allocate a free port for (repeatable).")
@click.option("--count", type=click.IntRange(min=1, max=50), default=1, show_default=True, help="Number of ports to suggest when --key is omitted.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def suggest_ports_command(keys: tuple[str, ...], count: int, as_json: bool) -> None:
    """Suggest free host ports from the configured port range."""
    def action() -> dict[str, Any]:
        from src.services.port_allocator import read_port_range, suggest_ports

        requested_keys = [item.strip() for item in keys if item and item.strip()]
        if not requested_keys:
            if count == 1:
                requested_keys = ["W9_HTTP_PORT_SET"]
            else:
                requested_keys = [f"PORT_{index + 1}" for index in range(count)]
        suggestions = suggest_ports(requested_keys)
        min_port, max_port = read_port_range()
        return {
            "items": suggestions,
            "configured_range": {"min": min_port, "max": max_port},
            "exhausted": any(item.get("port") is None for item in suggestions),
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        return "\n".join(f"- {item.get('key')}: {item.get('port') if item.get('port') is not None else 'exhausted'}" for item in items)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@host_group.command(name="env-check")
@click.option("--path", "check_path", default="/", show_default=True, help="Filesystem path to check disk and inode capacity on.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def host_env_check_command(check_path: str, as_json: bool) -> None:
    """Inspect swap, inode usage, DNS, and kernel parameters in the CLI environment.

    When run in a container, these checks reflect its visible environment, not
    a complete inspection of a remote host.
    """
    def action() -> dict[str, Any]:
        import os
        import shutil
        from pathlib import Path

        checks: dict[str, Any] = {}
        warnings: list[str] = []

        # 1. Swap & memory from /proc/meminfo
        meminfo: dict[str, int] = {}
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if ":" not in line:
                    continue
                k, _, v = line.partition(":")
                parts = v.strip().split()
                if parts and parts[0].isdigit():
                    meminfo[k.strip()] = int(parts[0]) * 1024
        except OSError:
            pass
        swap_total = meminfo.get("SwapTotal", 0)
        swap_free = meminfo.get("SwapFree", 0)
        checks["swap"] = {
            "total_bytes": swap_total,
            "free_bytes": swap_free,
            "used_bytes": max(swap_total - swap_free, 0),
            "enabled": swap_total > 0,
        }
        if swap_total == 0:
            warnings.append("Swap is not enabled (SwapTotal=0).")

        # 2. Disk & Inode capacity
        try:
            usage = shutil.disk_usage(check_path)
            vfs = os.statvfs(check_path)
            inodes_total = int(vfs.f_files)
            inodes_free = int(vfs.f_favail)
            inodes_used = max(inodes_total - inodes_free, 0)
            inode_pct = round((inodes_used / inodes_total) * 100, 1) if inodes_total > 0 else None
            checks["filesystem"] = {
                "path": check_path,
                "disk_total_bytes": usage.total,
                "disk_free_bytes": usage.free,
                "inodes_total": inodes_total,
                "inodes_free": inodes_free,
                "inodes_used_percent": inode_pct,
            }
            if inode_pct is not None and inode_pct >= 90:
                warnings.append(f"High inode utilization on {check_path}: {inode_pct}%.")
        except OSError as exc:
            checks["filesystem"] = {"path": check_path, "error": str(exc)}

        # 3. Kernel vm.max_map_count
        max_map_count: int | None = None
        try:
            raw_mmc = Path("/proc/sys/vm/max_map_count").read_text(encoding="utf-8").strip()
            if raw_mmc.isdigit():
                max_map_count = int(raw_mmc)
        except OSError:
            pass
        checks["kernel"] = {
            "vm_max_map_count": max_map_count,
        }
        if max_map_count is not None and max_map_count < 262144:
            warnings.append(f"vm.max_map_count is {max_map_count} (< 262144 recommended for Elasticsearch/SonarQube).")

        # 4. DNS nameservers
        nameservers: list[str] = []
        try:
            for line in Path("/etc/resolv.conf").read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("nameserver "):
                    parts = stripped.split()
                    if len(parts) >= 2:
                        nameservers.append(parts[1])
        except OSError:
            pass
        checks["dns"] = {
            "nameservers": nameservers,
            "configured": len(nameservers) > 0,
        }
        if not nameservers:
            warnings.append("No DNS nameservers found in /etc/resolv.conf.")

        return {
            "checks": checks,
            "warnings": warnings,
        }

    def render_text(payload: dict[str, Any]) -> str:
        checks = payload.get("checks") or {}
        swap = checks.get("swap") or {}
        fs = checks.get("filesystem") or {}
        kernel = checks.get("kernel") or {}
        dns = checks.get("dns") or {}
        return (
            f"Swap: enabled={swap.get('enabled')} total={swap.get('total_bytes')}B\n"
            f"Filesystem ({fs.get('path')}): disk_free={fs.get('disk_free_bytes')}B inodes_used={fs.get('inodes_used_percent')}%\n"
            f"Kernel: vm.max_map_count={kernel.get('vm_max_map_count')}\n"
            f"DNS: nameservers={', '.join(dns.get('nameservers') or []) or 'none'}"
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@host_group.group(name="ssh-profiles")
def host_ssh_profiles_group():
    """Inspect saved SSH host connection profile metadata (credentials masked)."""


@host_ssh_profiles_group.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_ssh_profiles_command(as_json: bool) -> None:
    """List saved SSH host connection profiles without exposing secrets."""
    def action() -> dict[str, Any]:
        import json as _json
        import sqlite3
        from src.services.host_access import HostAccessService

        service = HostAccessService()
        if not service.database_file.is_file():
            return {"items": [], "total": 0}

        items: list[dict[str, Any]] = []
        uri = f"{service.database_file.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT profile_id, operator_id, is_default, payload, updated_at FROM host_profiles ORDER BY is_default DESC, updated_at DESC"
            ).fetchall()
            for row in rows:
                try:
                    payload = _json.loads(row["payload"] or "{}")
                except Exception:
                    payload = {}
                items.append(
                    {
                        "profile_id": row["profile_id"],
                        "operator_id": row["operator_id"],
                        "is_default": bool(row["is_default"]),
                        "host": payload.get("host"),
                        "port": payload.get("port"),
                        "username": payload.get("username"),
                        "auth_method": payload.get("auth_method"),
                        "has_password": bool(payload.get("password")),
                        "has_private_key": bool(payload.get("private_key")),
                        "updated_at": row["updated_at"],
                    }
                )
        return {"items": items, "total": len(items)}

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No saved SSH profiles found."
        return "\n".join(
            f"- {item.get('profile_id')}: {item.get('username')}@{item.get('host')}:{item.get('port')} "
            f"(auth={item.get('auth_method')}, default={item.get('is_default')})"
            for item in items
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)

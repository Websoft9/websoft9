from __future__ import annotations

import re
import time
from typing import Any

import click

from src.cli.cli_output import CLIError, MAX_TEXT_BUDGET_BYTES, mask_sensitive_text, run_cli_action, truncate_utf8_text


_DURATION_PATTERN = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_DURATION_MULTIPLIERS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}


@click.group(name="docker")
def docker_group():
    """Inspect Docker containers and resources managed through Portainer."""


@docker_group.group(name="container")
def docker_container_group():
    """List, inspect, and read logs of Docker containers."""


def _resolve_endpoint_id(portainer_manager: Any, endpoint_id: int | None) -> int:
    if endpoint_id is not None:
        from src.services.common_check import check_endpointId

        check_endpointId(endpoint_id, portainer_manager)
        return endpoint_id
    return int(portainer_manager.get_local_endpoint_id())


def _parse_since_timestamp(since: str | None) -> int | None:
    if not since:
        return None
    match = _DURATION_PATTERN.match(since)
    if not match:
        raise CLIError("INVALID_ARGUMENT", f"Invalid --since duration '{since}'; expected <number><s|m|h|d>", exit_code=2)
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if amount <= 0:
        raise CLIError("INVALID_ARGUMENT", "--since duration must be positive", exit_code=2)
    return max(int(time.time()) - amount * _DURATION_MULTIPLIERS[unit], 0)


def _find_exact_container(containers: list[dict[str, Any]], target: str) -> dict[str, Any] | None:
    normalized = str(target or "").strip()
    if not normalized:
        return None
    normalized_name = f"/{normalized.lstrip('/')}"
    for container in containers:
        if not isinstance(container, dict):
            continue
        container_id = str(container.get("Id") or "")
        names = container.get("Names") or []
        if container_id == normalized or (isinstance(names, list) and normalized_name in names):
            return container
    return None


def _summarize_container_list_item(container: dict[str, Any]) -> dict[str, Any]:
    names = container.get("Names") or []
    name = str(names[0]).lstrip("/") if isinstance(names, list) and names else str(container.get("Name") or "").lstrip("/") or None
    labels = container.get("Labels") or {}
    return {
        "id": container.get("Id"),
        "name": name,
        "image": container.get("Image"),
        "state": container.get("State"),
        "status": container.get("Status"),
        "project": labels.get("com.docker.compose.project") if isinstance(labels, dict) else None,
    }


def _summarize_container_inspect(raw_info: dict[str, Any], endpoint_id: int) -> dict[str, Any]:
    state_obj = raw_info.get("State") or {}
    health_obj = state_obj.get("Health") or {}
    network_settings = raw_info.get("NetworkSettings") or {}
    networks_obj = network_settings.get("Networks") or {}
    mounts_raw = raw_info.get("Mounts") or []

    networks = []
    if isinstance(networks_obj, dict):
        for net_name, net_data in sorted(networks_obj.items()):
            if isinstance(net_data, dict):
                networks.append(
                    {
                        "name": net_name,
                        "ip_address": net_data.get("IPAddress") or None,
                        "gateway": net_data.get("Gateway") or None,
                    }
                )

    mounts = []
    if isinstance(mounts_raw, list):
        for mount in mounts_raw:
            if isinstance(mount, dict):
                mounts.append(
                    {
                        "type": mount.get("Type"),
                        "name": mount.get("Name"),
                        "destination": mount.get("Destination"),
                        "rw": bool(mount.get("RW", True)),
                    }
                )

    return {
        "id": raw_info.get("Id"),
        "name": str(raw_info.get("Name") or "").lstrip("/") or None,
        "endpoint_id": endpoint_id,
        "image": (raw_info.get("Config") or {}).get("Image") or raw_info.get("Image"),
        "state": state_obj.get("Status"),
        "running": bool(state_obj.get("Running", False)),
        "health": health_obj.get("Status") if isinstance(health_obj, dict) else None,
        "exit_code": state_obj.get("ExitCode"),
        "oom_killed": bool(state_obj.get("OOMKilled", False)),
        "restart_count": raw_info.get("RestartCount", 0),
        "started_at": state_obj.get("StartedAt"),
        "finished_at": state_obj.get("FinishedAt"),
        "networks": networks,
        "mounts": mounts,
    }


@docker_container_group.command(name="list")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to local endpoint).")
@click.option("--project", help="Filter by Docker Compose project label.")
@click.option("--state", "state_filter", help="Filter by container state (e.g. running, exited).")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_containers_command(endpoint_id: int | None, project: str | None, state_filter: str | None, as_json: bool) -> None:
    """List Docker containers on the target endpoint."""
    def action() -> dict[str, Any]:
        from src.services.portainer_manager import PortainerManager

        manager = PortainerManager()
        resolved_endpoint = _resolve_endpoint_id(manager, endpoint_id)
        containers = manager.get_containers(resolved_endpoint) or []
        items = [_summarize_container_list_item(item) for item in containers if isinstance(item, dict)]
        if project:
            items = [item for item in items if item.get("project") == project]
        if state_filter:
            expected_state = state_filter.strip().lower()
            items = [item for item in items if str(item.get("state") or "").lower() == expected_state]
        items.sort(key=lambda item: str(item.get("name") or item.get("id") or ""))
        return {
            "endpoint_id": resolved_endpoint,
            "items": items,
            "total": len(items),
        }

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No containers found."
        lines = [f"Containers ({len(items)}):"]
        for item in items:
            lines.append(f"- {item.get('name') or item.get('id')} [{item.get('state')}] image={item.get('image')} project={item.get('project') or '-'}")
        return "\n".join(lines)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_container_group.command(name="inspect")
@click.argument("container")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to local endpoint).")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def inspect_container_command(container: str, endpoint_id: int | None, as_json: bool) -> None:
    """Inspect a Docker container by exact name or full ID."""
    def action() -> dict[str, Any]:
        from src.services.portainer_manager import PortainerManager

        manager = PortainerManager()
        resolved_endpoint = _resolve_endpoint_id(manager, endpoint_id)
        containers = manager.get_containers(resolved_endpoint) or []
        matched = _find_exact_container(containers, container)
        if matched is None:
            raise CLIError("CONTAINER_NOT_FOUND", f"Container '{container}' not found", details={"container": container})
        target_id = str(matched.get("Id") or container)
        info = manager.get_container_by_id(resolved_endpoint, target_id)
        return _summarize_container_inspect(info, resolved_endpoint)

    def render_text(payload: dict[str, Any]) -> str:
        return (
            f"Container: {payload.get('name')} ({payload.get('id')})\n"
            f"State: {payload.get('state')} (health={payload.get('health') or '-'}, exit_code={payload.get('exit_code')}, oom_killed={payload.get('oom_killed')})\n"
            f"Image: {payload.get('image')}\n"
            f"Restart Count: {payload.get('restart_count')}"
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_container_group.command(name="logs")
@click.argument("container")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to local endpoint).")
@click.option("--tail", type=click.IntRange(min=1, max=1000), default=100, show_default=True, help="Number of lines from the end of the logs.")
@click.option("--since", help="Relative duration filter such as 15m, 1h, 24h, or 7d.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def container_logs_command(container: str, endpoint_id: int | None, tail: int, since: str | None, as_json: bool) -> None:
    """Read bounded stdout/stderr logs for a Docker container."""
    def action() -> tuple[dict[str, Any], bool]:
        from src.services.app_access_manager import AppAccessManager
        from src.services.portainer_manager import PortainerManager

        since_ts = _parse_since_timestamp(since)
        manager = PortainerManager()
        resolved_endpoint = _resolve_endpoint_id(manager, endpoint_id)
        containers = manager.get_containers(resolved_endpoint) or []
        matched = _find_exact_container(containers, container)
        if matched is None:
            raise CLIError("CONTAINER_NOT_FOUND", f"Container '{container}' not found", details={"container": container})

        target_id = str(matched.get("Id") or container)
        params: dict[str, Any] = {
            "stdout": "true",
            "stderr": "true",
            "follow": "false",
            "tail": str(tail),
        }
        if since_ts is not None:
            params["since"] = str(since_ts)

        try:
            raw_bytes, scan_truncated = manager.portainer.read_container_logs_bounded(
                resolved_endpoint,
                target_id,
                params,
                max_bytes=1024 * 1024,
                timeout_seconds=20,
            )
        except TimeoutError as exc:
            raise CLIError("LOGS_UNAVAILABLE", str(exc), details={"container": container}) from exc
        except Exception as exc:
            raise CLIError("LOGS_UNAVAILABLE", f"Failed to read container logs: {exc}", details={"container": container}) from exc

        if raw_bytes is None:
            raise CLIError("CONTAINER_NOT_FOUND", f"Container '{container}' not found", details={"container": container})

        raw_entries = AppAccessManager.decode_container_log_entries(raw_bytes, allow_partial_frame=scan_truncated)
        tailed_entries = raw_entries[-tail:] if len(raw_entries) > tail else raw_entries

        sanitized_entries: list[dict[str, str]] = []
        used_bytes = 0
        budget_truncated = False
        for item in reversed(tailed_entries):
            masked_text = mask_sensitive_text(item.get("text") or "")
            encoded = masked_text.encode("utf-8", errors="replace")
            if used_bytes + len(encoded) > MAX_TEXT_BUDGET_BYTES:
                remaining = MAX_TEXT_BUDGET_BYTES - used_bytes
                if remaining > 0 and not sanitized_entries:
                    clipped_text, _ = truncate_utf8_text(masked_text, remaining, keep_tail=True)
                    sanitized_entries.append({"stream": item.get("stream") or "unknown", "text": clipped_text})
                budget_truncated = True
                break
            sanitized_entries.append({"stream": item.get("stream") or "unknown", "text": masked_text})
            used_bytes += len(encoded)
        sanitized_entries.reverse()

        warnings: list[str] = []
        truncated = bool(scan_truncated or budget_truncated)
        if scan_truncated:
            warnings.append("Container log stream reached 1 MiB scan limit and was truncated.")
        if budget_truncated:
            warnings.append("Container log output exceeded 64 KiB text budget and was truncated.")

        names = matched.get("Names") or []
        resolved_name = str(names[0]).lstrip("/") if isinstance(names, list) and names else container
        return (
            {
                "container_id": target_id,
                "container_name": resolved_name,
                "endpoint_id": resolved_endpoint,
                "entries": sanitized_entries,
                "warnings": warnings,
            },
            truncated,
        )

    def render_text(payload: dict[str, Any]) -> str:
        entries = payload.get("entries") or []
        if not entries:
            return f"No log entries for container '{payload.get('container_name') or payload.get('container_id')}'."
        return "\n".join(f"[{entry.get('stream')}] {entry.get('text')}" for entry in entries)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


_PROTECTED_CONTROL_PLANE_NAMES = {"websoft9", "websoft9-apphub", "websoft9-git", "websoft9-portainer", "websoft9-proxy", "websoft9-gateway"}


def _is_protected_container(container_obj: dict[str, Any]) -> bool:
    labels = container_obj.get("Labels") or {}
    if isinstance(labels, dict) and str(labels.get("com.docker.compose.project") or "").lower() == "websoft9":
        return True
    names = container_obj.get("Names") or []
    for raw in names:
        clean = str(raw or "").lstrip("/").lower()
        if clean in _PROTECTED_CONTROL_PLANE_NAMES or clean.startswith("websoft9-"):
            return True
    return False


@docker_container_group.command(name="stats")
@click.argument("container")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID (defaults to local endpoint).")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def container_stats_command(container: str, endpoint_id: int | None, as_json: bool) -> None:
    """Sample point-in-time CPU, memory, network, and PID metrics for a container."""
    def action() -> dict[str, Any]:
        from src.services.portainer_manager import PortainerManager

        manager = PortainerManager()
        resolved_endpoint = _resolve_endpoint_id(manager, endpoint_id)
        containers = manager.get_containers(resolved_endpoint) or []
        matched = _find_exact_container(containers, container)
        if matched is None:
            raise CLIError("CONTAINER_NOT_FOUND", f"Container '{container}' not found", details={"container": container})
        target_id = str(matched.get("Id") or container)

        raw_stats = manager.get_container_stats(resolved_endpoint, target_id)

        mem_stats = raw_stats.get("memory_stats") or {}
        mem_usage = mem_stats.get("usage")
        mem_limit = mem_stats.get("limit")
        mem_pct = round((mem_usage / mem_limit) * 100, 2) if isinstance(mem_usage, int) and isinstance(mem_limit, int) and mem_limit > 0 else None

        cpu_stats = raw_stats.get("cpu_stats") or {}
        precpu_stats = raw_stats.get("precpu_stats") or {}
        cpu_total = (cpu_stats.get("cpu_usage") or {}).get("total_usage")
        precpu_total = (precpu_stats.get("cpu_usage") or {}).get("total_usage")
        sys_cpu = cpu_stats.get("system_cpu_usage")
        presys_cpu = precpu_stats.get("system_cpu_usage")
        online_cpus = cpu_stats.get("online_cpus") or len((cpu_stats.get("cpu_usage") or {}).get("percpu_usage") or []) or 1
        cpu_pct: float | None = None
        if all(isinstance(x, int) for x in (cpu_total, precpu_total, sys_cpu, presys_cpu)):
            cpu_delta = cpu_total - precpu_total
            sys_delta = sys_cpu - presys_cpu
            if sys_delta > 0 and cpu_delta >= 0:
                cpu_pct = round((cpu_delta / sys_delta) * online_cpus * 100.0, 2)

        pids = (raw_stats.get("pids_stats") or {}).get("current")
        names = matched.get("Names") or []
        resolved_name = str(names[0]).lstrip("/") if isinstance(names, list) and names else container
        return {
            "container_id": target_id,
            "container_name": resolved_name,
            "cpu_percent": cpu_pct,
            "memory_usage_bytes": mem_usage,
            "memory_limit_bytes": mem_limit,
            "memory_percent": mem_pct,
            "pids": pids,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return (
            f"Container {payload.get('container_name')}: cpu={payload.get('cpu_percent')}% "
            f"mem={payload.get('memory_usage_bytes')}/{payload.get('memory_limit_bytes')}B ({payload.get('memory_percent')}%) "
            f"pids={payload.get('pids')}"
        )

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


def _run_container_control(container: str, endpoint_id: int | None, operation: str, yes: bool, as_json: bool) -> None:
    def action() -> dict[str, Any]:
        from src.services.portainer_manager import PortainerManager

        manager = PortainerManager()
        resolved_endpoint = _resolve_endpoint_id(manager, endpoint_id)
        containers = manager.get_containers(resolved_endpoint) or []
        matched = _find_exact_container(containers, container)
        if matched is None:
            raise CLIError("CONTAINER_NOT_FOUND", f"Container '{container}' not found", details={"container": container})
        if _is_protected_container(matched):
            raise CLIError("PERMISSION_DENIED", f"Refusing to {operation} protected Websoft9 control-plane container '{container}'")

        if not yes:
            if as_json:
                raise CLIError(
                    "CONFIRMATION_REQUIRED",
                    f"Container {operation} on '{container}' requires --yes confirmation",
                    details={"container": container, "operation": operation},
                )
            if not click.confirm(f"Perform '{operation}' on container '{container}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        target_id = str(matched.get("Id") or container)
        if operation == "start":
            resp = manager.portainer.start_container(resolved_endpoint, target_id)
        elif operation == "stop":
            resp = manager.portainer.stop_container(resolved_endpoint, target_id)
        elif operation == "restart":
            resp = manager.portainer.restart_container(resolved_endpoint, target_id)
        else:
            raise CLIError("INVALID_ARGUMENT", f"Unsupported operation: {operation}", exit_code=2)

        if resp.status_code not in {200, 204, 304}:
            raise CLIError("OPERATION_FAILED", f"Failed to {operation} container '{container}' (HTTP {resp.status_code})")

        return {
            "container_id": target_id,
            "container": container,
            "action": operation,
            "status": "completed",
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Container '{payload.get('container')}' {payload.get('action')} completed."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_container_group.command(name="start")
@click.argument("container")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID.")
@click.option("--yes", "-y", is_flag=True, help="Confirm starting container.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def start_container_command(container: str, endpoint_id: int | None, yes: bool, as_json: bool) -> None:
    """Start a non-control-plane Docker container."""
    _run_container_control(container, endpoint_id, "start", yes, as_json)


@docker_container_group.command(name="stop")
@click.argument("container")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID.")
@click.option("--yes", "-y", is_flag=True, help="Confirm stopping container.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def stop_container_command(container: str, endpoint_id: int | None, yes: bool, as_json: bool) -> None:
    """Stop a non-control-plane Docker container."""
    _run_container_control(container, endpoint_id, "stop", yes, as_json)


@docker_container_group.command(name="restart")
@click.argument("container")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID.")
@click.option("--yes", "-y", is_flag=True, help="Confirm restarting container.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def restart_container_command(container: str, endpoint_id: int | None, yes: bool, as_json: bool) -> None:
    """Restart a non-control-plane Docker container."""
    _run_container_control(container, endpoint_id, "restart", yes, as_json)


@docker_group.group(name="image")
def docker_image_group():
    """List and pull Docker images."""


@docker_image_group.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_images_command(as_json: bool) -> None:
    """List local Docker images."""
    def action() -> dict[str, Any]:
        import docker as _docker

        client = _docker.from_env()
        try:
            images = client.images.list()
        finally:
            try:
                client.close()
            except Exception:
                pass
        items = []
        for img in images:
            attrs = getattr(img, "attrs", {}) or {}
            tags = list(getattr(img, "tags", []) or [])
            items.append(
                {
                    "id": getattr(img, "short_id", None) or attrs.get("Id"),
                    "tags": tags,
                    "size_bytes": attrs.get("Size"),
                    "created": attrs.get("Created"),
                }
            )
        return {"items": items, "total": len(items)}

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No Docker images found."
        return "\n".join(f"- {item.get('id')}: {', '.join(item.get('tags') or ['<untagged>'])} ({item.get('size_bytes')}B)" for item in items)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_image_group.command(name="pull")
@click.argument("image_ref")
@click.option("--yes", "-y", is_flag=True, help="Confirm pulling the Docker image.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def pull_image_command(image_ref: str, yes: bool, as_json: bool) -> None:
    """Pull a Docker image using Websoft9's configured mirror fallback chain."""
    def action() -> dict[str, Any]:
        import docker as _docker
        from src.services.image_pull import pull_with_fallback, validate_image_reference

        validate_image_reference(image_ref)
        if not yes:
            if as_json:
                raise CLIError("CONFIRMATION_REQUIRED", f"Pulling image '{image_ref}' requires --yes confirmation", details={"image": image_ref})
            if not click.confirm(f"Pull Docker image '{image_ref}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        client = _docker.from_env()
        try:
            pulled = pull_with_fallback(client, image_ref)
        finally:
            try:
                client.close()
            except Exception:
                pass
        return {
            "image": image_ref,
            "served_from": getattr(pulled, "source", "direct"),
            "status": "pulled",
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Pulled image '{payload.get('image')}' (source={payload.get('served_from')})."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_group.group(name="volume")
def docker_volume_group():
    """Inspect and manage Docker volumes with inactive-app and control-plane protection."""


@docker_volume_group.command(name="list")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID.")
@click.option("--dangling", is_flag=True, help="Only list dangling volumes.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_volumes_command(endpoint_id: int | None, dangling: bool, as_json: bool) -> None:
    """List Docker volumes on the target endpoint."""
    def action() -> dict[str, Any]:
        from src.services.portainer_manager import PortainerManager

        manager = PortainerManager()
        resolved_endpoint = _resolve_endpoint_id(manager, endpoint_id)
        volumes = manager.get_volumes(resolved_endpoint, dangling) or []
        items = []
        for vol in volumes:
            if not isinstance(vol, dict):
                continue
            labels = vol.get("Labels") or {}
            items.append(
                {
                    "name": vol.get("Name"),
                    "driver": vol.get("Driver"),
                    "project": labels.get("com.docker.compose.project") if isinstance(labels, dict) else None,
                    "created_at": vol.get("CreatedAt"),
                }
            )
        items.sort(key=lambda item: str(item.get("name") or ""))
        return {"endpoint_id": resolved_endpoint, "items": items, "total": len(items)}

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No Docker volumes found."
        return "\n".join(f"- {item.get('name')} (driver={item.get('driver')}, project={item.get('project') or '-'})" for item in items)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_volume_group.command(name="inspect")
@click.argument("volume_name")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def inspect_volume_command(volume_name: str, endpoint_id: int | None, as_json: bool) -> None:
    """Inspect metadata of a specific Docker volume (host paths excluded)."""
    def action() -> dict[str, Any]:
        from src.services.portainer_manager import PortainerManager

        manager = PortainerManager()
        resolved_endpoint = _resolve_endpoint_id(manager, endpoint_id)
        volumes = manager.get_volumes(resolved_endpoint, False) or []
        target = next((v for v in volumes if isinstance(v, dict) and v.get("Name") == volume_name), None)
        if target is None:
            raise CLIError("NOT_FOUND", f"Volume '{volume_name}' not found", details={"volume": volume_name})
        labels = target.get("Labels") or {}
        return {
            "name": target.get("Name"),
            "driver": target.get("Driver"),
            "scope": target.get("Scope"),
            "project": labels.get("com.docker.compose.project") if isinstance(labels, dict) else None,
            "labels": labels if isinstance(labels, dict) else {},
            "created_at": target.get("CreatedAt"),
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Volume: {payload.get('name')} (driver={payload.get('driver')}, project={payload.get('project') or '-'})"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_volume_group.command(name="delete")
@click.argument("volume_name")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID.")
@click.option("--yes", "-y", is_flag=True, help="Confirm permanently deleting the volume.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def delete_volume_command(volume_name: str, endpoint_id: int | None, yes: bool, as_json: bool) -> None:
    """Delete an unreferenced Docker volume (protects control-plane and managed/inactive app volumes)."""
    def action() -> dict[str, Any]:
        from src.services.portainer_manager import PortainerManager

        if volume_name.lower().startswith("websoft9"):
            raise CLIError("PERMISSION_DENIED", f"Refusing to delete protected platform volume '{volume_name}'")

        manager = PortainerManager()
        resolved_endpoint = _resolve_endpoint_id(manager, endpoint_id)
        volumes = manager.get_volumes(resolved_endpoint, False) or []
        target = next((v for v in volumes if isinstance(v, dict) and v.get("Name") == volume_name), None)
        if target is None:
            raise CLIError("NOT_FOUND", f"Volume '{volume_name}' not found", details={"volume": volume_name})

        labels = target.get("Labels") or {}
        project = str(labels.get("com.docker.compose.project") or "") if isinstance(labels, dict) else ""
        if project.lower() == "websoft9":
            raise CLIError("PERMISSION_DENIED", f"Refusing to delete control-plane volume '{volume_name}'")

        stacks = manager.get_stacks(resolved_endpoint) or []
        stack_names = {str(s.get("Name") or "") for s in stacks if isinstance(s, dict)}
        if project and project in stack_names:
            raise CLIError(
                "INVALID_REQUEST",
                f"Volume '{volume_name}' belongs to managed stack '{project}' (active or inactive retained data); use 'app remove --purge-data' instead",
                details={"volume": volume_name, "stack": project},
            )

        if not yes:
            if as_json:
                raise CLIError("CONFIRMATION_REQUIRED", f"Deleting volume '{volume_name}' requires --yes confirmation", details={"volume": volume_name})
            if not click.confirm(f"Permanently delete Docker volume '{volume_name}'?"):
                raise CLIError("OPERATION_CANCELLED", "Operation cancelled by operator")

        manager.remove_volume([volume_name], resolved_endpoint)
        return {"deleted_volume": volume_name, "endpoint_id": resolved_endpoint}

    def render_text(payload: dict[str, Any]) -> str:
        return f"Deleted volume '{payload.get('deleted_volume')}'."

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_group.group(name="network")
def docker_network_group():
    """List and inspect Docker networks."""


@docker_network_group.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_networks_command(as_json: bool) -> None:
    """List Docker networks on the host."""
    def action() -> dict[str, Any]:
        import docker as _docker

        client = _docker.from_env()
        try:
            nets = client.networks.list()
        finally:
            try:
                client.close()
            except Exception:
                pass
        items = []
        for net in nets:
            attrs = getattr(net, "attrs", {}) or {}
            items.append(
                {
                    "id": getattr(net, "short_id", None) or attrs.get("Id"),
                    "name": getattr(net, "name", None) or attrs.get("Name"),
                    "driver": attrs.get("Driver"),
                    "scope": attrs.get("Scope"),
                }
            )
        items.sort(key=lambda item: str(item.get("name") or ""))
        return {"items": items, "total": len(items)}

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        return "\n".join(f"- {item.get('name')} ({item.get('id')}) driver={item.get('driver')}" for item in items)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_network_group.command(name="inspect")
@click.argument("network_name")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def inspect_network_command(network_name: str, as_json: bool) -> None:
    """Inspect a Docker network and its attached containers."""
    def action() -> dict[str, Any]:
        import docker as _docker

        client = _docker.from_env()
        try:
            try:
                net = client.networks.get(network_name)
            except Exception as exc:
                raise CLIError("NOT_FOUND", f"Network '{network_name}' not found", details={"network": network_name}) from exc
            attrs = getattr(net, "attrs", {}) or {}
        finally:
            try:
                client.close()
            except Exception:
                pass
        containers_map = attrs.get("Containers") or {}
        attached = [
            {
                "id": cid,
                "name": info.get("Name"),
                "ipv4_address": info.get("IPv4Address"),
            }
            for cid, info in containers_map.items()
            if isinstance(info, dict)
        ]
        return {
            "id": attrs.get("Id"),
            "name": attrs.get("Name"),
            "driver": attrs.get("Driver"),
            "scope": attrs.get("Scope"),
            "ipam": attrs.get("IPAM"),
            "containers": attached,
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Network: {payload.get('name')} (driver={payload.get('driver')}, containers={len(payload.get('containers') or [])})"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_group.group(name="stack")
def docker_stack_group():
    """List and inspect Portainer stacks (Git credentials masked)."""


@docker_stack_group.command(name="list")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def list_stacks_command(endpoint_id: int | None, as_json: bool) -> None:
    """List Portainer stacks on the target endpoint."""
    def action() -> dict[str, Any]:
        from src.services.portainer_manager import PortainerManager

        manager = PortainerManager()
        resolved_endpoint = _resolve_endpoint_id(manager, endpoint_id)
        stacks = manager.get_stacks(resolved_endpoint) or []
        items = [
            {
                "id": stack.get("Id"),
                "name": stack.get("Name"),
                "status": stack.get("Status"),
                "creation_date": stack.get("CreationDate"),
            }
            for stack in stacks
            if isinstance(stack, dict)
        ]
        items.sort(key=lambda item: str(item.get("name") or ""))
        return {"endpoint_id": resolved_endpoint, "items": items, "total": len(items)}

    def render_text(payload: dict[str, Any]) -> str:
        items = payload.get("items") or []
        if not items:
            return "No Portainer stacks found."
        return "\n".join(f"- {item.get('name')} (id={item.get('id')}, status={item.get('status')})" for item in items)

    run_cli_action(action, as_json=as_json, text_renderer=render_text)


@docker_stack_group.command(name="inspect")
@click.argument("stack_name")
@click.option("--endpoint-id", "endpoint_id", type=click.IntRange(min=1), help="Endpoint ID.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON envelope.")
def inspect_stack_command(stack_name: str, endpoint_id: int | None, as_json: bool) -> None:
    """Inspect a Portainer stack with Git credentials masked."""
    def action() -> dict[str, Any]:
        from src.services.portainer_manager import PortainerManager

        manager = PortainerManager()
        resolved_endpoint = _resolve_endpoint_id(manager, endpoint_id)
        stack = manager.get_stack_by_name(stack_name, resolved_endpoint)
        if not stack:
            raise CLIError("NOT_FOUND", f"Stack '{stack_name}' not found", details={"stack": stack_name})
        git_cfg = stack.get("GitConfig") or {}
        return {
            "id": stack.get("Id"),
            "name": stack.get("Name"),
            "status": stack.get("Status"),
            "endpoint_id": resolved_endpoint,
            "git_config": {
                "url": mask_sensitive_text(str(git_cfg.get("URL") or "")) if isinstance(git_cfg, dict) else None,
                "reference_name": git_cfg.get("ReferenceName") if isinstance(git_cfg, dict) else None,
                "config_file_path": git_cfg.get("ConfigFilePath") if isinstance(git_cfg, dict) else None,
                "config_hash": git_cfg.get("ConfigHash") if isinstance(git_cfg, dict) else None,
            },
        }

    def render_text(payload: dict[str, Any]) -> str:
        return f"Stack: {payload.get('name')} (id={payload.get('id')}, status={payload.get('status')})"

    run_cli_action(action, as_json=as_json, text_renderer=render_text)

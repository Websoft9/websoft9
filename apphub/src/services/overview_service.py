from __future__ import annotations

import json
import os
import socket
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

from src.core.config import ConfigManager
from src.schemas.coreServices import CoreServiceSummary
from src.schemas.overview import (
    OverviewAlert,
    OverviewAppsSummary,
    OverviewHostSummary,
    OverviewProductSummary,
    OverviewResponse,
    OverviewRuntimeSummary,
    OverviewServicesSummary,
    OverviewTaskItem,
    OverviewTasksSummary,
)
from src.services.core_services import CoreServicesService
from src.services.product_auth import ProductAuthService
from src.services.product_metadata import read_product_edition, read_product_metadata


class OverviewService:
    def __init__(
        self,
        auth_service: Optional[ProductAuthService] = None,
        product_metadata_loader: Optional[Callable[[], dict]] = None,
        available_catalog_count_loader: Optional[Callable[[], Optional[int]]] = None,
        host_summary_loader: Optional[Callable[[], dict]] = None,
        host_runtime_summary_loader: Optional[Callable[[], dict]] = None,
        apps_loader: Optional[Callable[[], Sequence[object]]] = None,
        runtime_summary_loader: Optional[Callable[[], dict]] = None,
        services_loader: Optional[Callable[[Optional[str]], Sequence[CoreServiceSummary]]] = None,
        tasks_loader: Optional[Callable[[], Sequence[OverviewTaskItem]]] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.auth_service = auth_service or ProductAuthService()
        self._product_metadata_loader = product_metadata_loader or self._load_product_metadata
        self._available_catalog_count_loader = available_catalog_count_loader or self._load_available_catalog_count
        self._host_summary_loader = host_summary_loader or self._load_host_summary
        self._host_runtime_summary_loader = host_runtime_summary_loader or self._load_host_runtime_summary
        self._apps_loader = apps_loader or self._load_overview_apps
        self._runtime_summary_loader = runtime_summary_loader or self._load_runtime_summary
        self._services_loader = services_loader or (lambda session_token: CoreServicesService().list_services(session_token))
        self._tasks_loader = tasks_loader or self._load_recent_tasks
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._uses_default_tasks_loader = tasks_loader is None
        self._last_cpu_usage_sample: Optional[tuple[int, int]] = None
        self._last_host_cpu_sample: Optional[tuple[int, int]] = None
        self._cached_host_cpu_percent: Optional[tuple[float, int]] = None
        self._last_network_sample: Optional[tuple[int, int, int]] = None
        self._docker_host_info_cache_lock = threading.RLock()
        self._cached_docker_host_info: Optional[tuple[dict, int]] = None

    def get_overview(self, session_token: Optional[str]) -> OverviewResponse:
        self.auth_service._require_authenticated_operator(session_token)

        app_inventory = self._load_apps_inventory()
        apps = self._safe_apps_summary(app_inventory)
        product = self._safe_product_summary(apps)
        host = self._safe_host_summary()
        runtime = self._safe_runtime_summary()
        host_runtime = self._safe_host_runtime_summary()
        services = self._safe_services_summary(session_token)
        tasks = self._safe_tasks_summary(app_inventory)

        return OverviewResponse(
            generated_at=self._timestamp_now(),
            product=product,
            host=host,
            apps=apps,
            runtime=runtime,
            host_runtime=host_runtime,
            services=services,
            tasks=tasks,
            alerts=self._build_alerts(apps=apps, services=services, tasks=tasks),
        )

    def _safe_product_summary(self, apps: OverviewAppsSummary) -> OverviewProductSummary:
        try:
            payload = self._product_metadata_loader() or {}
            catalog_app_count: Optional[int] = None
            try:
                catalog_app_count = self._available_catalog_count_loader()
            except Exception:
                catalog_app_count = None
            return OverviewProductSummary(
                version=payload.get("version") or None,
                edition_key=payload.get("edition_key") or None,
                edition_name=payload.get("edition_name") or None,
                catalog_app_count=catalog_app_count,
                installed_count=apps.installed_count if apps.available else None,
                available_app_count=payload.get("max_apps"),
                upgrade_state=payload.get("upgrade_state") or "unknown",
            )
        except Exception as exc:
            return OverviewProductSummary(available=False, unavailable_reason=str(exc))

    def _safe_runtime_summary(self) -> OverviewRuntimeSummary:
        try:
            payload = self._runtime_summary_loader() or {}
            return OverviewRuntimeSummary(**payload)
        except Exception as exc:
            return OverviewRuntimeSummary(available=False, unavailable_reason=str(exc), health_state="critical")

    def _safe_host_summary(self) -> OverviewHostSummary:
        try:
            payload = self._host_summary_loader() or {}
            return OverviewHostSummary(**payload)
        except Exception as exc:
            return OverviewHostSummary(available=False, unavailable_reason=str(exc))

    def _safe_host_runtime_summary(self) -> OverviewRuntimeSummary:
        try:
            payload = self._host_runtime_summary_loader() or {}
            return OverviewRuntimeSummary(**payload)
        except Exception as exc:
            return OverviewRuntimeSummary(available=False, unavailable_reason=str(exc), health_state="critical")

    def _safe_apps_summary(self, apps: Sequence[object] | Exception | None = None) -> OverviewAppsSummary:
        if isinstance(apps, Exception):
            return OverviewAppsSummary(available=False, unavailable_reason=str(apps))

        if apps is None:
            apps = self._load_apps_inventory()

        if isinstance(apps, Exception):
            return OverviewAppsSummary(available=False, unavailable_reason=str(apps))

        installed_count = len(apps)
        active_count = sum(1 for app in apps if self._app_status(app) == 1)
        inactive_count = sum(1 for app in apps if self._app_status(app) == 2)
        installing_count = sum(1 for app in apps if self._app_status(app) == 3)
        error_count = sum(1 for app in apps if self._app_status(app) == 4)

        return OverviewAppsSummary(
            installed_count=installed_count,
            active_count=active_count,
            inactive_count=inactive_count,
            installing_count=installing_count,
            error_count=error_count,
        )

    def _safe_services_summary(self, session_token: Optional[str]) -> OverviewServicesSummary:
        try:
            services = list(self._services_loader(session_token) or [])
        except Exception as exc:
            return OverviewServicesSummary(available=False, unavailable_reason=str(exc))

        return OverviewServicesSummary(
            total_count=len(services),
            healthy_count=sum(1 for service in services if service.health_state == "healthy"),
            degraded_count=sum(1 for service in services if service.health_state == "degraded"),
            unavailable_count=sum(1 for service in services if service.health_state == "unavailable"),
        )

    def _safe_tasks_summary(self, apps: Sequence[object] | Exception | None = None) -> OverviewTasksSummary:
        if isinstance(apps, Exception) and self._uses_default_tasks_loader:
            return OverviewTasksSummary(available=False, unavailable_reason=str(apps))

        try:
            if apps is not None and self._uses_default_tasks_loader:
                items = list(self._load_recent_tasks_from_apps(apps))
            else:
                items = list(self._tasks_loader() or [])
        except Exception as exc:
            return OverviewTasksSummary(available=False, unavailable_reason=str(exc))
        return OverviewTasksSummary(items=items)

    def _load_apps_inventory(self) -> list[object] | Exception:
        try:
            return list(self._apps_loader() or [])
        except Exception as exc:
            return exc

    def _build_alerts(
        self,
        *,
        apps: OverviewAppsSummary,
        services: OverviewServicesSummary,
        tasks: OverviewTasksSummary,
    ) -> list[OverviewAlert]:
        alerts: list[OverviewAlert] = []
        if apps.available and (apps.error_count > 0 or apps.installing_count > 0):
            level = "error" if apps.error_count > 0 else "info"
            detail_parts = []
            if apps.error_count > 0:
                detail_parts.append(f"{apps.error_count} app(s) need attention")
            if apps.installing_count > 0:
                detail_parts.append(f"{apps.installing_count} task(s) still running")
            alerts.append(
                OverviewAlert(
                    key="apps-attention",
                    level=level,
                    title="Application attention required",
                    detail=", ".join(detail_parts),
                    target_route=apps.target_route,
                )
            )
        if services.available and (services.degraded_count > 0 or services.unavailable_count > 0):
            level = "error" if services.unavailable_count > 0 else "warning"
            alerts.append(
                OverviewAlert(
                    key="services-attention",
                    level=level,
                    title="Core services need review",
                    detail=f"{services.degraded_count} degraded, {services.unavailable_count} unavailable",
                    target_route=services.target_route,
                )
            )
        for item in tasks.items:
            if item.status == "failed":
                alerts.append(
                    OverviewAlert(
                        key=f"task-{item.key}",
                        level="error",
                        title=item.title,
                        detail=item.detail,
                        target_route=item.target_route,
                    )
                )
            elif item.status == "running":
                alerts.append(
                    OverviewAlert(
                        key=f"task-{item.key}",
                        level="info",
                        title=item.title,
                        detail=item.detail,
                        target_route=item.target_route,
                    )
                )
        return alerts

    def _load_product_metadata(self) -> dict:
        metadata = read_product_metadata()
        edition = read_product_edition()
        return {
            "version": metadata.get("version") or None,
            "edition_key": edition.key,
            "edition_name": edition.names.get("zh-CN") or edition.name,
            "max_apps": edition.max_apps,
            "upgrade_state": "unknown",
        }

    def _load_available_catalog_count(self) -> Optional[int]:
        try:
            from src.services.app_manager import AppManger

            initial_apps = ConfigManager("config.ini").get_value("initial_apps", "keys")
            filtered_keys = {
                item.strip()
                for item in (initial_apps or "").split(",")
                if item.strip()
            }
            media_path = AppManger()._ensure_media_asset("product_en.json")
            with open(media_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return None

        if not isinstance(payload, list):
            return None
        if not filtered_keys:
            return len(payload)
        return sum(1 for item in payload if isinstance(item, dict) and item.get("key") in filtered_keys)

    def _load_docker_host_info(self) -> dict:
        now_ns = time.monotonic_ns()
        with self._docker_host_info_cache_lock:
            cached = self._cached_docker_host_info
            if cached is not None:
                payload, cached_at_ns = cached
                if now_ns - cached_at_ns < 5_000_000_000:
                    return dict(payload)

        client = None
        try:
            import docker

            client = docker.from_env()
            info = client.info() or {}
            version = client.version() or {}
        except Exception:
            return {}
        finally:
            if client is not None:
                close_client = getattr(client, "close", None)
                if callable(close_client):
                    try:
                        close_client()
                    except Exception:
                        pass

        payload = {
            "hostname": info.get("Name") or None,
            "os_name": info.get("OperatingSystem") or None,
            "kernel_version": info.get("KernelVersion") or None,
            "architecture": info.get("Architecture") or version.get("Arch") or None,
            "cpu_cores": info.get("NCPU") or None,
            "memory_total_bytes": info.get("MemTotal") or None,
            "docker_root_dir": info.get("DockerRootDir") or None,
        }

        with self._docker_host_info_cache_lock:
            self._cached_docker_host_info = (payload, now_ns)

        return dict(payload)

    def _load_host_summary(self) -> dict:
        docker_host_info = self._load_docker_host_info()
        uname = os.uname()
        return {
            "hostname": docker_host_info.get("hostname") or socket.gethostname() or None,
            "os_name": docker_host_info.get("os_name") or self._read_os_release_name(),
            "kernel_version": docker_host_info.get("kernel_version") or uname.release or None,
            "architecture": docker_host_info.get("architecture") or uname.machine or None,
            "uptime_seconds": self._read_uptime_seconds(),
        }

    def _load_runtime_summary(self) -> dict:
        runtime_scope = "system"
        cpu_quota_cores = self._read_cgroup_cpu_limit_cores()
        cpu_cores = os.cpu_count() or 1
        cpu_percent = self._read_cgroup_cpu_percent(cpu_quota_cores)
        if cpu_percent is not None:
            runtime_scope = "container"
            cpu_percent = round(cpu_percent, 1)
        else:
            cpu_percent = self._read_host_cpu_percent()
            if cpu_percent is None:
                load_one = os.getloadavg()[0]
                cpu_percent = min(max((load_one / cpu_cores) * 100, 0.0), 100.0)
            cpu_percent = round(cpu_percent, 1)

        memory_snapshot = self._read_cgroup_memory_snapshot()
        if memory_snapshot is not None:
            runtime_scope = "container"
            memory_total_bytes, memory_used_bytes = memory_snapshot
        else:
            cgroup_memory_usage_bytes = self._read_cgroup_memory_usage_bytes()
            if cgroup_memory_usage_bytes is not None:
                runtime_scope = "container"
                memory_total_bytes, _ = self._read_memory_snapshot()
                memory_used_bytes = cgroup_memory_usage_bytes
            else:
                memory_total_bytes, memory_available_bytes = self._read_memory_snapshot()
                memory_used_bytes = max(memory_total_bytes - memory_available_bytes, 0)

        memory_percent = round((memory_used_bytes / memory_total_bytes) * 100, 1) if memory_total_bytes > 0 else 0.0

        network_rx_bytes, network_tx_bytes, network_rx_rate_bytes, network_tx_rate_bytes = self._read_network_summary()

        peak_percent = max(cpu_percent, memory_percent)
        if peak_percent >= 90:
            health_state = "critical"
        elif peak_percent >= 75:
            health_state = "warning"
        else:
            health_state = "healthy"

        return {
            "runtime_scope": runtime_scope,
            "health_state": health_state,
            "cpu_percent": cpu_percent,
            "cpu_cores": cpu_cores,
            "cpu_quota_cores": round(cpu_quota_cores, 2) if isinstance(cpu_quota_cores, float) else None,
            "memory_percent": memory_percent,
            "memory_used_bytes": memory_used_bytes,
            "memory_total_bytes": memory_total_bytes,
            "network_rx_rate_bytes": network_rx_rate_bytes,
            "network_tx_rate_bytes": network_tx_rate_bytes,
            "network_rx_bytes": network_rx_bytes,
            "network_tx_bytes": network_tx_bytes,
            "disk_percent": None,
            "disk_used_bytes": None,
            "disk_total_bytes": None,
        }

    def _load_host_runtime_summary(self) -> dict:
        docker_host_info = self._load_docker_host_info()
        cpu_cores = docker_host_info.get("cpu_cores") or os.cpu_count() or 1
        cpu_percent = self._read_host_cpu_percent()
        if cpu_percent is None:
            load_one = os.getloadavg()[0]
            cpu_percent = min(max((load_one / cpu_cores) * 100, 0.0), 100.0)
        cpu_percent = round(cpu_percent, 1)

        memory_total_bytes, memory_available_bytes = self._read_memory_snapshot()
        resolved_memory_total_bytes = docker_host_info.get("memory_total_bytes") or memory_total_bytes
        memory_used_bytes = max(resolved_memory_total_bytes - memory_available_bytes, 0)
        memory_total_bytes = resolved_memory_total_bytes
        memory_percent = round((memory_used_bytes / memory_total_bytes) * 100, 1) if memory_total_bytes > 0 else 0.0

        disk_target = docker_host_info.get("docker_root_dir") or "/"
        try:
            disk_usage = shutil.disk_usage(disk_target)
        except OSError:
            disk_usage = shutil.disk_usage("/")
        disk_used_bytes = max(disk_usage.used, 0)
        disk_total_bytes = max(disk_usage.total, 0)
        disk_percent = round((disk_used_bytes / disk_total_bytes) * 100, 1) if disk_total_bytes > 0 else 0.0

        network_rx_bytes, network_tx_bytes, network_rx_rate_bytes, network_tx_rate_bytes = self._read_network_summary()

        peak_percent = max(cpu_percent, memory_percent, disk_percent)
        if peak_percent >= 90:
            health_state = "critical"
        elif peak_percent >= 75:
            health_state = "warning"
        else:
            health_state = "healthy"

        return {
            "runtime_scope": "system",
            "health_state": health_state,
            "cpu_percent": cpu_percent,
            "cpu_cores": cpu_cores,
            "cpu_quota_cores": None,
            "memory_percent": memory_percent,
            "memory_used_bytes": memory_used_bytes,
            "memory_total_bytes": memory_total_bytes,
            "network_rx_rate_bytes": network_rx_rate_bytes,
            "network_tx_rate_bytes": network_tx_rate_bytes,
            "network_rx_bytes": network_rx_bytes,
            "network_tx_bytes": network_tx_bytes,
            "disk_percent": disk_percent,
            "disk_used_bytes": disk_used_bytes,
            "disk_total_bytes": disk_total_bytes,
        }

    def _read_network_summary(self) -> tuple[int | None, int | None, int | None, int | None]:
        snapshot = self._read_network_snapshot()
        if snapshot is None:
            return None, None, None, None

        rx_bytes, tx_bytes = snapshot
        now_ns = time.monotonic_ns()
        sample = self._last_network_sample
        if sample is None:
            self._last_network_sample = (rx_bytes, tx_bytes, now_ns)
            return rx_bytes, tx_bytes, None, None
        else:
            previous_rx, previous_tx, previous_now_ns = sample
            self._last_network_sample = (rx_bytes, tx_bytes, now_ns)
            delta_rx = rx_bytes - previous_rx
            delta_tx = tx_bytes - previous_tx
            delta_time_ns = now_ns - previous_now_ns

        if delta_time_ns <= 0:
            return rx_bytes, tx_bytes, None, None

        rx_rate = max(int((max(delta_rx, 0) * 1_000_000_000) / delta_time_ns), 0)
        tx_rate = max(int((max(delta_tx, 0) * 1_000_000_000) / delta_time_ns), 0)
        return rx_bytes, tx_bytes, rx_rate, tx_rate

    def _read_network_snapshot(self) -> Optional[tuple[int, int]]:
        raw_snapshot = self._read_text_file(Path("/proc/net/dev"))
        if not raw_snapshot:
            return None

        total_rx = 0
        total_tx = 0
        found_interface = False
        for line in raw_snapshot.splitlines()[2:]:
            if ":" not in line:
                continue
            interface_name, payload = line.split(":", 1)
            interface_name = interface_name.strip()
            if not interface_name or interface_name == "lo":
                continue
            parts = payload.split()
            if len(parts) < 16:
                continue
            try:
                total_rx += int(parts[0])
                total_tx += int(parts[8])
            except ValueError:
                continue
            found_interface = True

        if not found_interface:
            return None
        return total_rx, total_tx

    def _read_cgroup_cpu_percent(self, cpu_quota_cores: Optional[float]) -> Optional[float]:
        usage_ns = self._read_cgroup_cpu_usage_ns()
        if usage_ns is None:
            return None

        now_ns = time.monotonic_ns()
        sample = self._last_cpu_usage_sample
        if sample is None:
            self._last_cpu_usage_sample = (usage_ns, now_ns)
            return None
        else:
            previous_usage_ns, previous_now_ns = sample
            self._last_cpu_usage_sample = (usage_ns, now_ns)
            delta_usage_ns = usage_ns - previous_usage_ns
            delta_wall_ns = now_ns - previous_now_ns

        if delta_usage_ns < 0 or delta_wall_ns <= 0:
            return None

        effective_cores = cpu_quota_cores if cpu_quota_cores and cpu_quota_cores > 0 else float(os.cpu_count() or 1)
        if effective_cores <= 0:
            return None

        return min(max((delta_usage_ns / delta_wall_ns / effective_cores) * 100, 0.0), 999.0)

    def _read_host_cpu_percent(self) -> Optional[float]:
        now_ns = time.monotonic_ns()
        cached = self._cached_host_cpu_percent
        if cached is not None:
            cached_percent, cached_at_ns = cached
            if now_ns - cached_at_ns < 500_000_000:
                return cached_percent

        sample = self._read_host_cpu_times()
        if sample is None:
            return None

        previous_sample = self._last_host_cpu_sample
        if previous_sample is None:
            self._last_host_cpu_sample = sample
            return None
        else:
            self._last_host_cpu_sample = sample
            percent = self._calculate_host_cpu_percent(previous_sample, sample)

        if percent is None:
            return None

        self._cached_host_cpu_percent = (percent, now_ns)
        return percent

    def _read_host_cpu_times(self) -> Optional[tuple[int, int]]:
        raw_stats = self._read_text_file(Path("/proc/stat"))
        if not raw_stats:
            return None

        for line in raw_stats.splitlines():
            if not line.startswith("cpu "):
                continue

            parts = line.split()
            if len(parts) < 5:
                return None

            try:
                values = [int(value) for value in parts[1:]]
            except ValueError:
                return None

            idle_ticks = values[3] + (values[4] if len(values) > 4 else 0)
            total_ticks = sum(values)
            return idle_ticks, total_ticks

        return None

    def _calculate_host_cpu_percent(
        self,
        previous_sample: tuple[int, int],
        current_sample: tuple[int, int],
    ) -> Optional[float]:
        previous_idle_ticks, previous_total_ticks = previous_sample
        current_idle_ticks, current_total_ticks = current_sample

        delta_total_ticks = current_total_ticks - previous_total_ticks
        delta_idle_ticks = current_idle_ticks - previous_idle_ticks
        if delta_total_ticks <= 0 or delta_idle_ticks < 0:
            return None

        busy_ticks = max(delta_total_ticks - delta_idle_ticks, 0)
        return min(max((busy_ticks / delta_total_ticks) * 100, 0.0), 100.0)

    def _read_cgroup_cpu_limit_cores(self) -> Optional[float]:
        cpu_max = self._read_text_file(Path("/sys/fs/cgroup/cpu.max"))
        if cpu_max:
            quota_raw, _, period_raw = cpu_max.partition(" ")
            if quota_raw and quota_raw != "max":
                try:
                    quota_us = int(quota_raw)
                    period_us = int(period_raw.strip())
                    if quota_us > 0 and period_us > 0:
                        return quota_us / period_us
                except ValueError:
                    pass

        quota_raw = self._read_text_file(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"))
        period_raw = self._read_text_file(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us"))
        if quota_raw and period_raw:
            try:
                quota_us = int(quota_raw)
                period_us = int(period_raw)
                if quota_us > 0 and period_us > 0:
                    return quota_us / period_us
            except ValueError:
                return None

        return None

    def _read_cgroup_cpu_usage_ns(self) -> Optional[int]:
        cpu_stat = self._read_text_file(Path("/sys/fs/cgroup/cpu.stat"))
        if cpu_stat:
            for line in cpu_stat.splitlines():
                if line.startswith("usage_usec "):
                    _, _, value = line.partition(" ")
                    try:
                        return int(value.strip()) * 1000
                    except ValueError:
                        return None

        cpuacct_usage = self._read_text_file(Path("/sys/fs/cgroup/cpuacct/cpuacct.usage"))
        if cpuacct_usage:
            try:
                return int(cpuacct_usage)
            except ValueError:
                return None

        return None

    def _read_cgroup_memory_snapshot(self) -> Optional[tuple[int, int]]:
        current_raw = self._read_text_file(Path("/sys/fs/cgroup/memory.current"))
        max_raw = self._read_text_file(Path("/sys/fs/cgroup/memory.max"))
        if current_raw and max_raw:
            try:
                working_set_bytes = self._read_cgroup_memory_usage_bytes()
                if working_set_bytes is None:
                    return None
                limit_bytes = self._parse_cgroup_limit(max_raw)
                if limit_bytes is not None and limit_bytes > 0:
                    return limit_bytes, min(working_set_bytes, limit_bytes)
            except ValueError:
                return None

        current_raw = self._read_text_file(Path("/sys/fs/cgroup/memory/memory.usage_in_bytes"))
        max_raw = self._read_text_file(Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"))
        if current_raw and max_raw:
            try:
                working_set_bytes = self._read_cgroup_memory_usage_bytes()
                if working_set_bytes is None:
                    return None
                limit_bytes = self._parse_cgroup_limit(max_raw)
                if limit_bytes is not None and limit_bytes > 0:
                    return limit_bytes, min(working_set_bytes, limit_bytes)
            except ValueError:
                return None

        return None

    def _read_cgroup_memory_usage_bytes(self) -> Optional[int]:
        current_raw = self._read_text_file(Path("/sys/fs/cgroup/memory.current"))
        if current_raw:
            try:
                used_bytes = int(current_raw)
            except ValueError:
                return None
            inactive_file_bytes = self._read_cgroup_memory_stat_value(Path("/sys/fs/cgroup/memory.stat"), "inactive_file") or 0
            return max(used_bytes - inactive_file_bytes, 0)

        current_raw = self._read_text_file(Path("/sys/fs/cgroup/memory/memory.usage_in_bytes"))
        if current_raw:
            try:
                used_bytes = int(current_raw)
            except ValueError:
                return None
            inactive_file_bytes = (
                self._read_cgroup_memory_stat_value(Path("/sys/fs/cgroup/memory/memory.stat"), "total_inactive_file")
                or self._read_cgroup_memory_stat_value(Path("/sys/fs/cgroup/memory/memory.stat"), "inactive_file")
                or 0
            )
            return max(used_bytes - inactive_file_bytes, 0)

        return None

    def _read_cgroup_memory_stat_value(self, path: Path, key: str) -> Optional[int]:
        raw_stats = self._read_text_file(path)
        if not raw_stats:
            return None

        for line in raw_stats.splitlines():
            if line.startswith(f"{key} "):
                _, _, value = line.partition(" ")
                try:
                    return int(value.strip())
                except ValueError:
                    return None

        return None

    def _parse_cgroup_limit(self, raw_value: str) -> Optional[int]:
        value = raw_value.strip()
        if not value or value == "max":
            return None
        try:
            limit = int(value)
        except ValueError:
            return None
        if limit <= 0 or limit >= (1 << 60):
            return None
        return limit

    def _read_text_file(self, path: Path) -> Optional[str]:
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return content or None

    def _load_recent_tasks(self) -> list[OverviewTaskItem]:
        apps = self._load_apps_inventory()
        if isinstance(apps, Exception):
            raise apps
        return self._load_recent_tasks_from_apps(apps)

    def _load_recent_tasks_from_apps(self, apps: Sequence[object]) -> list[OverviewTaskItem]:
        items: list[OverviewTaskItem] = []

        for app in apps:
            app_id = str(self._app_field(app, "app_id") or "app")
            app_name = str(self._app_field(app, "app_name") or app_id)
            status = self._app_status(app)
            detail = self._app_field(app, "error") or None
            updated_at = self._coerce_task_timestamp(self._app_field(app, "creationDate"))
            if status == 3:
                items.append(
                    OverviewTaskItem(
                        key=f"install-{self._app_field(app, 'tracking_id') or app_id}",
                        kind="app-install",
                        title=f"Installing {app_name}",
                        status="running",
                        detail="Application installation is still running",
                        updated_at=updated_at,
                        target_route="/myapps",
                    )
                )
            elif status == 4:
                items.append(
                    OverviewTaskItem(
                        key=f"install-{self._app_field(app, 'tracking_id') or app_id}",
                        kind="app-install",
                        title=f"{app_name} needs attention",
                        status="failed",
                        detail=str(detail or "Application task failed"),
                        updated_at=updated_at,
                        target_route="/myapps",
                    )
                )

        for task in list(self._load_proxy_tasks()):
            task_id = str(task.get("task_id") or "").strip()
            if not task_id:
                continue
            raw_status = str(task.get("status") or "").strip().lower()
            if raw_status not in {"running", "completed", "failed"}:
                continue
            normalized_status = "success" if raw_status == "completed" else raw_status
            proxy_host = task.get("proxy_host") or {}
            domain_names = proxy_host.get("domain_names") if isinstance(proxy_host, dict) else None
            primary_domain = domain_names[0] if isinstance(domain_names, list) and domain_names else None
            items.append(
                OverviewTaskItem(
                    key=f"proxy-{task_id}",
                    kind="proxy",
                    title=f"Proxy change for {primary_domain}" if isinstance(primary_domain, str) and primary_domain else "Proxy change task",
                    status=normalized_status,
                    detail=task.get("error") or None,
                    updated_at=self._coerce_task_timestamp(task.get("updated_at")),
                    target_route="/gateway",
                )
            )

        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items[:10]

    def _timestamp_now(self) -> str:
        return self._now_provider().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _load_overview_apps(self) -> Sequence[object]:
        from src.services.app_status import appInstalling, appInstallingError
        from src.services.portainer_manager import PortainerManager

        portainer_manager = PortainerManager()
        endpoint_id = portainer_manager.get_local_endpoint_id()
        stacks = portainer_manager.get_stacks(endpoint_id)
        containers = portainer_manager.get_containers(endpoint_id)

        containers_by_project: dict[str, list[dict]] = {}
        for container in containers:
            labels = container.get("Labels") or {}
            project_name = labels.get("com.docker.compose.project")
            if isinstance(project_name, str) and project_name:
                containers_by_project.setdefault(project_name, []).append(container)

        apps: list[dict[str, object]] = []
        for stack in stacks:
            stack_name = stack.get("Name")
            if not isinstance(stack_name, str) or not stack_name:
                continue

            stack_status = stack.get("Status", 0)
            stack_containers = containers_by_project.get(stack_name, [])
            stack_status, stack_error = self._resolve_overview_stack_runtime_state(stack_status, stack_containers)
            apps.append(
                {
                    "app_id": stack_name,
                    "app_name": stack_name,
                    "status": stack_status,
                    "creationDate": stack.get("CreationDate", ""),
                    "error": stack_error,
                }
            )

        apps_by_id = {
            app.get("app_id"): app
            for app in apps
            if isinstance(app.get("app_id"), str) and app.get("app_id")
        }

        for app_uuid, app in appInstalling.items():
            app_id = app.get("app_id")
            if not isinstance(app_id, str) or not app_id:
                continue
            apps_by_id[app_id] = {
                "app_id": app_id,
                "app_name": app.get("app_name") or app_id,
                "tracking_id": app.get("tracking_id", app_uuid),
                "status": app.get("status"),
                "creationDate": app.get("updated_at") or app.get("created_at"),
                "error": app.get("error"),
            }

        for app_uuid, app in appInstallingError.items():
            app_id = app.get("app_id")
            if not isinstance(app_id, str) or not app_id or app_id in apps_by_id:
                continue
            apps_by_id[app_id] = {
                "app_id": app_id,
                "app_name": app.get("app_name") or app_id,
                "tracking_id": app.get("tracking_id", app_uuid),
                "status": app.get("status"),
                "creationDate": app.get("updated_at") or app.get("created_at"),
                "error": app.get("error"),
            }

        return list(apps_by_id.values())

    def _resolve_overview_stack_runtime_state(self, stack_status: int, stack_containers: Sequence[dict] | None) -> tuple[int, str | None]:
        if stack_status == 1 and not stack_containers:
            return 4, "No containers were created for this stack."

        if stack_status == 1 and stack_containers:
            normalized_states = {
                str(container.get("State") or container.get("Status") or "").strip().lower()
                for container in stack_containers
            }
            running_states = {"running", "healthy"}
            if normalized_states and normalized_states.isdisjoint(running_states):
                return 4, "Containers were created for this stack but none of them are running."

        return stack_status, None

    def _load_proxy_tasks(self) -> list[dict]:
        try:
            from src.services.proxy_task_manager import ProxyTaskManager
            return list(ProxyTaskManager._tasks.values())
        except Exception:
            return []

    def _app_field(self, app: object, key: str):
        if isinstance(app, dict):
            return app.get(key)
        return getattr(app, key, None)

    def _app_status(self, app: object) -> int:
        try:
            return int(self._app_field(app, "status") or 0)
        except (TypeError, ValueError):
            return 0

    def _coerce_task_timestamp(self, value: object) -> str:
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
            except (OSError, OverflowError, ValueError):
                return self._timestamp_now()
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return self._timestamp_now()
            if normalized.endswith("Z"):
                return normalized
            try:
                parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
                return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            except ValueError:
                return self._timestamp_now()
        return self._timestamp_now()

    def _read_memory_snapshot(self) -> tuple[int, int]:
        meminfo: dict[str, int] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, _, raw_value = line.partition(":")
                parts = raw_value.strip().split()
                if not parts:
                    continue
                try:
                    meminfo[key] = int(parts[0]) * 1024
                except ValueError:
                    continue

        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
        return total, available

    def _read_os_release_name(self) -> Optional[str]:
        raw_os_release = self._read_text_file(Path("/etc/os-release"))
        if not raw_os_release:
            return None

        for line in raw_os_release.splitlines():
            if line.startswith("PRETTY_NAME="):
                _, _, value = line.partition("=")
                return value.strip().strip('"') or None

        for line in raw_os_release.splitlines():
            if line.startswith("NAME="):
                _, _, value = line.partition("=")
                return value.strip().strip('"') or None

        return None

    def _read_uptime_seconds(self) -> Optional[int]:
        raw_uptime = self._read_text_file(Path("/proc/uptime"))
        if not raw_uptime:
            return None

        uptime_value, _, _ = raw_uptime.partition(" ")
        try:
            return max(int(float(uptime_value)), 0)
        except ValueError:
            return None

import json
import os
import re
import subprocess
import threading
import time
import fcntl
import docker
from typing import Any, Dict, List, Optional
from src.core.exception import CustomException
from src.core.logger import logger
from src.core.config import ConfigManager
from src.services.app_manager import AppManger
from src.services.image_pull import ImagePullError, pull_error_detail, pull_with_fallback
from src.services.portainer_manager import PortainerManager

RESTIC_CACHE_PATH = "/data/restic-cache"

# Every restic command runs in its own throwaway container, which costs about a second even for an
# empty repository. Repository readiness is determined from its local config file so listing
# snapshots does not need to start a separate `cat config` container.
SNAPSHOT_LIST_TTL_SECONDS = 5.0
_repository_ready_cache: Dict[str, tuple[int, int]] = {}
_snapshot_list_cache: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}
_cache_lock = threading.Lock()
_repository_lock = threading.Lock()
_snapshot_cache_generation = 0


def _invalidate_snapshot_cache() -> None:
    """Drop the cached snapshot list every time the repository changes."""
    global _snapshot_cache_generation
    with _cache_lock:
        _snapshot_list_cache.clear()
        _snapshot_cache_generation += 1


def _extract_restic_error(data: Dict[str, Any]) -> str:
    """Extract a human-readable error message from a Restic JSON error line.
    
    Restic v0.17+ uses ``message_type: "error"`` with a nested ``error.message``.
    Restic v0.19+ uses ``message_type: "exit_error"`` with a top-level ``message``.
    """
    msg_type = data.get("message_type") or ""
    if msg_type in ("exit_error", "fatal_error"):
        return data.get("message") or "Fatal Restic error"
    if msg_type == "error":
        err_info = data.get("error", {})
        if isinstance(err_info, dict):
            return err_info.get("message") or str(err_info)
        return str(err_info) if err_info else "Unknown Restic error"
    # Fallback: any top-level message
    return data.get("message") or "Unknown Restic error"


def _is_effective_runtime_container(container: Dict[str, Any], app_id: str) -> bool:
    names = container.get("Names") or []
    normalized_names = [str(name or "").strip("/") for name in names]
    if f"{app_id}-init" in normalized_names:
        return False
    return True


def _container_state(container: Dict[str, Any]) -> str:
    return str(container.get("State") or container.get("Status") or "").strip().lower()


class BackupManager:
    """Volume Backup Manager using Restic container runner"""

    RESTIC_LOCAL_ARGS = ["--insecure-no-password", "--json"]

    def __init__(self):
        try:
            self.docker_client = docker.from_env()

            config_manager = ConfigManager("system.ini")
            self.repository_path = config_manager.get_value("volume_backup", "repopath")
            try:
                self.restic_image = config_manager.get_value("volume_backup", "image") or "restic/restic:latest"
            except Exception:
                self.restic_image = "restic/restic:latest"

            # Ensure cache dir exists
            os.makedirs(RESTIC_CACHE_PATH, exist_ok=True)

            # The repository is verified lazily: doing it here would start a restic container for
            # every request (the manager is created per call) and the console would wait for it.
        except CustomException:
            raise
        except Exception as e:
            logger.error(f"Failed to initialize BackupManager: {e}")
            raise CustomException()

    # ------------------------------------------------------------------
    #  Docker Restic execution — all Restic operations use the same runtime
    # ------------------------------------------------------------------
    def _resolve_host_path(self, container_path: str) -> str:
        """Resolve a container-internal path to its host-level equivalent
        by inspecting the Docker volume mounts of the current container."""
        container_path = os.path.realpath(container_path)
        try:
            # Inspect own container to find bind mounts
            own_id = os.environ.get("HOSTNAME") or ""
            if own_id:
                try:
                    info = self.docker_client.containers.get(own_id)
                    mounts = info.attrs.get("Mounts") or []
                    for mount in mounts:
                        dest = mount.get("Destination") or ""
                        dest_real = os.path.realpath(dest)
                        if container_path == dest_real or container_path.startswith(dest_real + os.sep):
                            source = mount.get("Source") or ""
                            return container_path.replace(dest_real, source, 1)
                except Exception:
                    pass
            return container_path
        except Exception:
            return container_path

    def _ensure_restic_image(self):
        try:
            self.docker_client.images.get(self.restic_image)
            return
        except docker.errors.ImageNotFound:
            logger.access(f"Pulling Restic image: {self.restic_image}")

        # The restic image is a Docker Hub official image, so the shared plan reaches it the
        # same way the install and upgrade paths reach theirs.
        try:
            pulled = pull_with_fallback(self.docker_client, self.restic_image)
        except ImagePullError as exc:
            raise CustomException(
                500, f"Failed to pull {self.restic_image}", pull_error_detail(exc)
            ) from exc
        if pulled.source != "direct":
            logger.access(
                f"Restic image {self.restic_image} came from {pulled.source}"
            )

    def bootstrap_repository(self) -> None:
        """Prepare the image and empty repository during platform startup.

        Repository initialization starts a short-lived restic container through
        the Docker SDK, which also validates the image runtime without requiring
        a Docker CLI inside the platform container.
        """
        self._ensure_restic_image()
        self._ensure_repository()

    def _run_restic_container(self, command: List[str], extra_volumes: Dict[str, Dict[str, str]]) -> str:
        self._ensure_restic_image()

        volumes: Dict[str, Dict[str, str]] = {
            self._resolve_host_path(self.repository_path): {"bind": "/repo", "mode": "rw"},
            self._resolve_host_path(RESTIC_CACHE_PATH): {"bind": "/root/.cache/restic", "mode": "rw"},
        }
        volumes.update(extra_volumes)

        try:
            result = self.docker_client.containers.run(
                image=self.restic_image,
                command=["-r", "/repo"] + command + self.RESTIC_LOCAL_ARGS,
                volumes=volumes,
                remove=True,
                detach=False,
                stdout=True,
                stderr=True,
            )
            output = result.decode("utf-8") if isinstance(result, bytes) else str(result)
            return output
        except docker.errors.ContainerError as e:
            stderr_output = e.stderr.decode("utf-8") if e.stderr else str(e)
            msg = "Unknown error"
            # Restic v0.19+ outputs fatal errors to stderr as JSON with
            # message_type "exit_error" (top-level "message" key).  Older
            # versions may use "error" with a nested error.message.
            for line in stderr_output.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg_type = data.get("message_type") or ""
                if msg_type in ("exit_error", "fatal_error"):
                    msg = data.get("message") or "Fatal Restic error"
                    break
                if msg_type == "error":
                    err_info = data.get("error", {})
                    if isinstance(err_info, dict):
                        msg = err_info.get("message") or str(err_info)
                    else:
                        msg = str(err_info) if err_info else msg
                    break
            if msg == "Unknown error":
                # Fallback: try top-level message from the last JSON line
                for line in reversed(stderr_output.strip().split("\n")):
                    if not line.strip():
                        continue
                    try:
                        fallback = json.loads(line).get("message")
                        if fallback:
                            msg = fallback
                            break
                    except json.JSONDecodeError:
                        continue
            raise CustomException(500, msg, "Restic Container Error")
        except Exception as e:
            raise CustomException(500, f"Restic container failed: {e}", "Container Error")

    def _build_restic_volume_mounts(self, volumes_info: List[Dict[str, Any]]) -> tuple[Dict[str, Dict[str, str]], List[str]]:
        extra_volumes: Dict[str, Dict[str, str]] = {}
        container_paths: List[str] = []

        for volume in volumes_info:
            mountpoint = volume.get("Mountpoint")
            name = volume.get("Name")
            if not mountpoint or not name:
                continue

            resolved_mountpoint = self._resolve_host_path(mountpoint)
            extra_volumes[resolved_mountpoint] = {"bind": f"/{name}", "mode": "rw"}
            container_paths.append(f"/{name}")

        return extra_volumes, container_paths

    def _run_restic_repo_command(self, command: List[str]) -> str:
        return self._run_restic_container(command, {})

    # ------------------------------------------------------------------
    #  Repository management
    # ------------------------------------------------------------------
    def _repository_marker(self) -> tuple[int, int] | None:
        """Return a cheap local marker for an initialized restic repository."""
        try:
            stat = os.stat(os.path.join(self.repository_path, "config"))
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    def _ensure_repository(self) -> None:
        """Make sure the repository exists without starting a check-only restic container."""
        key = str(self.repository_path)
        repository_parent = os.path.dirname(self.repository_path)
        os.makedirs(repository_parent, exist_ok=True)
        lock_path = os.path.join(repository_parent, ".restic-repository-init.lock")

        # The startup bootstrap and API workers are separate processes. A lock
        # beside the repository makes their first initialization mutually exclusive.
        with open(lock_path, "a", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                with _repository_lock:
                    marker = self._repository_marker()
                    with _cache_lock:
                        cached_marker = _repository_ready_cache.get(key)
                    if marker is not None and marker == cached_marker:
                        return
                    if marker is None:
                        logger.info("Repository not initialized, initializing...")
                        self._init_repository()
                        marker = self._repository_marker()
                        if marker is None:
                            raise CustomException(500, "Restic repository initialization did not create config", "Repository Error")
                    with _cache_lock:
                        _repository_ready_cache[key] = marker
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _init_repository(self):
        try:
            output = self._run_restic_repo_command(["init"])
            result = json.loads(output)
            if result.get("message_type") != "initialized":
                logger.error(f"Unexpected init response: {result}")
        except CustomException as e:
            logger.error(f"Repository init failed: {e}")
            raise

    # ------------------------------------------------------------------
    #  Repository operations — container Restic
    # ------------------------------------------------------------------
    def list_snapshots(self, app_id: Optional[str] = None, use_cache: bool = True) -> List[Dict[str, Any]]:
        try:
            cache_key = f"{self.repository_path}:{app_id or ''}"
            if use_cache:
                with _cache_lock:
                    cached = _snapshot_list_cache.get(cache_key)
                    cache_generation = _snapshot_cache_generation
                if cached is not None and (time.monotonic() - cached[0]) < SNAPSHOT_LIST_TTL_SECONDS:
                    return [dict(item) for item in cached[1]]
            else:
                with _cache_lock:
                    cache_generation = _snapshot_cache_generation

            self._ensure_repository()

            command = ["snapshots"]
            if app_id:
                command.extend(["--tag", app_id])

            output = self._run_restic_repo_command(command)
            snapshots = json.loads(output) if output.strip() else []
            with _cache_lock:
                if cache_generation == _snapshot_cache_generation:
                    _snapshot_list_cache[cache_key] = (time.monotonic(), snapshots)
            return snapshots
        except (json.JSONDecodeError, KeyError):
            raise CustomException(500, "Failed to parse snapshot list", "Parse Error")
        except CustomException:
            raise
        except Exception as e:
            raise CustomException(500, f"List snapshots error: {e}", "List Error")

    def delete_snapshot(self, snapshot_id: str) -> None:
        try:
            self._ensure_repository()

            output = self._run_restic_repo_command(["forget", snapshot_id])
            if output.strip():
                raise CustomException(400, f"Delete failed: {output}", f"Snapshot: {snapshot_id}")
            _invalidate_snapshot_cache()
        except CustomException:
            raise
        except Exception as e:
            raise CustomException(500, str(e), "Delete Error")

    # ------------------------------------------------------------------
    #  Read-write operations — Docker runner (needs volume mounts)
    # ------------------------------------------------------------------
    def create_backup(self, app_id: str) -> None:
        try:
            app_info = AppManger().get_app_by_id(app_id)
            volumes_info = getattr(app_info, "volumes", [])
            extra_volumes, container_paths = self._build_restic_volume_mounts(volumes_info)

            if not container_paths:
                raise CustomException(400, f"No volumes found for app: {app_id}", "No Volumes")

            self._ensure_repository()

            command = ["backup"] + container_paths + ["--tag", app_id]
            output = self._run_restic_container(command, extra_volumes)

            backup_error = None
            summary_found = False
            for line in output.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(f"Non-JSON line in Restic backup output: {line[:200]}")
                    continue
                msg_type = data.get("message_type") or ""
                if msg_type == "summary" and "snapshot_id" in data:
                    summary_found = True
                elif msg_type in ("exit_error", "fatal_error", "error"):
                    backup_error = _extract_restic_error(data)

            if backup_error:
                raise CustomException(500, backup_error, f"Restic backup failed for app: {app_id}")
            if not summary_found:
                raise CustomException(500, f"Backup incomplete — no summary returned for app: {app_id}", "Backup Failed")

            _invalidate_snapshot_cache()
            logger.access(f"Backup successful for app: {app_id}")
        except CustomException:
            raise
        except Exception as e:
            logger.error(f"Backup error for app: {app_id}: {e}")
            raise CustomException(500, str(e), "Backup Error")

    def restore_backup(self, app_id: str, snapshot_id: str) -> None:
        try:
            logger.access(f"Restoring snapshot: {snapshot_id}")

            self._ensure_repository()

            # Verify the snapshot exists before attempting restore
            snapshots = self.list_snapshots(app_id, use_cache=False)
            snapshot = next(
                (s for s in snapshots if snapshot_id in {s.get("short_id"), s.get("id")}),
                None,
            )
            if snapshot is None:
                raise CustomException(400, f"Snapshot {snapshot_id} not found", "Snapshot Not Found")

            app_info = AppManger().get_app_by_id(
                app_id, reconcile_stale=False, readonly_install_state=True, strict_exists=True,
            )
            volumes_info = getattr(app_info, "volumes", [])
            endpoint_id = app_info.get("endpointId") if isinstance(app_info, dict) else getattr(app_info, "endpointId", None)

            if not endpoint_id or getattr(app_info, "status", None) == 2:
                raise CustomException(400, "Restore requires an existing application stack", "Restore the inactive application with app restore first")

            if not volumes_info:
                raise CustomException(400, f"No volumes found for app: {app_id}", "No Volumes")

            extra_volumes, container_paths = self._build_restic_volume_mounts(volumes_info)

            if not extra_volumes or len(extra_volumes) != len(volumes_info):
                raise CustomException(400, f"No valid volume mounts found for app: {app_id}", "No Volume Mounts")

            snapshot_paths = snapshot.get("paths")
            if (
                not isinstance(snapshot_paths, list)
                or not all(isinstance(path, str) for path in snapshot_paths)
                or set(snapshot_paths) != set(container_paths)
            ):
                raise CustomException(
                    400,
                    "Snapshot paths do not match application volume mounts",
                    f"Snapshot paths: {snapshot_paths}; destination paths: {container_paths}",
                )

            portainer = PortainerManager()
            containers = portainer.get_containers_by_stack_name(app_id, endpoint_id)
            if not any(_is_effective_runtime_container(c, app_id) for c in containers):
                raise CustomException(400, "Application has no runtime containers", "Restore the application stack before restoring its data")

            # Capture top-level volume ownership before restore so we do not
            # blindly force 33:33 onto non-www-data volumes (e.g. mysql 999, postgres 70).
            pre_restore_owners: dict[str, tuple[int, int]] = {}
            for host_path in extra_volumes:
                try:
                    st = os.stat(host_path)
                    pre_restore_owners[host_path] = (st.st_uid, st.st_gid)
                except OSError:
                    pass

            # Stop containers before restore to release file locks and caches.
            # If stopping fails, abort before overwriting live volume data!
            if endpoint_id:
                try:
                    portainer.stop_stack(app_id, endpoint_id)
                    logger.access(f"Stopped containers for app {app_id} before restore")
                except CustomException:
                    raise
                except Exception as exc:
                    logger.error(f"Failed to stop containers for app {app_id} before restore: {exc}")
                    raise CustomException(
                        500,
                        f"Failed to stop containers for app {app_id} before restore: {exc}",
                        "Restore Stop Failed",
                    ) from exc

            stopped_containers = portainer.get_containers_by_stack_name(app_id, endpoint_id)
            if (
                not any(_is_effective_runtime_container(c, app_id) for c in stopped_containers)
                or any(_container_state(c) not in {"exited", "dead", "created", "stopped"} for c in stopped_containers)
            ):
                raise CustomException(500, "Application containers are not quiescent", "Restore Stop Failed")

            output = self._run_restic_container(["restore", snapshot_id, "--target", "/"], extra_volumes)

            # Parse Restic output to verify success and capture any errors
            restore_error = None
            summary_found = False
            for line in output.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(f"Non-JSON line in Restic restore output: {line[:200]}")
                    continue
                msg_type = data.get("message_type") or ""
                if msg_type == "summary":
                    summary_found = True
                elif msg_type in ("exit_error", "fatal_error", "error"):
                    restore_error = _extract_restic_error(data)

            if restore_error:
                raise CustomException(500, restore_error, f"Restic restore failed for snapshot: {snapshot_id}")

            if not summary_found:
                raise CustomException(500, f"Restore incomplete — no summary returned for snapshot: {snapshot_id}", "Restore Failed")

            # Restore volume root ownership if Restic reset it to root while it was previously non-root.
            for host_path, (orig_uid, orig_gid) in pre_restore_owners.items():
                if (orig_uid, orig_gid) == (0, 0):
                    continue
                try:
                    current_st = os.stat(host_path)
                    if (current_st.st_uid, current_st.st_gid) == (0, 0):
                        os.chown(host_path, orig_uid, orig_gid)
                except OSError:
                    pass

            # Start containers after restore and surface any restart failure instead of swallowing it.
            if endpoint_id:
                try:
                    portainer.start_stack(app_id, endpoint_id)
                    logger.access(f"Started containers for app {app_id} after restore")
                except CustomException:
                    raise
                except Exception as exc:
                    logger.error(f"Failed to start containers for app {app_id} after restore: {exc}")
                    raise CustomException(
                        500,
                        f"Snapshot data was restored, but failed to start containers for app {app_id}: {exc}",
                        "Restore Restart Failed",
                    ) from exc

            self._ensure_restored_app_running(portainer, app_id, endpoint_id)
            _invalidate_snapshot_cache()
            logger.access(f"Snapshot {snapshot_id} restored successfully")
        except CustomException:
            raise
        except Exception as e:
            logger.error(f"Restore error: {e}")
            raise CustomException(500, str(e), "Restore Error")

    def _ensure_restored_app_running(self, portainer: PortainerManager, app_id: str, endpoint_id: int, timeout_seconds: int = 60, poll_interval: int = 3) -> None:
        deadline = time.monotonic() + max(timeout_seconds, 0)
        last_states: List[str] = []

        while True:
            containers = portainer.get_containers_by_stack_name(app_id, endpoint_id)
            runtime_containers = [c for c in containers if _is_effective_runtime_container(c, app_id)]

            if runtime_containers:
                states = [_container_state(container) for container in runtime_containers]
                last_states = states
                if any(state in {"running", "healthy"} for state in states):
                    return

            if time.monotonic() >= deadline:
                detail = ", ".join(last_states) if last_states else "no runtime containers found"
                raise CustomException(500, f"Restored app did not reach a running state: {detail}", "Restore Validation Failed")

            time.sleep(max(poll_interval, 1))
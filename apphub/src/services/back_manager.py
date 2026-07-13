import json
import os
import re
import time
import docker
import requests
from typing import Any, Dict, List, Optional
from src.core.exception import CustomException
from src.core.logger import logger
from src.core.config import ConfigManager
from src.services.app_manager import AppManger
from src.services.portainer_manager import PortainerManager

RESTIC_CACHE_PATH = "/data/restic-cache"


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


def _normalize_mirror(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.startswith("http://"):
        normalized = normalized[7:]
    elif normalized.startswith("https://"):
        normalized = normalized[8:]
    return normalized


def _fetch_mirrors() -> List[str]:
    try:
        from src.services.settings_manager import load_local_mirror_entries
        config_manager = ConfigManager("config.ini")
        configured = (config_manager.get_value("docker_mirror", "url") or "").strip()
        # Legacy URL — hasn't been bootstrapped yet, fall back to local.
        if not configured or configured.startswith("http://") or configured.startswith("https://"):
            return load_local_mirror_entries()
        return [_normalize_mirror(m) for m in configured.replace("\n", ",").split(",") if m.strip()]
    except Exception as e:
        logger.error(f"Failed to load mirrors: {e}")
        return []


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

            self._init_repository()
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

        try:
            self.docker_client.images.pull(self.restic_image)
            return
        except Exception as e:
            logger.warning(f"Direct pull of {self.restic_image} failed, trying mirrors: {e}")

        for mirror in _fetch_mirrors():
            mirrored = f"{mirror}/{self.restic_image}"
            try:
                self.docker_client.images.pull(mirrored)
                img = self.docker_client.images.get(mirrored)
                img.tag(self.restic_image)
                self.docker_client.images.remove(mirrored, force=True)
                logger.access(f"Pulled {self.restic_image} via mirror: {mirror}")
                return
            except Exception as ex:
                logger.warning(f"Mirror {mirror} failed: {ex}")

        raise CustomException(500, f"Failed to pull {self.restic_image}", "Image Pull Error")

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
    def _check_repository(self) -> bool:
        try:
            cfg = json.loads(self._run_restic_repo_command(["cat", "config"]))
            return bool(cfg.get("id") and cfg.get("version"))
        except CustomException:
            return False
        except (json.JSONDecodeError, KeyError):
            return False

    def _init_repository(self):
        if self._check_repository():
            return
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
    def list_snapshots(self, app_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            if not self._check_repository():
                raise CustomException(400, "Repository not initialized", "Repository Error")

            command = ["snapshots"]
            if app_id:
                command.extend(["--tag", app_id])

            output = self._run_restic_repo_command(command)
            return json.loads(output) if output.strip() else []
        except (json.JSONDecodeError, KeyError):
            raise CustomException(500, "Failed to parse snapshot list", "Parse Error")
        except CustomException:
            raise
        except Exception as e:
            raise CustomException(500, f"List snapshots error: {e}", "List Error")

    def delete_snapshot(self, snapshot_id: str) -> None:
        try:
            if not self._check_repository():
                raise CustomException(400, "Repository not initialized", "Repository Error")

            output = self._run_restic_repo_command(["forget", snapshot_id])
            if output.strip():
                raise CustomException(400, f"Delete failed: {output}", f"Snapshot: {snapshot_id}")
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

            if not self._check_repository():
                logger.info("Repository not initialized, re-initializing...")
                self._init_repository()

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

            logger.access(f"Backup successful for app: {app_id}")
        except CustomException:
            raise
        except Exception as e:
            logger.error(f"Backup error for app: {app_id}: {e}")
            raise CustomException(500, str(e), "Backup Error")

    def restore_backup(self, app_id: str, snapshot_id: str) -> None:
        try:
            logger.access(f"Restoring snapshot: {snapshot_id}")

            if not self._check_repository():
                raise CustomException(400, "Repository not initialized", "Repository Error")

            # Verify the snapshot exists before attempting restore
            snapshots = self.list_snapshots(app_id)
            snapshot_ids = {s.get("short_id") or s.get("id") or "" for s in snapshots}
            full_snapshot_ids = {s.get("id") or "" for s in snapshots}
            if snapshot_id not in snapshot_ids and snapshot_id not in full_snapshot_ids:
                raise CustomException(400, f"Snapshot {snapshot_id} not found", "Snapshot Not Found")

            app_info = AppManger().get_app_by_id(app_id)
            volumes_info = getattr(app_info, "volumes", [])
            endpoint_id = app_info.get("endpointId") if isinstance(app_info, dict) else getattr(app_info, "endpointId", None)

            if not volumes_info:
                raise CustomException(400, f"No volumes found for app: {app_id}", "No Volumes")

            extra_volumes, _ = self._build_restic_volume_mounts(volumes_info)

            if not extra_volumes:
                raise CustomException(400, f"No valid volume mounts found for app: {app_id}", "No Volume Mounts")

            portainer = PortainerManager()
            was_active = False
            stack_id = None
            if endpoint_id:
                try:
                    stack_info = portainer.get_stack_by_name(app_id, endpoint_id)
                    if stack_info:
                        stack_id = stack_info.get("Id")
                        was_active = stack_info.get("Status") == 1
                except Exception as exc:
                    logger.warning(f"Could not determine stack state for {app_id}: {exc}")

            # Stop containers before restore to release file locks and caches
            if endpoint_id and was_active:
                try:
                    portainer.stop_stack(app_id, endpoint_id)
                    logger.access(f"Stopped containers for app {app_id} before restore")
                except Exception as exc:
                    logger.warning(f"Failed to stop containers for app {app_id}: {exc}")

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

            # Use the stack state observed before restore. Once an active stack
            # is stopped, Portainer reports it as inactive, which would wrongly
            # push restores down the up_stack path and recreate containers.
            if endpoint_id:
                try:
                    if was_active:
                        portainer.start_stack(app_id, endpoint_id)
                    elif stack_id is not None:
                        portainer.up_stack(stack_id, endpoint_id)
                    else:
                        raise CustomException(404, "Not Found", f"Stack {app_id} not found")

                    self._ensure_restored_app_running(portainer, app_id, endpoint_id)
                    logger.access(f"Started containers for app {app_id} after restore")
                except CustomException:
                    raise
                except Exception as exc:
                    raise CustomException(500, str(exc), "Restore Start Validation Failed")

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
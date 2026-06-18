import json
import os
import re
import subprocess
import docker
import requests
from typing import Any, Dict, List, Optional
from src.core.exception import CustomException
from src.core.logger import logger
from src.core.config import ConfigManager
from src.services.app_manager import AppManger
from src.services.portainer_manager import PortainerManager

DEFAULT_MIRROR_URL = "https://artifact.websoft9.com/release/websoft9/mirrors.json"
RESTIC_CACHE_PATH = "/data/restic-cache"


def _normalize_mirror(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.startswith("http://"):
        normalized = normalized[7:]
    elif normalized.startswith("https://"):
        normalized = normalized[8:]
    return normalized


def _fetch_mirrors() -> List[str]:
    try:
        config_manager = ConfigManager("config.ini")
        configured = (config_manager.get_value("docker_mirror", "url") or "").strip() or DEFAULT_MIRROR_URL
        if configured.startswith("http://") or configured.startswith("https://"):
            resp = requests.get(configured)
            if resp.status_code != 200:
                logger.error(f"Failed to download mirrors: {resp.text}")
                return []
            return [_normalize_mirror(str(m)) for m in resp.json().get("mirrors", []) if str(m).strip()]
        return [_normalize_mirror(m) for m in configured.replace("\n", ",").split(",") if m.strip()]
    except Exception as e:
        logger.error(f"Failed to load mirrors: {e}")
        return []


class BackupManager:
    """Volume Backup Manager using Restic — hybrid local binary + Docker runner"""

    RESTIC_LOCAL_ARGS = ["--insecure-no-password", "--json"]

    def __init__(self):
        try:
            self.docker_client = docker.from_env()

            config_manager = ConfigManager("system.ini")
            self.repository_path = config_manager.get_value("volume_backup", "repopath")
            self.restic_image = config_manager.get_value("volume_backup", "image") or "restic/restic"

            # Verify local restic binary for read-only operations
            if not os.path.isfile("/usr/local/bin/restic") or not os.access("/usr/local/bin/restic", os.X_OK):
                raise CustomException(500, "Restic binary not found at /usr/local/bin/restic", "Restic Unavailable")

            # Ensure cache dir exists
            os.makedirs(RESTIC_CACHE_PATH, exist_ok=True)

            self._init_repository()
        except CustomException:
            raise
        except Exception as e:
            logger.error(f"Failed to initialize BackupManager: {e}")
            raise CustomException()

    # ------------------------------------------------------------------
    #  Local Restic execution — for list / delete / repo ops (fast, no Docker)
    # ------------------------------------------------------------------
    def _run_restic_local(self, command: List[str]) -> str:
        full_cmd = ["/usr/local/bin/restic", "-r", self.repository_path] + command + self.RESTIC_LOCAL_ARGS
        try:
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode != 0:
                err = result.stderr.strip() or f"exit code {result.returncode}"
                raise CustomException(500, err, "Restic Error")
            return result.stdout
        except CustomException:
            raise
        except subprocess.TimeoutExpired:
            raise CustomException(500, "Restic operation timed out after 3600s", "Restic Timeout")
        except FileNotFoundError:
            raise CustomException(500, "Restic binary not found", "Restic Unavailable")
        except Exception as e:
            raise CustomException(500, f"Restic command failed: {e}", "Restic Error")

    # ------------------------------------------------------------------
    #  Docker Restic execution — for backup / restore (needs volume mounts)
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
            logger.warn(f"Direct pull of {self.restic_image} failed, trying mirrors: {e}")

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
                logger.warn(f"Mirror {mirror} failed: {ex}")

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
            try:
                msg = json.loads(stderr_output).get("message", msg)
            except (json.JSONDecodeError, KeyError):
                pass
            raise CustomException(500, msg, "Restic Container Error")
        except Exception as e:
            raise CustomException(500, f"Restic container failed: {e}", "Container Error")

    # ------------------------------------------------------------------
    #  Repository management (local — only touches repo path)
    # ------------------------------------------------------------------
    def _check_repository(self) -> bool:
        try:
            cfg = json.loads(self._run_restic_local(["cat", "config"]))
            return bool(cfg.get("id") and cfg.get("version"))
        except CustomException:
            return False
        except (json.JSONDecodeError, KeyError):
            return False

    def _init_repository(self):
        if self._check_repository():
            return
        try:
            output = self._run_restic_local(["init"])
            result = json.loads(output)
            if result.get("message_type") != "initialized":
                logger.error(f"Unexpected init response: {result}")
        except CustomException as e:
            logger.error(f"Repository init failed: {e}")
            raise

    # ------------------------------------------------------------------
    #  Read-only operations — local binary (fast, no Docker)
    # ------------------------------------------------------------------
    def list_snapshots(self, app_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            if not self._check_repository():
                raise CustomException(400, "Repository not initialized", "Repository Error")

            command = ["snapshots"]
            if app_id:
                command.extend(["--tag", app_id])

            output = self._run_restic_local(command)
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

            output = self._run_restic_local(["forget", snapshot_id])
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

            extra_volumes: Dict[str, Dict[str, str]] = {}
            container_paths: List[str] = []
            for v in volumes_info:
                mountpoint = v.get("Mountpoint")
                name = v.get("Name")
                if mountpoint and name:
                    extra_volumes[mountpoint] = {"bind": f"/{name}", "mode": "rw"}
                    container_paths.append(f"/{name}")

            if not container_paths:
                raise CustomException(400, f"No volumes found for app: {app_id}", "No Volumes")

            if not self._check_repository():
                logger.info("Repository not initialized, re-initializing...")
                self._init_repository()

            command = ["backup"] + container_paths + ["--tag", app_id]
            output = self._run_restic_container(command, extra_volumes)

            for line in output.strip().split("\n"):
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("message_type") == "summary" and "snapshot_id" in data:
                    logger.access(f"Backup successful for app: {app_id}")
                    return

            raise CustomException(500, f"Backup failed for app: {app_id}", "Backup Failed")
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

            app_info = AppManger().get_app_by_id(app_id)
            volumes_info = getattr(app_info, "volumes", [])
            endpoint_id = app_info.get("endpointId") if isinstance(app_info, dict) else getattr(app_info, "endpointId", None)

            extra_volumes: Dict[str, Dict[str, str]] = {}
            for v in volumes_info:
                mountpoint = v.get("Mountpoint")
                name = v.get("Name")
                if mountpoint and name:
                    extra_volumes[mountpoint] = {"bind": f"/{name}", "mode": "rw"}

            # Stop containers before restore to release file locks and caches
            portainer = PortainerManager()
            if endpoint_id:
                try:
                    portainer.stop_stack(app_id, endpoint_id)
                    logger.access(f"Stopped containers for app {app_id} before restore")
                except Exception as exc:
                    logger.warn(f"Failed to stop containers for app {app_id}: {exc}")

            output = self._run_restic_container(["restore", snapshot_id, "--target", "/"], extra_volumes)

            # Start containers after restore
            if endpoint_id:
                try:
                    portainer.start_stack(app_id, endpoint_id)
                    logger.access(f"Started containers for app {app_id} after restore")
                except Exception as exc:
                    logger.warn(f"Failed to start containers for app {app_id}: {exc}")

            for line in output.strip().split("\n"):
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("message_type") == "summary":
                    logger.access(f"Snapshot {snapshot_id} restored successfully")
                    return

            raise CustomException(500, f"Restore failed for snapshot: {snapshot_id}", "Restore Failed")
        except CustomException:
            raise
        except Exception as e:
            logger.error(f"Restore error: {e}")
            raise CustomException(500, str(e), "Restore Error")
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import docker
import requests

from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.core.logger import logger
from src.services.image_pull import pull_with_fallback, require_local_image
from src.services.product_runtime_state import read_release_channel, read_release_version


ARTIFACT_BASE_URL = "https://artifact.websoft9.com/websoft9"
REQUIRED_ARTIFACTS = ("version.json", "docker-compose.yml", "runner-upgrade.sh", "manifest.json")
SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
RUNNER_IMAGE_TAG = "docker:29.8.1-cli"
RUNNER_IMAGE_DIGEST = "sha256:9f36dfce2d1fd053d700a4eca00c358df79bf7d8cb69d4a9e8d9981af18834ea"
# Pulled by digest so that no fallback source can serve a different image; resolution later
# goes through the tag, because a mirror pull records its own repository for that digest.
RUNNER_IMAGE = f"{RUNNER_IMAGE_TAG}@{RUNNER_IMAGE_DIGEST}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _seconds_since(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - moment).total_seconds()


# Last resort when the runner container cannot be inspected. Upgrades normally finish far
# sooner, so beyond this window the persisted "applying" flag can no longer be trusted.
STALE_APPLY_GRACE_SECONDS = 30 * 60

# A failure is only useful when it says what went wrong and what to do next. The runner records
# a machine-readable reason next to its human detail; these are the terminal states that carry one.
FAILURE_STATES = ("rolled_back", "rollback_failed", "degraded")
# Reason reported when the runner died without writing a terminal state of its own.
RUNNER_EXIT_REASON = "runner_exit"
# Runner logs are the fallback when the on-disk log is missing (the runner died before it opened
# its log), so the console can always show the operator why an upgrade stopped.
MAX_LOG_LINES = 1000
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# A deployment can use any compose file name. The runner has to replay the upgrade with the
# file the stack was actually created from: regenerating it from a different file would start a
# second container (name/port clash) while the health check kept watching the original one, so
# an upgrade could be reported as completed without anything having been upgraded.
DEFAULT_COMPOSE_FILE_NAME = "docker-compose.yml"

# Auto download is on by default: a published release is staged in the background so that the
# operator only has to confirm the install. `upgrade.auto_download = false` in config.ini
# turns it off (metered networks, maintenance windows, air-gapped reviews).
AUTO_DOWNLOAD_SECTION = "upgrade"
AUTO_DOWNLOAD_KEY = "auto_download"
AUTO_DOWNLOAD_DISABLED_VALUES = {"0", "false", "no", "off"}


def auto_download_enabled() -> bool:
    """Report whether a detected release may be downloaded without being asked."""
    try:
        configured = ConfigManager("config.ini").get_value(AUTO_DOWNLOAD_SECTION, AUTO_DOWNLOAD_KEY)
    except Exception:
        return True
    return str(configured or "").strip().lower() not in AUTO_DOWNLOAD_DISABLED_VALUES


def maybe_start_auto_download(*, latest_version: Any, current_version: Any = None) -> bool:
    """Stage a newer release in the background when auto download is allowed.

    Called by the scheduled check, the startup check and the explicit "check for updates"
    action, so it must never raise and never start a second job: the upgrade lock, the
    persisted state and the version comparison all guard the call.
    """
    # A test run must never reach the network or touch a deployment's data root.
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    try:
        if not latest_version or not auto_download_enabled():
            return False
        current = str(current_version or read_release_version() or "")
        current_parsed = UpgradeManager._parse_version(current)
        latest_parsed = UpgradeManager._parse_version(str(latest_version))
        if not current_parsed or not latest_parsed or latest_parsed <= current_parsed:
            return False
        manager = UpgradeManager()
        state = manager.status()
        if state.get("state") in {"downloading", "applying"}:
            return False
        if state.get("state") == "ready" and str(state.get("target_version") or "") == str(latest_version):
            # This release is already staged; nothing to fetch.
            return False
        manager.start_prepare()
        logger.info(f"Auto download started for {latest_version} (current {current})")
        return True
    except CustomException as exc:
        logger.warning(f"Auto download skipped: {exc.details}")
        return False
    except Exception as exc:
        logger.warning(f"Auto download could not start: {exc}")
        return False


class UpgradeManager:
    def __init__(self, *, data_root: str | None = None, artifact_base_url: str = ARTIFACT_BASE_URL):
        self.data_root = Path(data_root or os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data"))
        self.upgrade_root = self.data_root / "upgrade"
        self.artifact_base_url = artifact_base_url.rstrip("/")

    @property
    def state_file(self) -> Path:
        return self.upgrade_root / "state.json"

    def _read_state(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_state(self, payload: dict[str, Any]) -> None:
        self.upgrade_root.mkdir(parents=True, exist_ok=True)
        payload = {**payload, "updated_at": _utc_now()}
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.upgrade_root, delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=True, separators=(",", ":"))
            handle.write("\n")
            temporary_path = Path(handle.name)
        os.replace(temporary_path, self.state_file)

    def status(self, *, run_id: str | None = None) -> dict[str, Any]:
        state = self._read_state()
        if run_id and state.get("run_id") != run_id:
            raise CustomException(404, "Upgrade Not Found", "The requested upgrade task does not exist")
        if state.get("state") == "downloading" and not self._job_running():
            # The process was restarted (or crashed) while downloading. Report the
            # interrupted download instead of spinning forever, so the operator can retry.
            state = {**state, "state": "download_failed", "detail": "download_interrupted"}
        if state.get("state") == "applying" and self._apply_is_stale(state):
            # The runner vanished without writing a terminal state, so the upgrade was cut off.
            # Report it (and stop blocking retries) instead of pinning the console on
            # "applying" forever. Its exit code and last log line are the only reason available.
            runner_failure = self._runner_failure(state)
            state = {
                **state,
                "state": "apply_interrupted",
                "detail": runner_failure.get("detail") if runner_failure else "upgrade_interrupted",
                "reason": RUNNER_EXIT_REASON,
                **({"exit_code": runner_failure["exit_code"]} if runner_failure else {}),
            }
        # A failed download is a diagnostic, not a lifecycle state: nothing was installed, the
        # platform is idle and the operator can simply retry. Expose the durable record through
        # last_failure so that `state` only answers "what can I do right now".
        last_failure = None
        if state.get("state") == "download_failed":
            last_failure = self._failure_payload(state, default_reason="download_failed")
            state = {**state, "state": "idle", "detail": None}
        elif state.get("state") in FAILURE_STATES or state.get("state") == "apply_interrupted":
            # Terminal outcomes keep their own state so the console can explain what the platform
            # looks like now; the failure record is what makes the reason and the log reachable.
            last_failure = self._failure_payload(state, default_reason=str(state.get("state")))
        current_version = read_release_version() or ""
        return {
            "current_version": current_version,
            "channel": read_release_channel(),
            "run_id": state.get("run_id"),
            "state": state.get("state", "idle"),
            "target_version": state.get("target_version"),
            "detail": state.get("detail"),
            "reason": state.get("reason"),
            "exit_code": state.get("exit_code"),
            "updated_at": state.get("updated_at"),
            "log_path": state.get("log_path"),
            "last_failure": last_failure,
        }

    def _failure_payload(self, state: dict[str, Any], *, default_reason: str) -> dict[str, Any]:
        """Describe the last failed run so the console can show a reason, not just an outcome."""
        return {
            "run_id": str(state.get("run_id") or ""),
            "reason": state.get("reason") or default_reason,
            "detail": state.get("detail"),
            "exit_code": state.get("exit_code"),
            "target_version": state.get("target_version"),
            "at": state.get("updated_at"),
            "log_path": state.get("log_path"),
        }

    def _runner_failure(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Read why the runner container stopped: its exit code and last log line.

        A runner that aborts before touching the deployment never writes a state of its own, so
        the container itself is the only witness left. Returns None when Docker cannot answer,
        which keeps the caller on its generic "interrupted" wording.
        """
        run_id = str(state.get("run_id") or "").strip()
        if not run_id:
            return None
        try:
            container = docker.from_env().containers.get(self._runner_container_name(run_id))
            container.reload()
            exit_code = container.attrs.get("State", {}).get("ExitCode")
            raw = container.logs(tail=20, stdout=True, stderr=True)
        except Exception:  # noqa: BLE001 - diagnostics must never break the status endpoint
            return None
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        # The runner mirrors its log to the container output; the last non-empty line is the abort
        # message ("upgrade runner: ...") or the final progress line of a killed run.
        detail = lines[-1][:300] if lines else "upgrade_interrupted"
        return {"detail": detail, "exit_code": exit_code, "lines": lines[-20:]}

    @staticmethod
    def _runner_container_name(run_id: str) -> str:
        return f"websoft9-upgrade-{run_id[:12]}"

    @staticmethod
    def _clear_stale_runner(docker_client, run_id: str) -> None:
        """Remove the runner container left behind by an earlier attempt of the same run."""
        name = UpgradeManager._runner_container_name(run_id)
        try:
            container = docker_client.containers.get(name)
        except Exception:  # noqa: BLE001 - not found is the normal case
            return
        if getattr(container, "status", "") == "running":
            # Never kill a live runner: that would leave the platform half upgraded.
            raise CustomException(409, "Upgrade In Progress", "The previous upgrade runner is still running")
        try:
            container.remove(force=True)
            logger.info(f"Removed the leftover upgrade runner container {name}")
        except Exception as exc:  # noqa: BLE001 - surface it as a clear runner problem
            raise CustomException(502, "Upgrade Runner Unavailable", f"Unable to clear the previous upgrade runner: {exc}")

    def read_log(self, run_id: str, *, tail: int = 200) -> dict[str, Any]:
        """Return the tail of a run's upgrade log, falling back to the runner container output."""
        run_id = str(run_id or "").strip()
        if not RUN_ID_PATTERN.match(run_id):
            raise CustomException(400, "Invalid Upgrade Run", "The upgrade run id is not valid")
        try:
            limit = max(1, min(int(tail), MAX_LOG_LINES))
        except (TypeError, ValueError):
            limit = 200
        log_file = self.upgrade_root / "logs" / f"{run_id}.log"
        lines: list[str] = []
        try:
            lines = [line for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        except OSError:
            lines = []
        source = "file"
        if not lines:
            runner_failure = self._runner_failure({"run_id": run_id})
            lines = list(runner_failure.get("lines", [])) if runner_failure else []
            source = "runner" if lines else "missing"
        return {
            "run_id": run_id,
            "source": source,
            "path": str(log_file),
            "lines": lines[-limit:],
        }

    def _acquire_lock(self):
        self.upgrade_root.mkdir(parents=True, exist_ok=True)
        handle = open(self.upgrade_root / "lock", "a", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise CustomException(409, "Upgrade In Progress", "Another upgrade operation is already active")
        return handle

    @staticmethod
    def _release_lock(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

    def _job_running(self) -> bool:
        """Return True while a download or apply holds the upgrade lock."""
        try:
            handle = self._acquire_lock()
        except CustomException:
            return True
        try:
            self._release_lock(handle)
        except OSError:
            pass
        return False

    def _runner_is_active(self, run_id: str) -> bool | None:
        """Report whether the upgrade runner container is still running.

        Returns None when Docker cannot be queried, so the caller can fall back to a deadline
        instead of guessing. The runner is started detached and kept after it exits, so its
        state is the observable fact we reconcile the persisted ``applying`` flag against.
        """
        try:
            containers = docker.from_env().containers.list(
                all=True,
                filters={"label": f"websoft9.upgrade.run_id={run_id}"},
            )
        except Exception:
            return None
        if not containers:
            return False
        return any(getattr(container, "status", "") == "running" for container in containers)

    def _apply_is_stale(self, state: dict[str, Any]) -> bool:
        run_id = str(state.get("run_id") or "").strip()
        if run_id:
            active = self._runner_is_active(run_id)
            if active is not None:
                return not active
        # Docker unavailable (or no run id to look up): only a generous deadline is left.
        age = _seconds_since(state.get("updated_at"))
        if age is None:
            return True
        return age > STALE_APPLY_GRACE_SECONDS

    def _download_file(self, url: str, destination: Path) -> None:
        try:
            response = requests.get(url, timeout=60, headers={"Cache-Control": "no-cache"})
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CustomException(502, "Upgrade Artifact Unavailable", f"Unable to download {url}: {exc}")
        destination.write_bytes(response.content)

    @staticmethod
    def _checksums(payload: str) -> dict[str, str]:
        checksums: dict[str, str] = {}
        for raw_line in payload.splitlines():
            parts = raw_line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            digest, filename = parts[0].lower(), parts[1].lstrip(" *")
            if not re.fullmatch(r"[0-9a-f]{64}", digest) or not SAFE_ARTIFACT_NAME.fullmatch(filename):
                continue
            if filename in checksums:
                raise CustomException(502, "Invalid Upgrade Artifact", f"Duplicate checksum entry: {filename}")
            checksums[filename] = digest
        return checksums

    def _download_and_verify_artifacts(self, *, channel: str, staging_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        base_url = f"{self.artifact_base_url}/{channel}"
        try:
            checksum_response = requests.get(f"{base_url}/SHA256SUMS", timeout=20, headers={"Cache-Control": "no-cache"})
            checksum_response.raise_for_status()
        except requests.RequestException as exc:
            raise CustomException(502, "Upgrade Artifact Unavailable", f"Unable to download SHA256SUMS: {exc}")
        checksums = self._checksums(checksum_response.text)
        for filename in REQUIRED_ARTIFACTS:
            expected = checksums.get(filename)
            if not expected:
                raise CustomException(502, "Invalid Upgrade Artifact", f"SHA256SUMS does not cover {filename}")
            destination = staging_dir / filename
            self._download_file(f"{base_url}/{filename}", destination)
            actual = hashlib.sha256(destination.read_bytes()).hexdigest()
            if actual != expected:
                raise CustomException(502, "Invalid Upgrade Artifact", f"Checksum mismatch for {filename}")
        return (
            json.loads((staging_dir / "manifest.json").read_text(encoding="utf-8")),
            json.loads((staging_dir / "version.json").read_text(encoding="utf-8")),
        )

    @staticmethod
    def _parse_version(value: str) -> tuple[int, int, int] | None:
        match = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?", value.strip())
        return tuple(int(part or 0) for part in match.groups()) if match else None

    def _discover_deployment(self) -> dict[str, str]:
        try:
            client = docker.from_env()
            current = client.containers.get(os.getenv("HOSTNAME", ""))
        except Exception as exc:
            raise CustomException(500, "Upgrade Precheck Failed", f"Cannot inspect the running product container: {exc}")

        labels = current.attrs.get("Config", {}).get("Labels", {}) or {}
        install_path = labels.get("com.docker.compose.project.working_dir", "")
        project = labels.get("com.docker.compose.project", "")
        container_name = current.name
        data_source = ""
        for mount in current.attrs.get("Mounts", []) or []:
            if mount.get("Type") == "bind" and mount.get("Destination") == str(self.data_root):
                data_source = str(mount.get("Source") or "")
                break
        if not install_path or not project or not data_source:
            raise CustomException(409, "Upgrade Precheck Failed", "The current Compose deployment cannot be safely identified")
        return {
            "install_path": install_path,
            "compose_project": project,
            "container_name": container_name,
            "compose_file": self._resolve_compose_file(labels, install_path),
            "data_root": data_source,
        }

    def _resolve_compose_file(self, labels: dict[str, Any], install_path: str) -> str:
        """Return the compose file the running deployment was created from."""
        candidates = [
            entry.strip()
            for entry in str(labels.get("com.docker.compose.project.config_files") or "").split(",")
            if entry.strip()
        ]
        parent = os.path.normpath(install_path)
        # The runner bind-mounts INSTALL_PATH only, so a file outside it could not be read anyway.
        for candidate in candidates:
            if os.path.isabs(candidate) and os.path.dirname(os.path.normpath(candidate)) == parent:
                return candidate
        return os.path.join(install_path, DEFAULT_COMPOSE_FILE_NAME)

    def prepare(self) -> dict[str, Any]:
        """Run a full prepare synchronously; used by tests."""
        return self._prepare(str(uuid4()))

    def start_prepare(self) -> dict[str, Any]:
        """Queue the download in the background and return the current status immediately."""
        state = self._read_state()
        # A stale "applying" must not block the operator forever: only a runner that is still
        # alive counts as an upgrade in progress.
        if state.get("state") == "applying" and not self._apply_is_stale(state):
            raise CustomException(409, "Upgrade In Progress", "An upgrade is already running")
        # Take the lock before publishing the state so that status() can trust it.
        lock = self._acquire_lock()
        try:
            run_id = str(uuid4())
            self._write_state({
                "run_id": run_id,
                "state": "downloading",
                "detail": "Downloading upgrade artifacts",
                "log_path": str(self.upgrade_root / "logs" / f"{run_id}.log"),
            })
            threading.Thread(target=self._run_prepare, args=(run_id, lock), daemon=True).start()
        except Exception:
            self._release_lock(lock)
            raise
        return self.status(run_id=run_id)

    def _run_prepare(self, run_id: str, lock) -> None:
        try:
            self._prepare_locked(run_id)
        except CustomException as exc:
            self._write_state({
                "run_id": run_id,
                "state": "download_failed",
                "detail": exc.details,
                "reason": "download_failed",
            })
        except Exception as exc:  # surface any failure through the persisted state
            self._write_state({
                "run_id": run_id,
                "state": "download_failed",
                "detail": str(exc),
                "reason": "download_failed",
            })
        finally:
            self._release_lock(lock)

    def _prepare(self, run_id: str) -> dict[str, Any]:
        lock = self._acquire_lock()
        try:
            return self._prepare_locked(run_id)
        finally:
            self._release_lock(lock)

    def _prepare_locked(self, run_id: str) -> dict[str, Any]:
        """Download and verify artifacts. The caller must hold the upgrade lock."""
        current_version = read_release_version() or ""
        channel = read_release_channel()
        staging_dir = self.upgrade_root / "staging" / run_id
        staging_dir.mkdir(parents=True, mode=0o700)
        self._write_state({
            "run_id": run_id,
            "state": "downloading",
            "detail": "Downloading upgrade artifacts",
            "log_path": str(self.upgrade_root / "logs" / f"{run_id}.log"),
        })
        try:
            manifest, version_payload = self._download_and_verify_artifacts(channel=channel, staging_dir=staging_dir)
            target_version = str(version_payload.get("version") or "").strip()
            image = manifest.get("image") if isinstance(manifest.get("image"), dict) else {}
            repository = str(image.get("repository") or "").strip()
            version_tag = str(image.get("version_tag") or "").strip()
            if not target_version or not repository or not version_tag:
                raise CustomException(502, "Invalid Upgrade Artifact", "Version or image metadata is missing")
            current_parsed, target_parsed = self._parse_version(current_version), self._parse_version(target_version)
            if not current_parsed or not target_parsed or target_parsed <= current_parsed:
                raise CustomException(409, "Upgrade Not Available", "The target version is not newer than the current version")
            install = manifest.get("install") if isinstance(manifest.get("install"), dict) else {}
            if install.get("runner_upgrade_script") != "runner-upgrade.sh":
                raise CustomException(502, "Invalid Upgrade Artifact", "The release does not support in-console upgrade")
            deployment = self._discover_deployment()
            try:
                docker_client = docker.from_env()
                # Same order as the host installer: direct pull, then Amazon ECR Public, then the
                # operator's accelerator mirrors. ECR only keeps the floating aliases, so the
                # pinned tag is mapped onto them and the pulled image is verified against the
                # target version before it is accepted.
                pulled = pull_with_fallback(
                    docker_client,
                    f"{repository}:{version_tag}",
                    expected_version=target_version,
                    alias_tags=[str(entry) for entry in (image.get("alias_tags") or [])],
                )
                pull_with_fallback(docker_client, RUNNER_IMAGE)
            except Exception as exc:
                raise CustomException(502, "Upgrade Image Unavailable", f"Unable to pull an upgrade image: {exc}")
            digest = pulled.digest
            if not digest:
                raise CustomException(502, "Upgrade Image Unavailable", "The pulled image has no repository digest")
            if pulled.source != "direct":
                logger.warning(f"Upgrade image {repository}:{version_tag} came from {pulled.source}")
            task = {
                "RUN_ID": run_id,
                "DATA_ROOT": deployment["data_root"],
                "STAGING_DIR": str(staging_dir),
                "INSTALL_PATH": deployment["install_path"],
                "COMPOSE_FILE": deployment["compose_file"],
                "COMPOSE_PROJECT": deployment["compose_project"],
                "TARGET_IMAGE_REPO": repository,
                "TARGET_IMAGE_TAG": version_tag,
                "TARGET_IMAGE_DIGEST": digest,
                "TARGET_VERSION": target_version,
                "CONTAINER_NAME": deployment["container_name"],
            }
            # The runner refuses a task file that sits outside the staging directory, so the task
            # and the material it points at always travel together in the same folder.
            task_file = staging_dir / "task.env"
            temporary_file = task_file.with_suffix(".tmp")
            temporary_file.write_text("".join(f"{key}={value}\n" for key, value in task.items()), encoding="utf-8")
            os.replace(temporary_file, task_file)
            self._write_state({
                "run_id": run_id,
                "state": "ready",
                "target_version": target_version,
                "detail": "Upgrade is prepared",
                "log_path": str(self.upgrade_root / "logs" / f"{run_id}.log"),
            })
            return self.status(run_id=run_id)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

    @staticmethod
    def _read_task(task_file: Path) -> dict[str, str]:
        allowed = {
            "RUN_ID", "DATA_ROOT", "STAGING_DIR", "INSTALL_PATH", "COMPOSE_FILE", "COMPOSE_PROJECT",
            "TARGET_IMAGE_REPO", "TARGET_IMAGE_TAG", "TARGET_IMAGE_DIGEST", "TARGET_VERSION", "CONTAINER_NAME",
        }
        values: dict[str, str] = {}
        try:
            lines = task_file.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise CustomException(409, "Upgrade Not Ready", f"Unable to read prepared task: {exc}")
        for line in lines:
            if not line or line.startswith("#") or "=" not in line:
                raise CustomException(409, "Upgrade Not Ready", "The prepared task is invalid")
            key, value = line.split("=", 1)
            if key not in allowed or key in values or not value or any(character in value for character in "'\"`$\\ !;&|<>"):
                raise CustomException(409, "Upgrade Not Ready", "The prepared task is invalid")
            values[key] = value
        if values.keys() != allowed:
            raise CustomException(409, "Upgrade Not Ready", "The prepared task is incomplete")
        return values

    def retry(self) -> dict[str, Any]:
        """Re-run the last failed upgrade with the release that is already staged.

        A rollback restores the deployment but keeps the staged material, so a retry needs no
        download: once the cause is fixed (a freed port, a pulled image) the same attempt can be
        started again with a single click.
        """
        state = self._read_state()
        run_id = str(state.get("run_id") or "").strip()
        retryable = (*FAILURE_STATES, "apply_interrupted", "download_failed")
        if state.get("state") not in retryable or not RUN_ID_PATTERN.match(run_id):
            raise CustomException(409, "Upgrade Not Retryable", "There is no failed upgrade to retry")
        if state.get("state") == "download_failed":
            # Nothing was staged, so a retry means downloading again.
            raise CustomException(409, "Upgrade Not Retryable", "The release has to be downloaded again")
        staging_dir = self.upgrade_root / "staging" / run_id
        if not (staging_dir / "docker-compose.yml").is_file() or not (staging_dir / "runner-upgrade.sh").is_file():
            raise CustomException(409, "Upgrade Not Retryable", "The staged release is no longer available")
        # Raises when the staged task is missing or tampered with, before any state changes.
        self._read_task(staging_dir / "task.env")
        self._write_state({
            "run_id": run_id,
            "state": "ready",
            "target_version": state.get("target_version"),
            "detail": "Upgrade is prepared",
            "log_path": str(self.upgrade_root / "logs" / f"{run_id}.log"),
        })
        logger.info(f"Upgrade {run_id} retried after {state.get('reason') or 'a failure'}")
        return self.apply()

    def apply(self) -> dict[str, Any]:
        lock = self._acquire_lock()
        try:
            state = self._read_state()
            if state.get("state") != "ready" or not state.get("run_id"):
                raise CustomException(409, "Upgrade Not Ready", "Prepare a newer version before starting the upgrade")
            run_id = str(state["run_id"])
            task_file = self.upgrade_root / "staging" / run_id / "task.env"
            task = self._read_task(task_file)
            if task["RUN_ID"] != run_id:
                raise CustomException(409, "Upgrade Not Ready", "The prepared task does not match its status")
            try:
                docker_client = docker.from_env()
                # The runner image is resolved through its tag and verified by digest: a mirror
                # pull records the digest under the mirror's repository, so the pinned reference
                # would not resolve on its own even though the content is the pinned one.
                require_local_image(docker_client, RUNNER_IMAGE_TAG, RUNNER_IMAGE_DIGEST)
                # A failed run deliberately keeps its runner container for diagnosis. Retrying the
                # same run id would clash with that leftover, so it is cleared first.
                self._clear_stale_runner(docker_client, run_id)
                docker_client.containers.run(
                    image=RUNNER_IMAGE_TAG,
                    command=["sh", f"{task['STAGING_DIR']}/runner-upgrade.sh", str(task_file)],
                    name=self._runner_container_name(run_id),
                    volumes={
                        "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"},
                        task["DATA_ROOT"]: {"bind": task["DATA_ROOT"], "mode": "rw"},
                        task["INSTALL_PATH"]: {"bind": task["INSTALL_PATH"], "mode": "rw"},
                    },
                    detach=True,
                    remove=False,
                    labels={"owner": "websoft9", "websoft9.upgrade.run_id": run_id},
                )
            except Exception as exc:
                raise CustomException(502, "Upgrade Runner Unavailable", f"Unable to start the upgrade runner: {exc}")
            self._write_state({
                **state,
                "state": "applying",
                "detail": "Upgrade runner started",
                "log_path": str(self.upgrade_root / "logs" / f"{run_id}.log"),
            })
            return self.status(run_id=run_id)
        finally:
            self._release_lock(lock)
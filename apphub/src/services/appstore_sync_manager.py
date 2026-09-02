from __future__ import annotations

import os
import subprocess
import sys
import json
import shutil
import datetime
import time
import tempfile
import importlib.util
from pathlib import Path

from src.core.exception import CustomException


_SYNC_LOCK_FILE = "/tmp/websoft9-appstore-sync.lock"


class AppStoreSyncManager:
    def __init__(self) -> None:
        self._default_script_path = self._resolve_default_script_path()
        self._default_state_path = self._resolve_default_state_path()

    @staticmethod
    def _resolve_default_script_path() -> str:
        configured_path = os.getenv("WEBSOFT9_PLATFORM_ASSET_SYNC_SCRIPT")
        if configured_path:
            return configured_path

        runtime_path = Path("/websoft9/script/platform-sync-runtime-assets.py")
        if runtime_path.exists():
            return str(runtime_path)

        workspace_path = Path(__file__).resolve().parents[3] / "docker" / "scripts" / "platform-sync-runtime-assets.py"
        return str(workspace_path)

    @staticmethod
    def _resolve_default_state_path() -> str:
        configured_path = os.getenv("WEBSOFT9_APP_STORE_SYNC_STATE")
        if configured_path:
            return configured_path

        data_root = os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data")
        persistent_path = Path(data_root) / "config" / "appstore_sync_state.json"
        persistent_path.parent.mkdir(parents=True, exist_ok=True)
        return str(persistent_path)

    def _load_sync_state(self) -> dict:
        state_path = Path(self._default_state_path)
        if not state_path.exists():
            return {}

        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _write_sync_state(self, payload: dict) -> None:
        state_path = Path(self._default_state_path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8")

    @staticmethod
    def _replace_tree(source: Path, target: Path) -> None:
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)

    def _build_candidate_manifests(self, candidate_root: Path) -> None:
        spec = importlib.util.spec_from_file_location("platform_sync_runtime_assets", self._default_script_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load app store manifest builder: {self._default_script_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.build_and_publish_app_store_manifests(candidate_root / "media", candidate_root / "library")

    @staticmethod
    def _backup_trees(targets: list[Path], backup_root: Path) -> dict[Path, Path | None]:
        backups: dict[Path, Path | None] = {}
        for index, target in enumerate(targets):
            if target.exists():
                backup = backup_root / str(index)
                shutil.copytree(target, backup)
                backups[target] = backup
            else:
                backups[target] = None
        return backups

    def _restore_trees(self, backups: dict[Path, Path | None]) -> None:
        for target, backup in backups.items():
            if target.exists():
                shutil.rmtree(target)
            if backup is not None:
                self._replace_tree(backup, target)

    @staticmethod
    def _resolve_default_snapshot_root() -> str:
        configured_path = os.getenv("WEBSOFT9_APP_STORE_SNAPSHOT_ROOT")
        if configured_path:
            return configured_path

        runtime_path = Path("/websoft9/appstore")
        if runtime_path.parent.exists():
            return str(runtime_path)

        workspace_path = Path(__file__).resolve().parents[3] / "appstore"
        return str(workspace_path)

    @staticmethod
    def _resolve_runtime_package_root(package_type: str) -> Path:
        env_map = {
            "media": "WEBSOFT9_MEDIA_ROOT",
            "library": "WEBSOFT9_LIBRARY_ROOT",
        }
        default_map = {
            "media": "/websoft9/media",
            "library": "/websoft9/library",
        }

        configured_path = os.getenv(env_map[package_type])
        if configured_path:
            return Path(configured_path)

        runtime_path = Path(default_map[package_type])
        if runtime_path.parent.exists():
            return runtime_path

        workspace_path = Path(__file__).resolve().parents[3] / package_type
        return workspace_path

    def get_state(self) -> dict:
        """Return the current sync state for consumer inspection."""
        state = self._load_sync_state()
        return {
            "channel": state.get("channel"),
            "datasetVersion": state.get("datasetVersion"),
            "catalogDatasetVersion": state.get("catalogDatasetVersion"),
            "libraryDatasetVersion": state.get("libraryDatasetVersion"),
            "generatedAt": state.get("generatedAt"),
            "lastSyncedAt": state.get("lastSyncedAt"),
            "syncMode": state.get("syncMode"),
            "updated": state.get("updated", False),
            "snapshotRoot": state.get("snapshotRoot"),
        }

    def list_versions(self) -> dict:
        current_state = self._load_sync_state()
        snapshot_root = Path(current_state.get("snapshotRoot") or self._resolve_default_snapshot_root())
        releases_root = snapshot_root / "releases"
        active_dataset = current_state.get("datasetVersion")

        versions: list[dict[str, object]] = []
        if releases_root.exists():
            for release_dir in sorted(
                [item for item in releases_root.iterdir() if item.is_dir()],
                key=lambda item: item.name,
                reverse=True,
            ):
                packages = sorted(child.name for child in release_dir.iterdir() if child.is_dir())
                versions.append(
                    {
                        "datasetVersion": release_dir.name,
                        "active": release_dir.name == active_dataset,
                        "packages": packages,
                        "path": str(release_dir),
                    }
                )

        return {
            "activeDatasetVersion": active_dataset,
            "snapshotRoot": str(snapshot_root),
            "versions": versions,
        }

    def activate(self, dataset_version: str, trigger: str = "manual") -> dict:
        if not dataset_version:
            raise CustomException(status_code=400, message="App Store Activate Failed", details="datasetVersion is required")

        current_state = self._load_sync_state()
        snapshot_root = Path(current_state.get("snapshotRoot") or self._resolve_default_snapshot_root())
        release_root = snapshot_root / "releases" / dataset_version
        current_root = snapshot_root / "current"

        if not release_root.exists() or not release_root.is_dir():
            raise CustomException(
                status_code=404,
                message="App Store Activate Failed",
                details=f"App Store dataset version not found: {dataset_version}",
            )

        required_packages = {package_type: release_root / package_type for package_type in ("media", "library")}
        if any(not source_dir.is_dir() for source_dir in required_packages.values()):
            raise CustomException(
                status_code=409,
                message="App Store Activate Failed",
                details=f"App Store dataset is incomplete: {dataset_version}",
            )

        with tempfile.TemporaryDirectory(prefix="websoft9-appstore-activate-") as temporary_directory:
            candidate_root = Path(temporary_directory) / "current"
            for package_type, source_dir in required_packages.items():
                self._replace_tree(source_dir, candidate_root / package_type)
            try:
                self._build_candidate_manifests(candidate_root)
            except Exception as exc:
                raise CustomException(
                    status_code=409,
                    message="App Store Activate Failed",
                    details=f"App Store dataset manifest validation failed: {exc}",
                ) from exc

            package_snapshot_paths: dict[str, dict[str, str]] = {}
            activated_packages: list[str] = []
            targets = [
                target
                for package_type in ("media", "library")
                for target in (current_root / package_type, self._resolve_runtime_package_root(package_type))
            ]
            backups = self._backup_trees(targets, Path(temporary_directory) / "backups")
            try:
                for package_type in ("media", "library"):
                    source_dir = candidate_root / package_type
                    active_snapshot_dir = current_root / package_type
                    runtime_target_dir = self._resolve_runtime_package_root(package_type)
                    self._replace_tree(source_dir, active_snapshot_dir)
                    self._replace_tree(active_snapshot_dir, runtime_target_dir)
                    package_snapshot_paths[package_type] = {
                        "staging": str(snapshot_root / "staging" / dataset_version / package_type),
                        "release": str(release_root / package_type),
                        "current": str(active_snapshot_dir),
                    }
                    activated_packages.append(package_type)
            except Exception as exc:
                try:
                    self._restore_trees(backups)
                except Exception as rollback_exc:
                    raise CustomException(
                        status_code=500,
                        message="App Store Activate Failed",
                        details=f"App Store activation and rollback failed: {exc}; rollback: {rollback_exc}",
                    ) from rollback_exc
                raise CustomException(
                    status_code=500,
                    message="App Store Activate Failed",
                    details=f"App Store activation failed and was rolled back: {exc}",
                ) from exc

        if not activated_packages:
            raise CustomException(
                status_code=404,
                message="App Store Activate Failed",
                details=f"App Store dataset version has no activatable packages: {dataset_version}",
            )

        updated_state = {
            **current_state,
            "datasetVersion": dataset_version,
            "lastSyncedAt": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "syncMode": trigger,
            "updated": True,
            "snapshotRoot": str(snapshot_root),
            "snapshots": package_snapshot_paths,
            "activatedPackages": activated_packages,
        }
        self._write_sync_state(updated_state)

        return {
            "status": "success",
            "trigger": trigger,
            "datasetVersion": dataset_version,
            "snapshotRoot": str(snapshot_root),
            "activatedPackages": activated_packages,
        }

    def _is_sync_running(self) -> bool:
        lock_file = Path(_SYNC_LOCK_FILE)
        if not lock_file.exists():
            return False
        try:
            pid = int(lock_file.read_text(encoding="utf-8").strip())
            proc_stat = Path(f"/proc/{pid}/stat")
            if not proc_stat.exists():
                lock_file.unlink(missing_ok=True)
                return False

            stat_fields = proc_stat.read_text(encoding="utf-8").split()
            if len(stat_fields) >= 3 and stat_fields[2] == "Z":
                lock_file.unlink(missing_ok=True)
                return False

            os.kill(pid, 0)  # signal 0 just checks existence
            return True
        except (ValueError, OSError):
            lock_file.unlink(missing_ok=True)
            return False

    def _mark_sync_start(self, pid: int) -> None:
        Path(_SYNC_LOCK_FILE).write_text(str(pid), encoding="utf-8")

    def _mark_sync_end(self) -> None:
        Path(_SYNC_LOCK_FILE).unlink(missing_ok=True)

    def get_sync_status(self) -> dict:
        if self._is_sync_running():
            return {"status": "running"}
        state = self._load_sync_state()
        return {
            "status": "idle",
            "lastSyncedAt": state.get("lastSyncedAt"),
            "datasetVersion": state.get("datasetVersion"),
        }

    def sync(self, trigger: str = "manual", channel: str | None = None, package_types: str | None = None, force_refresh: bool = False, background: bool = True) -> dict:
        script_path = Path(self._default_script_path)
        if not script_path.exists():
            raise CustomException(
                status_code=500,
                message="App Store Sync Failed",
                details=f"App Store sync script not found: {script_path}",
            )

        if package_types and {item.strip() for item in package_types.split(",") if item.strip()} != {"media", "library"}:
            raise CustomException(
                status_code=400,
                message="App Store Sync Failed",
                details="App Store sync requires both media and library packages",
            )

        env = os.environ.copy()
        env["WEBSOFT9_RUNTIME_ASSET_SYNC_MODE"] = trigger
        env["WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC"] = "1" if force_refresh else "0"

        if channel:
            env["WEBSOFT9_RUNTIME_ASSET_CHANNEL"] = channel

        if package_types:
            env["WEBSOFT9_RUNTIME_ASSET_TYPES"] = package_types

        env.setdefault("WEBSOFT9_APP_STORE_SYNC_STATE", self._default_state_path)

        if not background:
            # Synchronous mode – used by CLI and build steps
            previous_state = self._load_sync_state()
            process = subprocess.run(
                [sys.executable, str(script_path)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            stdout = process.stdout.strip()
            stderr = process.stderr.strip()
            output = "\n".join(item for item in [stdout, stderr] if item).strip()

            if process.returncode != 0:
                raise CustomException(
                    status_code=500,
                    message="App Store Sync Failed",
                    details=output or f"Sync process exited with code {process.returncode}",
                )

            current_state = self._load_sync_state()
            previous_dataset = previous_state.get("datasetVersion")
            current_dataset = current_state.get("datasetVersion")
            updated = previous_dataset != current_dataset or bool(current_state.get("updated"))

            return {
                "status": "success",
                "trigger": trigger,
                "channel": current_state.get("channel") or channel or "auto",
                "package_types": package_types or "media,library",
                "force_refresh": force_refresh,
                "datasetVersion": current_dataset,
                "generatedAt": current_state.get("generatedAt"),
                "updated": updated,
                "packageSyncPlan": current_state.get("packageSyncPlan") or {},
                "snapshotRoot": current_state.get("snapshotRoot"),
                "details": output or "App Store assets synchronized successfully",
            }

        # Background mode – spawn a lightweight wrapper that reaps the sync process
        # and clears the lock file when the job completes.
        log_path = Path("/tmp/websoft9-appstore-sync.log")
        wrapper_code = (
            "import os, subprocess, sys\n"
            "log_path, lock_path, script_path = sys.argv[1:4]\n"
            "exit_code = 0\n"
            "with open(log_path, 'a', encoding='utf-8') as log_file:\n"
            "    try:\n"
            "        result = subprocess.run([sys.executable, script_path], env=os.environ.copy(), stdout=log_file, stderr=subprocess.STDOUT, check=False)\n"
            "        exit_code = result.returncode\n"
            "    finally:\n"
            "        try:\n"
            "            os.unlink(lock_path)\n"
            "        except FileNotFoundError:\n"
            "            pass\n"
            "sys.exit(exit_code)\n"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", wrapper_code, str(log_path), _SYNC_LOCK_FILE, str(script_path)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        self._mark_sync_start(process.pid)

        return {
            "status": "accepted",
            "message": "App Store sync started in background.",
        }

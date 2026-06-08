from __future__ import annotations

import os
import subprocess
import sys
import json
import shutil
import datetime
from pathlib import Path

from src.core.exception import CustomException


class AppStoreSyncManager:
    def __init__(self) -> None:
        self._default_script_path = self._resolve_default_script_path()
        self._default_state_path = self._resolve_default_state_path()

    @staticmethod
    def _resolve_default_script_path() -> str:
        configured_path = os.getenv("WEBSOFT9_PLATFORM_ASSET_SYNC_SCRIPT")
        if configured_path:
            return configured_path

        runtime_path = Path("/websoft9/docker/scripts/platform-sync-runtime-assets.py")
        if runtime_path.exists():
            return str(runtime_path)

        workspace_path = Path(__file__).resolve().parents[3] / "docker" / "scripts" / "platform-sync-runtime-assets.py"
        return str(workspace_path)

    @staticmethod
    def _resolve_default_state_path() -> str:
        configured_path = os.getenv("WEBSOFT9_APP_STORE_SYNC_STATE")
        if configured_path:
            return configured_path

        runtime_path = Path("/websoft9/apphub/src/config/appstore_sync_state.json")
        if runtime_path.parent.exists():
            return str(runtime_path)

        workspace_path = Path(__file__).resolve().parents[1] / "config" / "appstore_sync_state.json"
        return str(workspace_path)

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

        package_snapshot_paths: dict[str, dict[str, str]] = {}
        activated_packages: list[str] = []
        for package_type in ("media", "library"):
            source_dir = release_root / package_type
            if not source_dir.exists() or not source_dir.is_dir():
                continue

            active_snapshot_dir = current_root / package_type
            runtime_target_dir = self._resolve_runtime_package_root(package_type)
            self._replace_tree(source_dir, active_snapshot_dir)
            self._replace_tree(active_snapshot_dir, runtime_target_dir)
            package_snapshot_paths[package_type] = {
                "staging": str(snapshot_root / "staging" / dataset_version / package_type),
                "release": str(source_dir),
                "current": str(active_snapshot_dir),
            }
            activated_packages.append(package_type)

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

    def sync(self, trigger: str = "manual", channel: str | None = None, package_types: str | None = None, force_refresh: bool = True) -> dict:
        script_path = Path(self._default_script_path)
        if not script_path.exists():
            raise CustomException(
                status_code=500,
                message="App Store Sync Failed",
                details=f"App Store sync script not found: {script_path}",
            )

        env = os.environ.copy()
        env["WEBSOFT9_RUNTIME_ASSET_SYNC_MODE"] = trigger
        env["WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC"] = "1" if force_refresh else "0"

        if channel:
            env["WEBSOFT9_RUNTIME_ASSET_CHANNEL"] = channel

        if package_types:
            env["WEBSOFT9_RUNTIME_ASSET_TYPES"] = package_types

        env.setdefault("WEBSOFT9_APP_STORE_SYNC_STATE", self._default_state_path)

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

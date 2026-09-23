import json
import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.modules.pop('src.services.appstore_sync_manager', None)
sys.modules.pop('src.core.exception', None)

exception_module = importlib.import_module('src.core.exception')
manager_module = importlib.import_module('src.services.appstore_sync_manager')

CustomException = exception_module.CustomException
AppStoreSyncManager = manager_module.AppStoreSyncManager


def test_sync_refuses_to_start_when_another_sync_is_running(monkeypatch):
    monkeypatch.setenv("WEBSOFT9_PLATFORM_ASSET_SYNC_SCRIPT", __file__)
    manager = AppStoreSyncManager()
    monkeypatch.setattr(manager, "_is_sync_running", lambda: True)

    with pytest.raises(CustomException) as error:
        manager.sync(trigger="manual", package_types="media,library", background=False)

    assert error.value.status_code == 409
    assert "already running" in error.value.details


def test_foreground_sync_publishes_and_clears_the_running_marker(tmp_path, monkeypatch):
    state_path = tmp_path / "config" / "appstore_sync_state.json"
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))
    monkeypatch.setenv("WEBSOFT9_PLATFORM_ASSET_SYNC_SCRIPT", __file__)
    manager = AppStoreSyncManager()
    marker_during_run = []

    class FakeCompletedProcess:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(*_args, **_kwargs):
        marker_during_run.append(manager.is_sync_running())
        return FakeCompletedProcess()

    monkeypatch.setattr(manager_module.subprocess, "run", fake_run)

    result = manager.sync(trigger="cli", package_types="media,library", background=False)

    assert marker_during_run == [True]
    assert manager.is_sync_running() is False
    assert result["status"] == "success"


def test_get_state_exposes_appstore_incompatibility(tmp_path, monkeypatch):
    state_path = tmp_path / "config" / "appstore_sync_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"syncStatus": "incompatible", "incompatibility": {"message": "Please upgrade Websoft9"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))

    state = AppStoreSyncManager().get_state()

    assert state["syncStatus"] == "incompatible"
    assert state["incompatibility"] == {"message": "Please upgrade Websoft9"}

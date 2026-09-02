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


def test_list_versions_returns_sorted_releases_and_active_dataset(tmp_path, monkeypatch):
    snapshot_root = tmp_path / "appstore"
    releases_root = snapshot_root / "releases"
    (releases_root / "2026.06.08.120000" / "media").mkdir(parents=True)
    (releases_root / "2026.06.08.110000" / "library").mkdir(parents=True)
    state_path = tmp_path / "config" / "appstore_sync_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "datasetVersion": "2026.06.08.110000",
                "snapshotRoot": str(snapshot_root),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))
    manager = AppStoreSyncManager()

    result = manager.list_versions()

    assert result["activeDatasetVersion"] == "2026.06.08.110000"
    assert [item["datasetVersion"] for item in result["versions"]] == [
        "2026.06.08.120000",
        "2026.06.08.110000",
    ]
    assert result["versions"][1]["active"] is True


def test_activate_switches_current_snapshot_and_runtime_roots(tmp_path, monkeypatch):
    snapshot_root = tmp_path / "appstore"
    release_root = snapshot_root / "releases" / "2026.06.08.110000"
    (release_root / "media" / "json").mkdir(parents=True)
    (release_root / "library" / "apps" / "mysql").mkdir(parents=True)
    (release_root / "media" / "json" / "product_en.json").write_text('[{"key":"mysql","title":"MySQL"}]\n', encoding="utf-8")
    (release_root / "media" / "json" / "product_zh.json").write_text('[{"key":"mysql","title":"MySQL"}]\n', encoding="utf-8")
    (release_root / "library" / "apps" / "mysql" / ".env").write_text("W9_HTTP_PORT_SET=3306\n", encoding="utf-8")
    (release_root / "library" / "apps" / "mysql" / "variables.json").write_text('{"edition":[{"dist":"community","version":"8.0"}]}\n', encoding="utf-8")

    runtime_media = tmp_path / "runtime" / "media"
    runtime_library = tmp_path / "runtime" / "library"
    (runtime_media / "json").mkdir(parents=True)
    (runtime_library / "apps" / "mysql").mkdir(parents=True)
    (runtime_media / "json" / "product_en.json").write_text('{"version":"current"}\n', encoding="utf-8")
    (runtime_library / "apps" / "mysql" / ".env").write_text("MYSQL_CURRENT=1\n", encoding="utf-8")

    state_path = tmp_path / "config" / "appstore_sync_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "datasetVersion": "2026.06.08.120000",
                "snapshotRoot": str(snapshot_root),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))
    monkeypatch.setenv("WEBSOFT9_MEDIA_ROOT", str(runtime_media))
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(runtime_library))

    manager = AppStoreSyncManager()
    result = manager.activate("2026.06.08.110000", trigger="rollback")

    assert result["datasetVersion"] == "2026.06.08.110000"
    assert sorted(result["activatedPackages"]) == ["library", "media"]
    assert (snapshot_root / "current" / "media" / "json" / "product_en.json").read_text(encoding="utf-8") == '[{"key":"mysql","title":"MySQL"}]\n'
    assert json.loads((runtime_media / "json" / "app-store-manifest_en.json").read_text(encoding="utf-8"))["apps"][0]["key"] == "mysql"
    assert (runtime_library / "apps" / "mysql" / ".env").read_text(encoding="utf-8") == "W9_HTTP_PORT_SET=3306\n"

    updated_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert updated_state["datasetVersion"] == "2026.06.08.110000"
    assert updated_state["activatedPackages"] == ["media", "library"] or updated_state["activatedPackages"] == ["library", "media"]


def test_activate_keeps_current_data_when_candidate_manifest_is_invalid(tmp_path, monkeypatch):
    snapshot_root = tmp_path / "appstore"
    release_root = snapshot_root / "releases" / "2026.06.08.110000"
    (release_root / "media" / "json").mkdir(parents=True)
    (release_root / "library" / "apps" / "mysql").mkdir(parents=True)
    (release_root / "media" / "json" / "product_en.json").write_text('[]\n', encoding="utf-8")
    (release_root / "library" / "apps" / "mysql" / ".env").write_text("W9_HTTP_PORT_SET=3306\n", encoding="utf-8")

    runtime_media = tmp_path / "runtime" / "media"
    runtime_library = tmp_path / "runtime" / "library"
    (runtime_media / "json").mkdir(parents=True)
    (runtime_library / "apps").mkdir(parents=True)
    (runtime_media / "json" / "product_en.json").write_text('{"version":"current"}\n', encoding="utf-8")
    (runtime_library / "apps" / "current").mkdir()
    state_path = tmp_path / "config" / "appstore_sync_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"datasetVersion": "2026.06.08.120000", "snapshotRoot": str(snapshot_root)}), encoding="utf-8")

    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))
    monkeypatch.setenv("WEBSOFT9_MEDIA_ROOT", str(runtime_media))
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(runtime_library))

    with __import__("pytest").raises(CustomException) as exc_info:
        AppStoreSyncManager().activate("2026.06.08.110000")

    assert exc_info.value.status_code == 409
    assert (runtime_media / "json" / "product_en.json").read_text(encoding="utf-8") == '{"version":"current"}\n'
    assert (runtime_library / "apps" / "current").is_dir()


def test_activate_restores_runtime_and_current_when_replacement_fails(tmp_path, monkeypatch):
    snapshot_root = tmp_path / "appstore"
    release_root = snapshot_root / "releases" / "2026.06.08.110000"
    (release_root / "media" / "json").mkdir(parents=True)
    (release_root / "library" / "apps" / "mysql").mkdir(parents=True)
    for locale in ("en", "zh"):
        (release_root / "media" / "json" / f"product_{locale}.json").write_text('[{"key":"mysql"}]', encoding="utf-8")
    (release_root / "library" / "apps" / "mysql" / ".env").write_text("W9_HTTP_PORT_SET=3306\n", encoding="utf-8")
    (release_root / "library" / "apps" / "mysql" / "variables.json").write_text('{"edition":[{"dist":"community","version":"8.0"}]}', encoding="utf-8")

    runtime_media = tmp_path / "runtime" / "media"
    runtime_library = tmp_path / "runtime" / "library"
    current_media = snapshot_root / "current" / "media"
    current_library = snapshot_root / "current" / "library"
    for directory, marker in ((runtime_media, "runtime-media"), (runtime_library, "runtime-library"), (current_media, "current-media"), (current_library, "current-library")):
        directory.mkdir(parents=True)
        (directory / "marker").write_text(marker, encoding="utf-8")
    state_path = tmp_path / "config" / "appstore_sync_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"datasetVersion": "2026.06.08.120000", "snapshotRoot": str(snapshot_root)}), encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))
    monkeypatch.setenv("WEBSOFT9_MEDIA_ROOT", str(runtime_media))
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(runtime_library))

    manager = AppStoreSyncManager()
    original_replace_tree = manager._replace_tree
    replacements = 0

    def fail_before_library_current(source, target):
        nonlocal replacements
        replacements += 1
        if replacements == 5:
            raise OSError("injected replacement failure")
        original_replace_tree(source, target)

    monkeypatch.setattr(manager, "_replace_tree", fail_before_library_current)
    with pytest.raises(CustomException) as exc_info:
        manager.activate("2026.06.08.110000")

    assert "rolled back" in exc_info.value.details
    for directory, marker in ((runtime_media, "runtime-media"), (runtime_library, "runtime-library"), (current_media, "current-media"), (current_library, "current-library")):
        assert (directory / "marker").read_text(encoding="utf-8") == marker
    assert json.loads(state_path.read_text(encoding="utf-8"))["datasetVersion"] == "2026.06.08.120000"


def test_activate_rejects_unknown_dataset_version(tmp_path, monkeypatch):
    state_path = tmp_path / "config" / "appstore_sync_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"snapshotRoot": str(tmp_path / "appstore")}), encoding="utf-8")
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))

    manager = AppStoreSyncManager()

    try:
        manager.activate("2026.06.08.999999")
        assert False, "Expected CustomException"
    except CustomException as exc:
        assert exc.status_code == 404
        assert "dataset version not found" in exc.details
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from test_local_app_store import _write_app
from test_platform_sync_dictionary import _zip_bytes, runtime_assets
from test_platform_sync_dictionary import contract_v2 as contract_v2

from src.core.exception import CustomException
from src.services import local_app_store
from src.services.app_manager import AppManger
from src.services.appstore_availability import get_appstore_assets_state, require_appstore_assets
from src.services.appstore_sync_manager import AppStoreSyncManager
from src.services.common_check import install_validate


def _read_state(tmp_path):
    return json.loads((tmp_path / "state.json").read_bytes())


@pytest.mark.parametrize("mode", ["build", "runtime"])
@pytest.mark.parametrize("layout", ["flat", "json"])
@pytest.mark.parametrize(("root_contract", "library_contract"), [("1", "1"), ("1", "2"), ("2", "2")])
def test_publisher_catalog_layout_and_older_json_layout(
    tmp_path, monkeypatch, contract_v2, mode, layout, root_contract, library_contract
):
    base, payloads, artifacts, _, _ = contract_v2
    root = payloads[f"{base}/manifests/appstore-manifest.json"]
    root["schemaVersion"] = root_contract
    root["library"]["schemaVersion"] = library_contract
    for path in ("manifest.json", "apps-index.json", "apps-delta.json"):
        payloads[f"{base}/library/{path}"]["schemaVersion"] = library_contract
    (tmp_path / "source-library/library.json").write_text(json.dumps({"schemaVersion": library_contract}))
    artifacts[f"{base}/library/full/latest.zip"] = _zip_bytes(tmp_path / "source-library", "library")
    if layout == "json":
        artifacts[f"{base}/catalog/full/latest.zip"] = _zip_bytes(tmp_path / "source-media", "media")
    monkeypatch.setenv("WEBSOFT9_RUNTIME_ASSET_SYNC_MODE", mode)

    assert runtime_assets.main() == 0
    state = _read_state(tmp_path)
    assert state["syncStatus"] == "ready"
    runtime_assets.validate_saved_asset_snapshot(state, tmp_path / "media", tmp_path / "library")


def test_unchanged_dataset_does_not_write_assets_back_up_or_toggle_availability(tmp_path, monkeypatch, contract_v2):
    assert runtime_assets.main() == 0
    before = _read_state(tmp_path)
    availability = runtime_assets.runtime_assets_status_path().read_bytes()

    def unexpected_write(*args, **kwargs):
        raise AssertionError("an unchanged complete dataset must not enter activation")

    for name in (
        "backup_trees",
        "write_runtime_assets_status",
        "publish_json_files",
        "build_and_publish_app_store_manifests",
        "stage_snapshot",
        "download_file",
    ):
        monkeypatch.setattr(runtime_assets, name, unexpected_write)
    assert runtime_assets.main() == 0
    assert runtime_assets.runtime_assets_status_path().read_bytes() == availability
    assert _read_state(tmp_path)["assetDigests"] == before["assetDigests"]
    assert _read_state(tmp_path)["updated"] is False


@pytest.mark.parametrize("fail_download", [False, True])
def test_full_prefetch_preserves_ready_baseline_until_activation(tmp_path, monkeypatch, contract_v2, fail_download):
    assert runtime_assets.main() == 0
    before = _read_state(tmp_path)
    original = [runtime_assets.tree_content_fingerprint(tmp_path / kind) for kind in ("media", "library", "snapshots")]
    monkeypatch.setenv("WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC", "1")
    real_download = runtime_assets.download_file
    real_apply = runtime_assets.apply_package_source
    events = []

    def checked_download(url, target):
        assert get_appstore_assets_state()["status"] == "ready"
        require_appstore_assets()
        events.append("download")
        if fail_download:
            raise runtime_assets.AppStoreTransientError("publisher offline")
        real_download(url, target)

    def checked_activation(*args, **kwargs):
        assert get_appstore_assets_state()["status"] == "updating"
        with pytest.raises(CustomException) as error:
            require_appstore_assets()
        assert error.value.status_code == 503
        events.append("activation")
        return real_apply(*args, **kwargs)

    monkeypatch.setattr(runtime_assets, "download_file", checked_download)
    monkeypatch.setattr(runtime_assets, "apply_package_source", checked_activation)
    assert runtime_assets.main() == int(fail_download)
    assert "download" in events
    assert ("activation" in events) is not fail_download
    assert get_appstore_assets_state()["status"] == "ready"
    assert _read_state(tmp_path)["datasetVersion"] == before["datasetVersion"]
    if fail_download:
        assert _read_state(tmp_path)["syncStatus"] == "failed"
        assert [
            runtime_assets.tree_content_fingerprint(tmp_path / kind) for kind in ("media", "library", "snapshots")
        ] == original


def test_snapshot_metadata_repair_does_not_use_the_no_change_shortcut(tmp_path, monkeypatch, contract_v2):
    assert runtime_assets.main() == 0
    current = tmp_path / "snapshots/current/library/apps-index.json"
    current.write_text("{}")
    events = []
    real_write = runtime_assets.write_runtime_assets_status

    def record_status(status, *args, **kwargs):
        events.append(status)
        return real_write(status, *args, **kwargs)

    monkeypatch.setattr(runtime_assets, "write_runtime_assets_status", record_status)
    assert runtime_assets.main() == 0
    assert events == ["updating", "ready"]
    assert json.loads(current.read_bytes()) == _read_state(tmp_path)["manifests"]["appsIndex"]


def test_official_refresh_uses_verified_state_and_does_not_rewrite_identical_manifests(tmp_path, contract_v2):
    assert runtime_assets.main() == 0
    before = _read_state(tmp_path)
    availability = runtime_assets.runtime_assets_status_path().read_bytes()
    custom = tmp_path / "custom"
    _write_app(custom, "canvas")
    report = local_app_store.reload_app_store_catalog(custom)
    assert report["official"] == {"loaded": {"zh": 1, "en": 1}, "errors": []}
    assert report["custom"]["loaded"] == 1
    assert _read_state(tmp_path) == before
    assert runtime_assets.runtime_assets_status_path().read_bytes() == availability
    assert runtime_assets.main() == 0
    assert _read_state(tmp_path)["updated"] is False


@pytest.mark.parametrize("blocked", ["locked", "unavailable", "updating", "damaged"])
def test_official_refresh_reports_untrusted_or_busy_assets_without_blocking_custom(tmp_path, contract_v2, blocked):
    assert runtime_assets.main() == 0
    before = _read_state(tmp_path)
    custom = tmp_path / "custom"
    _write_app(custom, "canvas")
    lock = None
    if blocked == "locked":
        lock = runtime_assets.acquire_appstore_sync_lock(tmp_path)
        assert lock is not None
    elif blocked == "damaged":
        (tmp_path / "library/apps/wordpress/.env").write_text("corrupt payload")
    else:
        runtime_assets.write_runtime_assets_status(blocked)
    try:
        report = local_app_store.reload_app_store_catalog(custom)
    finally:
        if lock is not None:
            lock.close()
    assert report["official"]["errors"]
    assert report["custom"]["loaded"] == 1
    assert _read_state(tmp_path) == before
    if blocked == "damaged":
        assert get_appstore_assets_state()["status"] == "unavailable"


def _change_generated_manifest_builder(monkeypatch):
    original = runtime_assets.build_and_publish_app_store_manifests

    def build_changed(media, library):
        original(media, library)
        for locale in ("zh", "en"):
            path = media / "json" / f"app-store-manifest_{locale}.json"
            payload = json.loads(path.read_bytes())
            payload["buildNote"] = "new browsing projection"
            runtime_assets.publish_json_files({path: payload})

    monkeypatch.setattr(runtime_assets, "build_and_publish_app_store_manifests", build_changed)


def test_official_refresh_commits_changed_projection_with_matching_digests_and_snapshots(tmp_path, monkeypatch, contract_v2):
    assert runtime_assets.main() == 0
    before = _read_state(tmp_path)
    _change_generated_manifest_builder(monkeypatch)
    assert runtime_assets.reload_runtime_app_store_manifests() == {"loaded": {"zh": 1, "en": 1}, "errors": []}
    after = _read_state(tmp_path)
    assert after["datasetVersion"] == before["datasetVersion"]
    assert after["assetDigests"]["media"] != before["assetDigests"]["media"]
    assert after["assetDigests"]["library"] == before["assetDigests"]["library"]
    runtime_assets.validate_saved_asset_snapshot(after, tmp_path / "media", tmp_path / "library")
    for path in after["snapshots"]["media"].values():
        assert runtime_assets.tree_content_fingerprint(Path(path)) == after["assetDigests"]["media"]
    assert get_appstore_assets_state()["status"] == "ready"
    assert runtime_assets.main() == 0
    assert _read_state(tmp_path)["updated"] is False
    assert runtime_assets.recover_runtime_assets() == 0


@pytest.mark.parametrize("failure", ["snapshot", "state", "availability"])
def test_official_refresh_commit_failure_restores_projection_state_and_snapshots(tmp_path, monkeypatch, contract_v2, failure):
    assert runtime_assets.main() == 0
    before = _read_state(tmp_path)
    roots = [tmp_path / kind for kind in ("media", "library", "snapshots")]
    original = [runtime_assets.tree_content_fingerprint(root) for root in roots]
    _change_generated_manifest_builder(monkeypatch)
    real_write = runtime_assets.write_sync_state
    real_stage = runtime_assets.stage_snapshot

    def fail_write(path, payload):
        if failure == "state" and path == tmp_path / "state.json" and payload["assetDigests"] != before["assetDigests"]:
            raise OSError("refresh state write failed")
        if failure == "availability" and path == runtime_assets.runtime_assets_status_path() and payload["status"] == "ready":
            raise OSError("refresh availability write failed")
        return real_write(path, payload)

    def fail_stage(*args):
        if failure == "snapshot":
            raise OSError("refresh snapshot write failed")
        return real_stage(*args)

    monkeypatch.setattr(runtime_assets, "write_sync_state", fail_write)
    monkeypatch.setattr(runtime_assets, "stage_snapshot", fail_stage)
    with pytest.raises(OSError, match="refresh"):
        runtime_assets.reload_runtime_app_store_manifests()
    assert _read_state(tmp_path) == before
    assert [runtime_assets.tree_content_fingerprint(root) for root in roots] == original
    assert get_appstore_assets_state()["status"] == ("unavailable" if failure == "availability" else "ready")
    lock = runtime_assets.acquire_appstore_sync_lock(tmp_path)
    assert lock is not None
    lock.close()


def test_runtime_sync_refuses_unlocked_writes_and_keeps_verified_baseline(tmp_path, monkeypatch, contract_v2):
    assert runtime_assets.main() == 0
    before = _read_state(tmp_path)

    def broken_lock(*args):
        raise PermissionError("lock directory is not writable")

    monkeypatch.setattr(runtime_assets, "acquire_appstore_sync_lock", broken_lock)
    assert runtime_assets.main() == 1
    assert _read_state(tmp_path) == before
    assert get_appstore_assets_state()["status"] == "ready"


def _image_baseline(tmp_path, monkeypatch):
    image = tmp_path / "image"
    shutil.copytree(tmp_path / "snapshots", image)
    state = _read_state(tmp_path)
    state["snapshotRoot"] = str(image)
    state_path = image / "image-state.json"
    state_path.write_text(json.dumps(state))
    monkeypatch.setenv("WEBSOFT9_APPSTORE_IMAGE_STATE", str(state_path))
    return state


@pytest.mark.parametrize("remote", ["offline", "incompatible"])
@pytest.mark.parametrize(("root_contract", "library_contract"), [("1", "1"), ("1", "2"), ("2", "2")])
def test_recreation_restores_persistent_snapshot_before_a_failed_remote_update(
    tmp_path, monkeypatch, contract_v2, remote, root_contract, library_contract
):
    base, payloads, artifacts, _, _ = contract_v2
    root = payloads[f"{base}/manifests/appstore-manifest.json"]
    root["schemaVersion"] = root_contract
    root["library"]["schemaVersion"] = library_contract
    for path in ("manifest.json", "apps-index.json", "apps-delta.json"):
        payloads[f"{base}/library/{path}"]["schemaVersion"] = library_contract
    source = tmp_path / "source-library"
    (source / "library.json").write_text(json.dumps({"schemaVersion": library_contract}))
    artifacts[f"{base}/library/full/latest.zip"] = _zip_bytes(source, "library")
    assert runtime_assets.main() == 0
    expected = _read_state(tmp_path)
    (tmp_path / "library/apps/wordpress/.env").write_text("W9_HTTP_PORT_SET=70\n")
    (tmp_path / "library/library.json").write_text('{"schemaVersion":"1"}')
    media_link = tmp_path / "runtime-media"
    media_link.symlink_to(tmp_path / "media", target_is_directory=True)
    monkeypatch.setenv("WEBSOFT9_MEDIA_ROOT", str(media_link))
    monkeypatch.setenv("WEBSOFT9_APPSTORE_IMAGE_STATE", str(tmp_path / "missing-image-state.json"))

    def failed_remote(*args):
        if remote == "incompatible":
            raise runtime_assets.AppStoreCompatibilityError("unsupported root contract")
        raise runtime_assets.AppStoreTransientError("publisher offline")

    monkeypatch.setattr(runtime_assets, "download_verified_json", failed_remote)
    assert runtime_assets.recover_runtime_assets() == 0
    assert media_link.is_symlink()
    assert _read_state(tmp_path)["recovery"]["source"] == "persistent-snapshot"
    assert runtime_assets.tree_content_fingerprint(tmp_path / "library") == expected["assetDigests"]["library"]
    assert runtime_assets.tree_content_fingerprint(media_link) == expected["assetDigests"]["media"]
    assert runtime_assets.main() == 1
    assert _read_state(tmp_path)["datasetVersion"] == expected["datasetVersion"]
    assert get_appstore_assets_state()["status"] == "ready"
    assert AppStoreSyncManager().get_state()["assetsDatasetVersion"] == expected["datasetVersion"]
    require_appstore_assets()


def test_image_fallback_restores_both_components_instead_of_blessing_mixed_assets(tmp_path, monkeypatch, contract_v2):
    base, payloads, artifacts, requests, downloads = contract_v2
    assert runtime_assets.main() == 0
    image_state = _image_baseline(tmp_path, monkeypatch)
    source = tmp_path / "source-library"
    (source / "apps/wordpress/.env").write_text("W9_HTTP_PORT_SET=90\n")
    payloads[f"{base}/manifests/appstore-manifest.json"]["datasetVersion"] = "d" * 16
    payloads[f"{base}/manifests/appstore-manifest.json"]["library"]["datasetVersion"] = "e" * 16
    payloads[f"{base}/library/manifest.json"].update(datasetVersion="e" * 16, supportsPartialUpdate=False)
    payloads[f"{base}/library/apps-index.json"]["datasetVersion"] = "e" * 16
    payloads[f"{base}/library/apps-index.json"]["apps"][0]["hash"] = runtime_assets.app_content_fingerprint(
        source / "apps/wordpress", "wordpress"
    )
    artifacts[f"{base}/library/full/latest.zip"] = _zip_bytes(source, "library")
    assert runtime_assets.main() == 0
    assert _read_state(tmp_path)["datasetVersion"] != image_state["datasetVersion"]
    shutil.rmtree(tmp_path / "snapshots")
    (tmp_path / "library/apps/wordpress").rename(tmp_path / "library/apps/old-image-app")
    requests.clear()
    downloads.clear()
    assert runtime_assets.recover_runtime_assets() == 0
    restored = _read_state(tmp_path)
    assert restored["recovery"]["source"] == "image-baseline"
    assert restored["datasetVersion"] == image_state["datasetVersion"]
    for kind in ("media", "library"):
        assert runtime_assets.tree_content_fingerprint(tmp_path / kind) == image_state["assetDigests"][kind]
    assert requests == downloads == []


@pytest.mark.parametrize("damage", ["media", "library", "provenance", "image-contract"])
def test_no_complete_snapshot_blocks_official_consumers_but_does_not_replace_mixed_files(
    tmp_path, monkeypatch, contract_v2, damage
):
    assert runtime_assets.main() == 0
    state_path = tmp_path / "state.json"
    state = _read_state(tmp_path)
    if damage == "provenance":
        state.pop("assetDigests")
        state_path.write_text(json.dumps(state))
    else:
        for root in (
            tmp_path / damage if damage in {"media", "library"} else tmp_path / "library",
            tmp_path / "snapshots/releases" / state["datasetVersion"] / ("media" if damage == "media" else "library"),
        ):
            (root / "unexpected.json").write_text('{"unverified":true}')
    monkeypatch.setenv("WEBSOFT9_APPSTORE_IMAGE_STATE", str(tmp_path / "missing-image.json"))
    if damage == "image-contract":
        image_state = _image_baseline(tmp_path, monkeypatch)
        image_state["schemaVersion"] = image_state["manifests"]["root"]["schemaVersion"] = "999"
        Path(os.environ["WEBSOFT9_APPSTORE_IMAGE_STATE"]).write_text(json.dumps(image_state))
    before = {kind: runtime_assets.tree_content_fingerprint(tmp_path / kind) for kind in ("media", "library")}
    assert runtime_assets.recover_runtime_assets() == 1
    assert get_appstore_assets_state()["status"] == "unavailable"
    for kind in ("media", "library"):
        assert runtime_assets.tree_content_fingerprint(tmp_path / kind) == before[kind]
    for operation in (
        require_appstore_assets,
        lambda: AppManger().get_available_apps("en"),
        lambda: AppManger().get_catalog_apps("en"),
        lambda: install_validate(SimpleNamespace(), None),
        lambda: AppManger().install_app(SimpleNamespace()),
        lambda: AppManger()._install_app(SimpleNamespace()),
    ):
        with pytest.raises(CustomException) as error:
            operation()
        assert error.value.status_code == 503
        assert error.value.message == "App Store Assets Unavailable"


def test_recovery_write_failure_cannot_leave_a_ready_marker(tmp_path, monkeypatch, contract_v2):
    assert runtime_assets.main() == 0
    original = _read_state(tmp_path)
    (tmp_path / "library/library.json").write_text('{"schemaVersion":"1"}')
    real_replace = runtime_assets.replace_tree

    def failed_library(source, target):
        if target == tmp_path / "library":
            raise OSError("read-only library")
        return real_replace(source, target)

    monkeypatch.setattr(runtime_assets, "replace_tree", failed_library)
    assert runtime_assets.recover_runtime_assets() == 1
    assert get_appstore_assets_state()["status"] == "unavailable"
    assert _read_state(tmp_path) == original


def test_new_online_sync_can_repair_an_unavailable_installation(tmp_path, monkeypatch, contract_v2):
    base, _, _, _, downloads = contract_v2
    assert runtime_assets.main() == 0
    state = _read_state(tmp_path)
    state.pop("assetDigests")
    (tmp_path / "state.json").write_text(json.dumps(state))
    (tmp_path / "library/apps/wordpress/.env").write_text("old-image-library\n")
    monkeypatch.setenv("WEBSOFT9_APPSTORE_IMAGE_STATE", str(tmp_path / "missing-image.json"))
    assert runtime_assets.recover_runtime_assets() == 1
    assert get_appstore_assets_state()["status"] == "unavailable"
    downloads.clear()
    assert runtime_assets.main() == 0
    assert f"{base}/catalog/full/latest.zip" in downloads
    assert f"{base}/library/full/latest.zip" in downloads
    assert get_appstore_assets_state()["status"] == "ready"
    require_appstore_assets()


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "not json",
        "{}",
        '{"status":"ready"}',
        '{"status":"updating"}',
        '{"status":[]}',
        '{"status":"ready","datasetVersion":" "}',
    ],
)
def test_missing_or_invalid_boot_marker_is_fail_closed(tmp_path, monkeypatch, payload):
    path = tmp_path / "runtime-marker.json"
    monkeypatch.setenv("WEBSOFT9_APPSTORE_RUNTIME_STATE_FILE", str(path))
    if payload is not None:
        path.write_text(payload)
    with pytest.raises(CustomException) as error:
        require_appstore_assets()
    assert error.value.status_code == 503


def test_default_runtime_snapshots_live_on_the_persistent_data_volume(tmp_path, monkeypatch, contract_v2):
    monkeypatch.delenv("WEBSOFT9_APP_STORE_SNAPSHOT_ROOT")
    monkeypatch.setenv("WEBSOFT9_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("WEBSOFT9_APPSTORE_IMAGE_STATE", str(tmp_path / "missing-image.json"))
    assert runtime_assets.main() == 0
    expected = tmp_path / "data/appstore"
    state = _read_state(tmp_path)
    assert state["snapshotRoot"] == str(expected)
    for kind in ("media", "library"):
        assert (expected / "releases" / state["datasetVersion"] / kind).is_dir()
    runtime_assets.runtime_assets_status_path().unlink()
    assert runtime_assets.recover_runtime_assets() == 0
    assert get_appstore_assets_state()["status"] == "ready"


def test_external_database_precheck_cannot_read_unverified_official_templates():
    from src.api.v1.routers.app import test_external_database_install_connection as precheck

    runtime_assets.write_runtime_assets_status("unavailable")
    with pytest.raises(CustomException) as error:
        precheck(SimpleNamespace())
    assert error.value.status_code == 503


@pytest.mark.parametrize("invalid", ['{"datasetVersion":[]}', "not json", "[]"])
def test_invalid_persistent_state_does_not_prevent_verified_image_recovery(tmp_path, monkeypatch, contract_v2, invalid):
    assert runtime_assets.main() == 0
    expected = _image_baseline(tmp_path, monkeypatch)
    (tmp_path / "state.json").write_text(invalid)
    assert runtime_assets.recover_runtime_assets() == 0
    state = _read_state(tmp_path)
    assert state["recovery"]["source"] == "image-baseline"
    assert state["datasetVersion"] == expected["datasetVersion"]


def test_empty_library_path_does_not_bypass_the_official_gate():
    runtime_assets.write_runtime_assets_status("unavailable")
    for operation in (
        lambda: install_validate(SimpleNamespace(), None, ""),
        lambda: AppManger().install_app(SimpleNamespace(), library_path=""),
        lambda: AppManger()._install_app(SimpleNamespace(), library_path=""),
    ):
        with pytest.raises(CustomException) as error:
            operation()
        assert error.value.status_code == 503


def test_unavailable_official_assets_do_not_gate_local_library_validation(monkeypatch, tmp_path):
    runtime_assets.write_runtime_assets_status("unavailable")
    from src.services import common_check

    def local_validation(app_name, version, library_path):
        assert library_path == str(tmp_path)
        raise CustomException(400, "Local validation reached", "local template validation")

    monkeypatch.setattr(common_check, "PortainerManager", lambda: None)
    monkeypatch.setattr(common_check, "GiteaManager", lambda: None)
    monkeypatch.setattr(common_check, "check_appName_and_appVersion", local_validation)
    app = SimpleNamespace(
        app_name="custom", edition=SimpleNamespace(version="1"), proxy_enabled=False, domain_names=[], app_id="custom"
    )
    with pytest.raises(CustomException) as error:
        install_validate(app, None, str(tmp_path))
    assert error.value.message == "Local validation reached"


def test_cached_official_catalog_cannot_bypass_runtime_gate(monkeypatch):
    manager = AppManger()
    monkeypatch.setattr(manager, "_cache", {"available_apps_en_all": [{"key": "stale-app"}]})
    runtime_assets.write_runtime_assets_status("unavailable")
    with pytest.raises(CustomException) as error:
        manager.get_available_apps("en")
    assert error.value.status_code == 503


def test_availability_write_failure_still_records_failure_and_invalidates_the_marker(tmp_path, monkeypatch, contract_v2):
    assert runtime_assets.main() == 0
    monkeypatch.setenv("WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC", "1")
    original = _read_state(tmp_path)
    real_write = runtime_assets.write_sync_state
    marker = runtime_assets.runtime_assets_status_path()

    def failed_ready_write(path, payload):
        if path == marker and payload.get("status") == "ready":
            raise OSError("runtime marker write failed")
        return real_write(path, payload)

    monkeypatch.setattr(runtime_assets, "write_sync_state", failed_ready_write)
    assert runtime_assets.main() == 1
    assert _read_state(tmp_path)["datasetVersion"] == original["datasetVersion"]
    assert _read_state(tmp_path)["syncStatus"] == "failed"
    assert get_appstore_assets_state()["status"] == "unavailable"


@pytest.mark.parametrize("failure", ["state", "availability", "snapshot"])
def test_recovery_commit_failure_restores_state_and_all_destination_snapshots(tmp_path, monkeypatch, contract_v2, failure):
    assert runtime_assets.main() == 0
    before = _read_state(tmp_path)
    (tmp_path / "library/library.json").write_text('{"schemaVersion":"1"}')
    roots = [tmp_path / kind for kind in ("media", "library", "snapshots")]
    original = [runtime_assets.tree_content_fingerprint(root) for root in roots]
    real_write = runtime_assets.write_sync_state
    real_snapshot = runtime_assets.stage_snapshot
    marker = runtime_assets.runtime_assets_status_path()

    def failed_commit(path, payload):
        if (failure == "state" and path == tmp_path / "state.json" and "recovery" in payload) or (
            failure == "availability" and path == marker and payload.get("status") == "ready"
        ):
            raise OSError("recovery commit failed")
        return real_write(path, payload)

    def failed_snapshot(source, snapshot_root, dataset_version, kind):
        if failure == "snapshot" and kind == "library":
            raise OSError("snapshot commit failed")
        return real_snapshot(source, snapshot_root, dataset_version, kind)

    monkeypatch.setattr(runtime_assets, "write_sync_state", failed_commit)
    monkeypatch.setattr(runtime_assets, "stage_snapshot", failed_snapshot)
    assert runtime_assets.recover_runtime_assets() == 1
    assert _read_state(tmp_path) == before
    assert [runtime_assets.tree_content_fingerprint(root) for root in roots] == original
    assert get_appstore_assets_state()["status"] == "unavailable"


def test_accepted_install_is_marked_failed_if_assets_become_unavailable_before_the_worker_starts():
    from src.services.app_status import appInstallingError, start_app_installation

    tracking_id = start_app_installation("gatecheck", "wordpress")
    runtime_assets.write_runtime_assets_status("updating")
    with pytest.raises(CustomException) as error:
        AppManger().install_app(
            SimpleNamespace(app_id="gatecheck"),
            tracked_app_id="gatecheck",
            tracking_id=tracking_id,
        )
    assert error.value.status_code == 503
    assert tracking_id in appInstallingError


def test_entrypoint_recovers_before_starting_consumers_even_when_recovery_fails(tmp_path):
    script = Path(__file__).resolve().parents[2] / "docker/scripts/platform-entrypoint.sh"
    text = script.read_text().rstrip()
    assert text.endswith('main "$@"')
    trace = tmp_path / "trace"
    recovery = tmp_path / "recover.sh"
    recovery.write_text('#!/bin/bash\necho "recover:$1" >> "$TRACE"\nexit 1\n')
    recovery.chmod(0o700)
    harness = tmp_path / "entrypoint.sh"
    harness.write_text(
        text[: -len('main "$@"')]
        + """
ensure_data_managed_paths() { :; }
log_event() { :; }
write_status() { :; }
sync_runtime_config() { :; }
ensure_product_runtime_state() { :; }
write_appstore_startup_state() { :; }
start_supervisor() { echo supervisor >> "$TRACE"; }
sync_appstore_assets() { echo remote >> "$TRACE"; }
ensure_platform_network() { :; }
start_apphub_core() { :; }
prepull_volume_backup_image() { :; }
bootstrap_product_auth() { :; }
bootstrap_platform_gateway() { :; }
bootstrap_gitea() { :; }
bootstrap_portainer() { :; }
bootstrap_nginx_proxy_manager() { :; }
update_runtime_status() { :; }
monitor_runtime() { :; }
shutdown_supervisor() { :; }
main
"""
    )
    result = subprocess.run(
        ["bash", str(harness)],
        env={
            **os.environ,
            "TRACE": str(trace),
            "WEBSOFT9_PLATFORM_ASSET_SYNC_SCRIPT": str(recovery),
            "WEBSOFT9_DATA_ROOT": str(tmp_path / "data"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert trace.read_text().splitlines() == ["recover:--recover-only", "supervisor", "remote"]


def test_uploaded_brand_media_survives_reload_restart_recreation_and_catalog_updates(tmp_path, monkeypatch, contract_v2):
    import hashlib

    base, payloads, artifacts, _, downloads = contract_v2
    assert runtime_assets.main() == 0
    media = tmp_path / "media"
    uploads = {
        "0123456789abcdef0123456789abcdef.png": b"\x89PNG-brand-logo",
        "fedcba9876543210fedcba9876543210": b"extensionless-upload",
    }
    for name, content in uploads.items():
        (media / name).write_bytes(content)

    assert runtime_assets.reload_runtime_app_store_manifests() == {"loaded": {"zh": 1, "en": 1}, "errors": []}
    assert get_appstore_assets_state()["status"] == "ready"
    for name, content in uploads.items():
        assert (media / name).read_bytes() == content

    with monkeypatch.context() as intact_ctx:

        def unexpected_copy(*args, **kwargs):
            raise AssertionError("intact restart recovery must not restage or back up trees")

        intact_ctx.setattr(runtime_assets, "stage_snapshot", unexpected_copy)
        intact_ctx.setattr(runtime_assets, "backup_trees", unexpected_copy)
        assert runtime_assets.recover_runtime_assets() == 0
    assert _read_state(tmp_path)["recovery"] == {"source": "active-assets"}
    for name, content in uploads.items():
        assert (media / name).read_bytes() == content

    (tmp_path / "library/library.json").write_text('{"schemaVersion":"1"}')
    assert runtime_assets.recover_runtime_assets() == 0
    assert _read_state(tmp_path)["recovery"] == {"source": "persistent-snapshot"}
    for name, content in uploads.items():
        assert (media / name).read_bytes() == content
        for snapshot_dir in _read_state(tmp_path)["snapshots"]["media"].values():
            assert not (Path(snapshot_dir) / name).exists()

    downloads.clear()
    assert runtime_assets.main() == 0
    assert downloads == []
    for name, content in uploads.items():
        assert (media / name).read_bytes() == content

    source_json = tmp_path / "source-media/json"
    (source_json / "catalog_en.json").write_text('[{"key":"cms","title":"CMS"}]')
    catalog_content = ",".join(
        f"{name}={hashlib.sha256((source_json / name).read_bytes()).hexdigest()}"
        for name in ("catalog_en.json", "catalog_zh.json", "product_en.json", "product_zh.json")
    )
    new_cat_version = hashlib.sha256(catalog_content.encode() + b"\0").hexdigest()[:16]
    payloads[f"{base}/manifests/appstore-manifest.json"]["datasetVersion"] = "c" * 16
    payloads[f"{base}/manifests/appstore-manifest.json"]["catalog"]["datasetVersion"] = new_cat_version
    payloads[f"{base}/catalog/manifest.json"]["datasetVersion"] = new_cat_version
    artifacts[f"{base}/catalog/full/latest.zip"] = _zip_bytes(source_json, "catalog-updated")
    assert runtime_assets.main() == 0
    for name, content in uploads.items():
        assert (media / name).read_bytes() == content


def test_prefetch_and_app_delta_retries_clean_stale_extractions(tmp_path, monkeypatch, contract_v2):
    import hashlib
    import zipfile

    base, payloads, artifacts, _, _ = contract_v2
    monkeypatch.setattr(runtime_assets, "_APPSTORE_SYNC_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(runtime_assets, "_APPSTORE_SYNC_RETRY_DELAY_SECONDS", 0)

    def publisher_zip(source_dir: Path) -> bytes:
        archive_path = tmp_path / f"{source_dir.name}.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(path for path in source_dir.rglob("*") if path.is_file()):
                archive.write(item, arcname=item.relative_to(source_dir.parent))
        return archive_path.read_bytes()

    bad_cat = tmp_path / "pub-cat-attempt-1"
    shutil.copytree(tmp_path / "source-media/json", bad_cat)
    (bad_cat / "catalog_en.json").write_text('[{"stale":true}]')
    good_cat = tmp_path / "pub-cat-attempt-2"
    shutil.copytree(tmp_path / "source-media/json", good_cat)
    cat_attempts = {"count": 0, "bytes": publisher_zip(bad_cat)}
    good_cat_bytes = publisher_zip(good_cat)

    def raw_bytes(url: str) -> bytes:
        if url in payloads:
            return json.dumps(payloads[url], indent=2).encode()
        return artifacts[url]

    def flaky_cat_download(url, target):
        if url.endswith("catalog/full/latest.zip"):
            cat_attempts["count"] += 1
            cat_attempts["bytes"] = cat_attempts["bytes"] if cat_attempts["count"] == 1 else good_cat_bytes
            target.write_bytes(cat_attempts["bytes"])
            return
        target.write_bytes(raw_bytes(url))

    def flaky_cat_checksum(url):
        if url.endswith("catalog/full/latest.zip.sha256"):
            return hashlib.sha256(cat_attempts["bytes"]).hexdigest()
        return hashlib.sha256(raw_bytes(url.removesuffix(".sha256"))).hexdigest()

    monkeypatch.setattr(runtime_assets, "download_file", flaky_cat_download)
    monkeypatch.setattr(runtime_assets, "download_text", flaky_cat_checksum)
    assert runtime_assets.main() == 0
    assert cat_attempts["count"] == 2

    app = tmp_path / "source-library/apps/wordpress"
    (app / ".env").write_text("W9_HTTP_PORT_SET=9090\n")
    good_app_bytes = _zip_bytes(app, "wordpress")
    good_hash = runtime_assets.app_content_fingerprint(app, "wordpress")
    stale_app = tmp_path / "stale-wordpress"
    shutil.copytree(app, stale_app)
    (stale_app / "obsolete.txt").write_text("stale file")
    app_attempts = {"count": 0, "bytes": _zip_bytes(stale_app, "wordpress")}

    payloads[f"{base}/manifests/appstore-manifest.json"]["datasetVersion"] = "d" * 16
    payloads[f"{base}/manifests/appstore-manifest.json"]["library"]["datasetVersion"] = "e" * 16
    payloads[f"{base}/library/manifest.json"]["datasetVersion"] = "e" * 16
    payloads[f"{base}/library/apps-index.json"]["datasetVersion"] = "e" * 16
    payloads[f"{base}/library/apps-index.json"]["apps"][0]["hash"] = good_hash
    payloads[f"{base}/library/apps-delta.json"].update(
        fromVersion="b" * 16, toVersion="e" * 16, addedApps=[], changedApps=["wordpress"]
    )

    def flaky_app_download(url, target):
        if url.endswith("wordpress/latest.zip"):
            app_attempts["count"] += 1
            app_attempts["bytes"] = app_attempts["bytes"] if app_attempts["count"] == 1 else good_app_bytes
            target.write_bytes(app_attempts["bytes"])
            return
        target.write_bytes(raw_bytes(url))

    def flaky_app_checksum(url):
        if url.endswith("wordpress/latest.zip.sha256"):
            return hashlib.sha256(app_attempts["bytes"]).hexdigest()
        return hashlib.sha256(raw_bytes(url.removesuffix(".sha256"))).hexdigest()

    monkeypatch.setattr(runtime_assets, "download_file", flaky_app_download)
    monkeypatch.setattr(runtime_assets, "download_text", flaky_app_checksum)
    assert runtime_assets.main() == 0
    assert app_attempts["count"] == 2

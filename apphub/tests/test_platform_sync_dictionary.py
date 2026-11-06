"""Shared database dictionary sync and library-delta version handling.

The App Store publishes the dictionary by a content-addressed path plus SHA-256,
and expresses ``appsDelta`` in *library* dataset versions. Both facts are easy to
get subtly wrong in the runtime sync, so they are pinned here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "docker" / "scripts" / "platform-sync-runtime-assets.py"
MODULE_SPEC = importlib.util.spec_from_file_location("platform_sync_runtime_assets_dictionary_test", SCRIPT_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
runtime_assets = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(runtime_assets)

DICTIONARY = json.dumps({"postgresql": {"port": 5432}}, sort_keys=True).encode("utf-8")
DICTIONARY_SHA256 = hashlib.sha256(DICTIONARY).hexdigest()


def _bundle(sha256: str = DICTIONARY_SHA256) -> dict[str, object]:
    return {
        "library_manifest_url": "https://artifact.example/appstore/dev/library/manifest.json",
        "library_manifest": {
            "metadata": {
                "databaseTypes": {
                    "path": f"metadata/database-types-{sha256}.json",
                    "sha256": sha256,
                }
            }
        },
    }


# ── manifest parsing ────────────────────────────────────────────────


def test_the_manifest_names_the_dictionary_by_content():
    entry = runtime_assets.library_dictionary_entry(_bundle())

    assert entry == {
        "path": f"metadata/database-types-{DICTIONARY_SHA256}.json",
        "sha256": DICTIONARY_SHA256,
        "manifest_url": "https://artifact.example/appstore/dev/library/manifest.json",
    }


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        {"databaseTypes": {}},
        {"databaseTypes": {"path": "metadata/x.json", "sha256": "not-a-digest"}},
        {"databaseTypes": {"sha256": DICTIONARY_SHA256}},
    ],
)
def test_an_incomplete_metadata_block_is_not_used(metadata):
    bundle = {
        "library_manifest_url": "https://artifact.example/library/manifest.json",
        "library_manifest": {"metadata": metadata},
    }

    assert runtime_assets.library_dictionary_entry(bundle) is None


def test_a_legacy_manifest_without_metadata_is_ignored():
    assert runtime_assets.library_dictionary_entry({"library_manifest": {}}) is None
    assert runtime_assets.library_dictionary_entry(None) is None


# ── dictionary sync ─────────────────────────────────────────────────


def test_an_up_to_date_dictionary_is_not_downloaded(tmp_path, monkeypatch):
    local = tmp_path / "library" / "metadata" / "database-types.json"
    local.parent.mkdir(parents=True)
    local.write_bytes(DICTIONARY)

    def explode(*args, **kwargs):  # pragma: no cover - asserted by not being called
        raise AssertionError("an up-to-date dictionary must not be downloaded")

    monkeypatch.setattr(runtime_assets, "download_file", explode)

    report = runtime_assets.sync_shared_database_dictionary(_bundle(), [local])

    assert report == {"status": "unchanged", "sha256": DICTIONARY_SHA256}


def test_a_missing_dictionary_is_downloaded_verified_and_written(tmp_path, monkeypatch):
    local = tmp_path / "library" / "metadata" / "database-types.json"
    snapshot = tmp_path / "releases" / "dsv" / "library" / "metadata" / "database-types.json"
    downloaded: list[str] = []

    def fake_download(url, destination):
        downloaded.append(url)
        Path(destination).write_bytes(DICTIONARY)

    monkeypatch.setattr(runtime_assets, "download_file", fake_download)

    report = runtime_assets.sync_shared_database_dictionary(_bundle(), [local, snapshot])

    assert report == {"status": "updated", "sha256": DICTIONARY_SHA256}
    assert downloaded == [f"https://artifact.example/appstore/dev/library/metadata/database-types-{DICTIONARY_SHA256}.json"]
    assert local.read_bytes() == DICTIONARY
    assert snapshot.read_bytes() == DICTIONARY


def test_a_corrupt_local_dictionary_is_repaired_even_when_versions_match(tmp_path, monkeypatch):
    # A dictionary-only release, or a half-written file, must be fixed even though no app
    # package changes.
    local = tmp_path / "library" / "metadata" / "database-types.json"
    local.parent.mkdir(parents=True)
    local.write_text('{"broken":', encoding="utf-8")

    monkeypatch.setattr(runtime_assets, "download_file", lambda url, dest: Path(dest).write_bytes(DICTIONARY))

    report = runtime_assets.sync_shared_database_dictionary(_bundle(), [local])

    assert report["status"] == "updated"
    assert json.loads(local.read_text(encoding="utf-8")) == {"postgresql": {"port": 5432}}


def test_a_checksum_mismatch_leaves_the_existing_dictionary_alone(tmp_path, monkeypatch):
    local = tmp_path / "library" / "metadata" / "database-types.json"
    local.parent.mkdir(parents=True)
    # A stale but valid copy: the download must be verified before it may replace this file.
    local.write_text('{"postgresql": {"port": 5433}}', encoding="utf-8")

    monkeypatch.setattr(runtime_assets, "download_file", lambda url, dest: Path(dest).write_bytes(b'{"tampered":true}'))

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        runtime_assets.sync_shared_database_dictionary(_bundle(), [local])

    assert json.loads(local.read_text(encoding="utf-8")) == {"postgresql": {"port": 5433}}


def test_snapshot_targets_cover_the_live_library_and_every_snapshot(tmp_path):
    library_root = tmp_path / "library"
    snapshots = {
        "library": {
            "staging": str(tmp_path / "staging" / "dsv" / "library"),
            "release": str(tmp_path / "releases" / "dsv" / "library"),
            "current": str(tmp_path / "current" / "library"),
        }
    }

    targets = runtime_assets.library_dictionary_targets(library_root, snapshots)

    assert targets[0] == library_root / "metadata" / "database-types.json"
    assert [str(target.parents[1].name) for target in targets[1:]] == ["library", "library", "library"]
    assert len(targets) == 4


# ── library delta version chain ─────────────────────────────────────


def test_the_delta_chain_is_checked_against_library_dataset_versions(monkeypatch):
    """``appsDelta`` chains library dataset versions, never the root Appstore one."""
    captured: dict[str, object] = {}

    def fake_resolve(bundle, previous_version, latest_version):
        captured["previous"] = previous_version
        captured["latest"] = latest_version
        return None

    monkeypatch.setattr(runtime_assets, "resolve_library_delta_context", fake_resolve)

    bundle = {
        "appstore_manifest": {
            "datasetVersion": "rootnew",
            "catalog": {"datasetVersion": "catnew"},
            "library": {"datasetVersion": "libnew"},
        },
        "library_manifest": {"supportsPartialUpdate": True},
        "library_manifest_url": "https://artifact.example/appstore/dev/library/manifest.json",
    }
    previous_state = {
        "datasetVersion": "rootold",
        "catalogDatasetVersion": "catold",
        "libraryDatasetVersion": "libold",
    }

    plan = runtime_assets.determine_package_sync_plan(bundle, previous_state, "rootnew")

    assert plan["library"] is True
    assert captured == {"previous": "libold", "latest": "libnew"}


def test_an_older_state_without_component_versions_still_falls_back_to_the_root_version(monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        runtime_assets,
        "resolve_library_delta_context",
        lambda bundle, previous_version, latest_version: captured.update(previous=previous_version, latest=latest_version),
    )

    bundle = {
        "appstore_manifest": {"datasetVersion": "rootnew"},
        "library_manifest": {"supportsPartialUpdate": True},
        "library_manifest_url": "https://artifact.example/library/manifest.json",
    }

    runtime_assets.determine_package_sync_plan(bundle, {"datasetVersion": "rootold"}, "rootnew")

    assert captured == {"previous": "rootold", "latest": "rootnew"}


def test_a_missing_dictionary_triggers_one_repair_request_on_the_fast_path(tmp_path, monkeypatch):
    """An active dataset skips component manifests, but a broken dictionary is still fixed."""
    library_root = tmp_path / "library"
    library_root.mkdir()
    requested: list[str] = []

    def fake_download(url):
        requested.append(url)
        if url.endswith("appstore-manifest.json"):
            return {
                "schemaVersion": "1",
                "datasetVersion": "root-1",
                "catalog": {"datasetVersion": "cat-1", "manifest": "catalog/manifest.json"},
                "library": {"datasetVersion": "lib-1", "manifest": "library/manifest.json"},
            }
        return {"metadata": {"databaseTypes": {"path": "metadata/database-types-x.json", "sha256": DICTIONARY_SHA256}}}

    monkeypatch.setattr(runtime_assets, "download_json", fake_download)
    monkeypatch.setattr(runtime_assets, "artifact_base_default", lambda: "https://artifact.example.test", raising=False)
    monkeypatch.delenv("WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC", raising=False)
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(library_root))

    bundle = runtime_assets.fetch_appstore_manifests(
        "https://artifact.example.test",
        "dev",
        "1",
        previous_state={
            "schemaVersion": "1",
            "datasetVersion": "root-1",
            "catalogDatasetVersion": "cat-1",
            "libraryDatasetVersion": "lib-1",
            "databaseTypesSha256": DICTIONARY_SHA256,
        },
    )

    assert bundle["componentManifestsSkipped"] is True
    assert bundle["library_manifest"] is not None
    assert requested[-1] == "https://artifact.example.test/appstore/dev/library/manifest.json"


def test_an_intact_dictionary_keeps_the_fast_path_at_one_request(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    dictionary = library_root / "metadata" / "database-types.json"
    dictionary.parent.mkdir(parents=True)
    dictionary.write_bytes(DICTIONARY)
    requested: list[str] = []

    def fake_download(url):
        requested.append(url)
        return {
            "schemaVersion": "1",
            "datasetVersion": "root-1",
            "catalog": {"datasetVersion": "cat-1", "manifest": "catalog/manifest.json"},
            "library": {"datasetVersion": "lib-1", "manifest": "library/manifest.json"},
        }

    monkeypatch.setattr(runtime_assets, "download_json", fake_download)
    monkeypatch.delenv("WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC", raising=False)
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(library_root))

    runtime_assets.fetch_appstore_manifests(
        "https://artifact.example.test",
        "dev",
        "1",
        previous_state={
            "schemaVersion": "1",
            "datasetVersion": "root-1",
            "catalogDatasetVersion": "cat-1",
            "libraryDatasetVersion": "lib-1",
            "databaseTypesSha256": DICTIONARY_SHA256,
        },
    )

    assert requested == ["https://artifact.example.test/appstore/dev/manifests/appstore-manifest.json"]

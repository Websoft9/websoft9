"""Shared database dictionary sync and library-delta version handling.

The App Store publishes the dictionary by a content-addressed path plus SHA-256,
and expresses ``appsDelta`` in *library* dataset versions. Both facts are easy to
get subtly wrong in the runtime sync, so they are pinned here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "docker" / "scripts" / "platform-sync-runtime-assets.py"
MODULE_SPEC = importlib.util.spec_from_file_location("platform_sync_runtime_assets_dictionary_test", SCRIPT_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
runtime_assets = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(runtime_assets)

DICTIONARY = json.dumps({"postgresql": {"port": 5432}}, sort_keys=True).encode("utf-8")
DICTIONARY_SHA256 = hashlib.sha256(DICTIONARY).hexdigest()


@pytest.fixture(autouse=True)
def no_retry_waits(monkeypatch):
    monkeypatch.setattr(runtime_assets, "_APPSTORE_SYNC_RETRY_DELAY_SECONDS", 0)


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
        {"databaseTypes": {}},
        {"databaseTypes": {"path": "metadata/x.json", "sha256": "not-a-digest"}},
        {"databaseTypes": {"sha256": DICTIONARY_SHA256}},
    ],
)
def test_an_incomplete_metadata_block_is_rejected(metadata):
    bundle = {
        "library_manifest_url": "https://artifact.example/library/manifest.json",
        "library_manifest": {"metadata": metadata},
    }

    with pytest.raises(runtime_assets.AppStoreTransientError):
        runtime_assets.library_dictionary_entry(bundle)


def test_a_legacy_manifest_without_metadata_is_ignored():
    assert runtime_assets.library_dictionary_entry({"library_manifest": {}}) is None
    assert runtime_assets.library_dictionary_entry(None) is None
    assert runtime_assets.library_dictionary_entry({"library_manifest": {"metadata": {}}}) is None


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


# ── shared secret rules dictionary ──────────────────────────────────

SECRET_RULES = json.dumps({"base64": {"generator": "random_bytes", "encoding": "base64"}}).encode("utf-8")
SECRET_RULES_SHA256 = hashlib.sha256(SECRET_RULES).hexdigest()


def _secret_bundle(sha256: str = SECRET_RULES_SHA256) -> dict[str, object]:
    return {
        "library_manifest_url": "https://artifact.example/appstore/dev/library/manifest.json",
        "library_manifest": {
            "metadata": {
                "secretRules": {
                    "path": f"metadata/secret-rules-{sha256}.json",
                    "sha256": sha256,
                }
            }
        },
    }


def test_the_manifest_names_the_secret_rules_dictionary_by_content():
    entry = runtime_assets.library_dictionary_entry(_secret_bundle(), "secretRules")

    assert entry == {
        "path": f"metadata/secret-rules-{SECRET_RULES_SHA256}.json",
        "sha256": SECRET_RULES_SHA256,
        "manifest_url": "https://artifact.example/appstore/dev/library/manifest.json",
    }


def test_a_legacy_manifest_without_secret_rules_is_unavailable(tmp_path):
    local = tmp_path / "library" / "metadata" / "secret-rules.json"

    report = runtime_assets.sync_shared_dictionary(_bundle(), [local], entry_key="secretRules", filename="secret-rules.json")

    assert report == {"status": "unavailable"}
    assert not local.exists()


def test_secret_rules_are_downloaded_verified_and_written(tmp_path, monkeypatch):
    local = tmp_path / "library" / "metadata" / "secret-rules.json"
    snapshot = tmp_path / "releases" / "dsv" / "library" / "metadata" / "secret-rules.json"
    downloaded: list[str] = []

    def fake_download(url, destination):
        downloaded.append(url)
        Path(destination).write_bytes(SECRET_RULES)

    monkeypatch.setattr(runtime_assets, "download_file", fake_download)

    report = runtime_assets.sync_shared_dictionary(
        _secret_bundle(), [local, snapshot], entry_key="secretRules", filename="secret-rules.json"
    )

    assert report == {"status": "updated", "sha256": SECRET_RULES_SHA256}
    assert downloaded == [f"https://artifact.example/appstore/dev/library/metadata/secret-rules-{SECRET_RULES_SHA256}.json"]
    assert local.read_bytes() == SECRET_RULES
    assert snapshot.read_bytes() == SECRET_RULES


def test_a_missing_optional_dictionary_is_not_treated_as_damage(tmp_path):
    library_root = tmp_path / "library"

    # Nothing recorded yet: an older artifact simply has not published it.
    assert not runtime_assets._dictionary_repair_needed(library_root, {}, "secretRules", "secret-rules.json", known_only=True)
    # Recorded before: a missing file is damage and has to be repaired.
    assert runtime_assets._dictionary_repair_needed(
        library_root,
        {"secretRulesSha256": SECRET_RULES_SHA256},
        "secretRules",
        "secret-rules.json",
        known_only=True,
    )


def test_a_changed_recorded_dictionary_is_repaired(tmp_path):
    library_root = tmp_path / "library"
    local = library_root / "metadata" / "secret-rules.json"
    local.parent.mkdir(parents=True)
    local.write_bytes(SECRET_RULES)

    assert not runtime_assets._dictionary_repair_needed(
        library_root, {"secretRulesSha256": SECRET_RULES_SHA256}, "secretRules", "secret-rules.json", known_only=True
    )
    assert runtime_assets._dictionary_repair_needed(
        library_root, {"secretRulesSha256": "0" * 64}, "secretRules", "secret-rules.json", known_only=True
    )


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
        if url.endswith("catalog/manifest.json"):
            return {"schemaVersion": "1", "datasetVersion": "cat-1"}
        return {
            "schemaVersion": "1",
            "datasetVersion": "lib-1",
            "metadata": {"databaseTypes": {"path": "metadata/database-types-x.json", "sha256": DICTIONARY_SHA256}},
        }

    monkeypatch.setattr(runtime_assets, "download_json", fake_download)
    monkeypatch.setattr(runtime_assets, "download_verified_json", fake_download)
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

    assert len(requested) == 3
    assert bundle["library_manifest"] is not None
    assert "https://artifact.example.test/appstore/dev/library/manifest.json" in requested


def test_an_old_root_checks_component_schemas_even_when_dictionaries_are_intact(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    dictionary = library_root / "metadata" / "database-types.json"
    dictionary.parent.mkdir(parents=True)
    dictionary.write_bytes(DICTIONARY)
    requested: list[str] = []

    def fake_download(url):
        requested.append(url)
        if "/catalog/" in url:
            return {"schemaVersion": "1", "datasetVersion": "cat-1"}
        if "/library/" in url:
            return {"schemaVersion": "1", "datasetVersion": "lib-1"}
        return {
            "schemaVersion": "1",
            "datasetVersion": "root-1",
            "catalog": {"datasetVersion": "cat-1", "manifest": "catalog/manifest.json"},
            "library": {"datasetVersion": "lib-1", "manifest": "library/manifest.json"},
        }

    monkeypatch.setattr(runtime_assets, "download_json", fake_download)
    monkeypatch.setattr(runtime_assets, "download_verified_json", fake_download)
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

    assert len(requested) == 3


# ── torn publication, retries and partial activation ────────────────


def test_a_library_manifest_from_another_dataset_is_a_transient_error(tmp_path, monkeypatch):
    """The root manifest names the library dataset; a mismatch means a torn publication."""

    def fake_download(url):
        if url.endswith("library/manifest.json"):
            return {"schemaVersion": "1", "datasetVersion": "lib-old"}
        if url.endswith("catalog/manifest.json"):
            return {"schemaVersion": "1", "datasetVersion": "cat-1"}
        return {
            "schemaVersion": "1",
            "datasetVersion": "root-new",
            "catalog": {"datasetVersion": "cat-1", "manifest": "catalog/manifest.json"},
            "library": {"datasetVersion": "lib-new", "manifest": "library/manifest.json"},
        }

    monkeypatch.setattr(runtime_assets, "download_json", fake_download)
    monkeypatch.setattr(runtime_assets, "download_verified_json", fake_download)

    with pytest.raises(runtime_assets.AppStoreTransientError, match="does not match the root manifest"):
        runtime_assets.fetch_appstore_manifests("https://artifact.example.test", "dev", "1", force_refresh=True)


def test_transient_retry_runs_again_after_the_cache_window(monkeypatch):
    monkeypatch.setattr(runtime_assets, "_APPSTORE_SYNC_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(runtime_assets, "_APPSTORE_SYNC_RETRY_DELAY_SECONDS", 0)
    calls: list[int] = []

    def flaky():
        calls.append(len(calls))
        if len(calls) == 1:
            raise runtime_assets.AppStoreTransientError("checksum mismatch")
        return "ok"

    assert runtime_assets.with_transient_retry(flaky, label="test") == "ok"
    assert len(calls) == 2


def test_transient_retry_gives_up_after_the_configured_attempts(monkeypatch):
    monkeypatch.setattr(runtime_assets, "_APPSTORE_SYNC_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(runtime_assets, "_APPSTORE_SYNC_RETRY_DELAY_SECONDS", 0)
    calls: list[int] = []

    def always_fails():
        calls.append(len(calls))
        raise runtime_assets.AppStoreTransientError("still broken")

    with pytest.raises(runtime_assets.AppStoreTransientError):
        runtime_assets.with_transient_retry(always_fails, label="test")
    assert len(calls) == 2


def test_non_transient_errors_are_not_retried(monkeypatch):
    monkeypatch.setattr(runtime_assets, "_APPSTORE_SYNC_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(runtime_assets, "_APPSTORE_SYNC_RETRY_DELAY_SECONDS", 0)
    calls: list[int] = []

    def broken():
        calls.append(len(calls))
        raise ValueError("programming error")

    with pytest.raises(ValueError):
        runtime_assets.with_transient_retry(broken, label="test")
    assert len(calls) == 1


def test_a_verified_manifest_must_match_its_published_checksum(monkeypatch):
    payload = json.dumps({"datasetVersion": "lib-1"}).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()

    class FakeResponse:
        def __init__(self, body):
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(runtime_assets.urllib.request, "urlopen", lambda *a, **k: FakeResponse(payload))
    monkeypatch.setattr(runtime_assets, "download_text", lambda url: f"{digest}  manifest.json")

    assert runtime_assets.download_verified_json("https://artifact.example.test/library/manifest.json") == {
        "datasetVersion": "lib-1"
    }

    monkeypatch.setattr(runtime_assets, "download_text", lambda url: "0" * 64)
    with pytest.raises(runtime_assets.AppStoreTransientError, match="manifest checksum mismatch"):
        runtime_assets.download_verified_json("https://artifact.example.test/library/manifest.json")


def test_a_manifest_without_a_checksum_sibling_is_still_usable(monkeypatch):
    payload = json.dumps({"datasetVersion": "lib-1"}).encode("utf-8")

    class FakeResponse:
        def __init__(self, body):
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(runtime_assets.urllib.request, "urlopen", lambda *a, **k: FakeResponse(payload))

    def missing(url):
        cause = runtime_assets.urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        raise runtime_assets.AppStoreTransientError("404") from cause

    monkeypatch.setattr(runtime_assets, "download_text", missing)

    assert runtime_assets.download_verified_json("https://artifact.example.test/library/manifest.json") == {
        "datasetVersion": "lib-1"
    }


def test_the_apps_index_reports_a_failed_write(tmp_path, monkeypatch):
    target = tmp_path / "library"

    def broken_write(self, *args, **kwargs):  # pragma: no cover - raises
        raise OSError("disk full")

    monkeypatch.setattr(runtime_assets, "fetch_library_apps_index_payload", lambda bundle: {"apps": []})
    monkeypatch.setattr(Path, "write_text", broken_write, raising=False)

    assert runtime_assets.publish_library_apps_index(target, {}) is False


@pytest.mark.parametrize("checksum", ["", "   ", "not-a-checksum"])
def test_invalid_manifest_checksums_are_retryable(monkeypatch, checksum):
    from io import BytesIO

    monkeypatch.setattr(runtime_assets.urllib.request, "urlopen", lambda *args, **kwargs: BytesIO(b"{}"))
    monkeypatch.setattr(runtime_assets, "download_text", lambda url: checksum)

    with pytest.raises(runtime_assets.AppStoreTransientError, match="invalid manifest checksum"):
        runtime_assets.download_verified_json("https://artifact.example.test/manifest.json")


@pytest.mark.parametrize("status", [403, 503, None])
def test_checksum_network_failures_do_not_disable_verification(monkeypatch, status):
    from io import BytesIO

    monkeypatch.setattr(runtime_assets.urllib.request, "urlopen", lambda *args, **kwargs: BytesIO(b"{}"))

    def failed_checksum(url):
        cause = (
            TimeoutError("timeout")
            if status is None
            else runtime_assets.urllib.error.HTTPError(url, status, "failed", {}, None)
        )
        raise runtime_assets.AppStoreTransientError("checksum unavailable") from cause

    monkeypatch.setattr(runtime_assets, "download_text", failed_checksum)

    with pytest.raises(runtime_assets.AppStoreTransientError, match="checksum unavailable"):
        runtime_assets.download_verified_json("https://artifact.example.test/manifest.json")


def _indexed_bundle():
    return {
        "appstore_manifest": {"channel": "dev", "library": {"datasetVersion": "lib-new"}},
        "library_manifest_url": "https://artifact.example.test/appstore/dev/library/manifest.json",
        "library_manifest": {
            "schemaVersion": "1",
            "datasetVersion": "lib-new",
            "supportsPartialUpdate": True,
            "appsIndex": "apps-index.json",
            "appsDelta": "apps-delta.json",
            "checksum": {"appsIndex": "index.sha256", "appsDelta": "delta.sha256"},
        },
    }


@pytest.mark.parametrize("status", [404, 403, 503])
def test_a_missing_root_is_distinguished_from_other_download_failures(monkeypatch, status):
    def failed_root(url):
        cause = runtime_assets.urllib.error.HTTPError(url, status, "failed", {}, None)
        raise runtime_assets.AppStoreTransientError("root unavailable") from cause

    monkeypatch.setattr(runtime_assets, "download_verified_json", failed_root)
    expected = runtime_assets.AppStoreManifestNotFoundError if status == 404 else runtime_assets.AppStoreTransientError
    with pytest.raises(expected):
        runtime_assets.fetch_appstore_manifests("https://example.test", "dev", "1", {}, False)


def test_a_versioned_legacy_index_retains_bundle_compatibility(monkeypatch):
    bundle = {
        "library_manifest_url": "https://example.test/appstore/dev/library/manifest.json",
        "library_manifest": {
            "datasetVersion": "legacy",
            "appsIndex": "index.json",
            "checksum": {"appsIndex": "index.sha256"},
            "compatibility": {"appLevelArtifacts": True},
        },
    }
    payload = {
        "datasetVersion": "legacy",
        "apps": [{"key": "wordpress", "bundle": "wordpress.zip", "checksum": {"bundle": "wordpress.sha256"}}],
    }
    _serve_json(monkeypatch, payload)

    assert runtime_assets.resolve_library_apps_index(bundle)["wordpress"]["bundle"] == "wordpress.zip"
    assert runtime_assets.resolve_library_index_delta_context(bundle, {}, Path("unused"), "dev") is None


def _index_app(key="wordpress", digest="a" * 64):
    return {
        "app": key,
        "hash": digest,
        "package": {"latest": f"apps/{key}/latest.zip"},
        "checksum": {"latest": f"apps/{key}/latest.zip.sha256"},
    }


def _remote_index(apps=None):
    return {
        "schemaVersion": "1",
        "channel": "dev",
        "datasetVersion": "lib-new",
        "apps": [_index_app()] if apps is None else apps,
    }


def _serve_json(monkeypatch, payload):
    raw = json.dumps(payload, indent=3).encode("utf-8") + b"\n "
    calls = []

    def serve(request, **kwargs):
        calls.append(request.full_url)
        return BytesIO(raw)

    monkeypatch.setattr(runtime_assets.urllib.request, "urlopen", serve)
    monkeypatch.setattr(runtime_assets, "download_text", lambda url: hashlib.sha256(raw).hexdigest())
    return calls


def test_declared_index_verifies_raw_bytes_and_reuses_one_payload(tmp_path, monkeypatch):
    bundle = _indexed_bundle()
    calls = _serve_json(monkeypatch, _remote_index())
    payload = runtime_assets.fetch_library_apps_index_payload(bundle)
    assert runtime_assets.resolve_library_apps_index(bundle)["wordpress"]["hash"] == "a" * 64
    assert runtime_assets.publish_library_apps_index(tmp_path, bundle)
    assert json.loads((tmp_path / "apps-index.json").read_text()) == payload
    assert len(calls) == 1


@pytest.mark.parametrize("key", ["appsIndex", "appsDelta"])
@pytest.mark.parametrize("failure", ["404", "timeout", "invalid", "mismatch"])
def test_declared_json_checksum_failures_never_become_legacy(monkeypatch, key, failure):
    bundle = _indexed_bundle()
    _serve_json(monkeypatch, {})

    def failed_checksum(url):
        if failure == "404":
            cause = runtime_assets.urllib.error.HTTPError(url, 404, "missing", {}, None)
            raise runtime_assets.AppStoreTransientError("missing checksum") from cause
        if failure == "timeout":
            raise runtime_assets.AppStoreTransientError("timeout") from TimeoutError()
        return "bad" if failure == "invalid" else "0" * 64

    monkeypatch.setattr(runtime_assets, "download_text", failed_checksum)
    with pytest.raises(runtime_assets.AppStoreTransientError):
        runtime_assets._fetch_library_json(bundle, key)


@pytest.mark.parametrize(
    "field,value",
    [
        ("channel", "release"),
        ("channel", None),
        ("datasetVersion", "old"),
        ("datasetVersion", None),
        ("schemaVersion", "2"),
        ("schemaVersion", "999"),
    ],
)
def test_index_identity_must_match_the_bundle(monkeypatch, field, value):
    payload = _remote_index()
    payload[field] = value
    _serve_json(monkeypatch, payload)
    with pytest.raises(runtime_assets.AppStoreTransientError):
        runtime_assets.fetch_library_apps_index_payload(_indexed_bundle())


@pytest.mark.parametrize(
    "apps",
    [
        [_index_app("../escape")],
        [_index_app("/escape")],
        [_index_app("wordpress"), _index_app("wordpress")],
        [_index_app(digest="bad")],
        [{"app": "wordpress"}],
        [{**_index_app(), "checksum": {}}],
    ],
)
def test_current_index_requires_safe_unique_complete_app_metadata(monkeypatch, apps):
    _serve_json(monkeypatch, _remote_index(apps))
    with pytest.raises(runtime_assets.AppStoreTransientError):
        runtime_assets.fetch_library_apps_index_payload(_indexed_bundle())


@pytest.mark.parametrize("component", ["catalog", "library"])
@pytest.mark.parametrize("actual", ["old", "", None, 123, "missing"])
@pytest.mark.parametrize("repair", [False, True])
def test_component_versions_are_checked_on_normal_and_repair_paths(tmp_path, monkeypatch, component, actual, repair):
    root = {
        "schemaVersion": "1",
        "datasetVersion": "root",
        "catalog": {"manifest": "catalog/manifest.json", "datasetVersion": "cat"},
        "library": {"manifest": "library/manifest.json", "datasetVersion": "lib"},
    }
    monkeypatch.setattr(
        runtime_assets,
        "download_verified_json",
        lambda url: (
            root
            if url.endswith("appstore-manifest.json")
            else {}
            if actual == "missing" and f"/{component}/" in url
            else {
                "schemaVersion": "1",
                "datasetVersion": actual if f"/{component}/" in url else "cat" if "/catalog/" in url else "lib",
            }
        ),
    )
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(tmp_path))
    state = {"datasetVersion": "root", "catalogDatasetVersion": "cat", "libraryDatasetVersion": "lib"} if repair else {}
    with pytest.raises(runtime_assets.AppStoreTransientError):
        runtime_assets.fetch_appstore_manifests("https://example.test", "dev", "1", state, False)


@pytest.mark.parametrize("component", ["root", "catalog", "library"])
def test_manifest_channels_must_match_the_requested_channel(monkeypatch, component):
    root = {
        "schemaVersion": "1",
        "channel": "release" if component == "root" else "dev",
        "catalog": {"manifest": "catalog/manifest.json", "datasetVersion": "cat"},
        "library": {"manifest": "library/manifest.json", "datasetVersion": "lib"},
    }
    monkeypatch.setattr(
        runtime_assets,
        "download_verified_json",
        lambda url: (
            root
            if url.endswith("appstore-manifest.json")
            else {
                "schemaVersion": "1",
                "datasetVersion": "cat" if "/catalog/" in url else "lib",
                "channel": "release" if f"/{component}/" in url else "dev",
            }
        ),
    )

    with pytest.raises(runtime_assets.AppStoreTransientError, match="channel does not match"):
        runtime_assets.fetch_appstore_manifests("https://example.test", "dev", "1", {}, True)


def _write_apps(root, values):
    for key, value in values.items():
        app = root / "apps" / key
        app.mkdir(parents=True)
        (app / ".env").write_text(f"W9_HTTP_PORT_SET={value}\n", encoding="utf-8")
        (app / "variables.json").write_text('{"edition":[{"dist":"community","version":"1.0"}]}', encoding="utf-8")
    return [_index_app(key, runtime_assets.app_content_fingerprint(root / "apps" / key, key)) for key in sorted(values)]


def _zip_bytes(root, prefix):
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, f"{prefix}/{path.relative_to(root).as_posix()}")
    return output.getvalue()


def test_app_fingerprint_uses_canonical_sorted_paths_and_ignores_root_metadata(tmp_path):
    root = tmp_path / "library"
    _write_apps(root, {"wordpress": 80})
    nested = root / "apps" / "wordpress" / "nested"
    nested.mkdir()
    (nested / "file").write_bytes(b"content")
    digest = hashlib.sha256()
    for name in (".env", "nested/file", "variables.json"):
        digest.update(f"apps/wordpress/{name}".encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256((root / "apps" / "wordpress" / name).read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\0")
    (root / "apps-index.json").write_bytes(b"arbitrary metadata")
    assert runtime_assets.app_content_fingerprint(root / "apps" / "wordpress", "wordpress") == digest.hexdigest()


def test_app_fingerprint_sorts_paths_by_parts_like_the_publisher(tmp_path):
    """``src/hrms/`` sorts before ``src/hrms.png`` because the publisher hashes
    ``sorted(Path)``; plain string order would put the dot first and change the
    digest (erpnext publishes 1536 files this way)."""
    app = tmp_path / "apps" / "erpnext"
    (app / "src" / "hrms").mkdir(parents=True)
    (app / "src" / "hrms" / "__init__.py").write_bytes(b"code")
    (app / "src" / "hrms.png").write_bytes(b"image")

    digest = hashlib.sha256()
    for name in ("src/hrms/__init__.py", "src/hrms.png"):
        digest.update(f"apps/erpnext/{name}".encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256((app / name).read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\0")

    assert runtime_assets.app_content_fingerprint(app, "erpnext") == digest.hexdigest()


@pytest.mark.parametrize("link", ["escape", "directory", "internal"])
def test_app_fingerprint_handles_symlinks_without_escaping(tmp_path, link):
    app = tmp_path / "app"
    app.mkdir()
    (app / "file").write_bytes(b"content")
    if link == "internal":
        (app / "link").symlink_to("file")
        assert len(runtime_assets.app_content_fingerprint(app, "wordpress")) == 64
    else:
        target = tmp_path / "outside" if link == "escape" else app / "directory"
        if link == "escape":
            target.write_bytes(b"outside")
        else:
            target.mkdir()
        (app / "link").symlink_to(target)
        with pytest.raises(runtime_assets.AppStoreTransientError, match="symlink"):
            runtime_assets.app_content_fingerprint(app, "wordpress")


@pytest.mark.parametrize(
    "mode",
    [
        "skipped",
        "fast",
        "empty",
        "damaged",
        "index-version",
        "index-missing",
        "index-channel",
        "partial",
        "race",
        "full-race",
        "package-fallback",
        "package-fallback-race",
        "index-checksum-failure",
        "dictionary-failure",
        "partial-failure",
        "index-retry",
        "dictionary-retry",
        "prune-failure",
        "partial-matching",
    ],
)
def test_main_reconciles_indexes_and_validates_packages_before_activation(tmp_path, monkeypatch, mode):
    library = tmp_path / "library"
    media = tmp_path / "media"
    snapshots = tmp_path / "snapshots"
    new_library = tmp_path / "remote-library"
    new_media = tmp_path / "remote-media"
    old_values = {"keep": 80, "change": 81, "remove": 82}
    new_values = old_values if mode in {"empty", "partial-matching"} else {"keep": 80, "change": 91, "add": 92}
    old_apps = _write_apps(library, old_values)
    new_apps = _write_apps(new_library, new_values)
    for root, values in ((media, old_values), (new_media, new_values)):
        (root / "json").mkdir(parents=True)
        for locale in ("en", "zh"):
            (root / "json" / f"product_{locale}.json").write_text(
                json.dumps([{"key": key, "title": key} for key in values]), encoding="utf-8"
            )
    runtime_assets.build_and_publish_app_store_manifests(media, library)
    old_index = {"schemaVersion": "1", "datasetVersion": "lib-old", "channel": "dev", "apps": old_apps}
    if mode == "partial-matching":
        old_index["datasetVersion"] = "lib-new"
    (library / "apps-index.json").write_text(json.dumps(old_index), encoding="utf-8")
    dictionary = library / "metadata" / "database-types.json"
    dictionary.parent.mkdir(exist_ok=True)
    dictionary.write_bytes(b'{"old":true}')
    paths = {
        kind: {key: str(value) for key, value in runtime_assets.stage_snapshot(root, snapshots, "root-old", kind).items()}
        for kind, root in (("library", library), ("media", media))
    }
    state = {
        "channel": "dev",
        "schemaVersion": "1",
        "datasetVersion": "root-old",
        "libraryDatasetVersion": "lib-old",
        "catalogDatasetVersion": "cat-old",
        "databaseTypesSha256": hashlib.sha256(dictionary.read_bytes()).hexdigest(),
        "snapshots": paths,
    }
    if mode in {"partial", "partial-failure", "partial-matching"}:
        state.update(datasetVersion="root-new", libraryDatasetVersion="lib-new", catalogDatasetVersion="cat-new", partial=True)
    if mode == "damaged":
        (library / "apps" / "keep" / ".env").write_bytes(b"corrupt baseline")
    if mode in {"index-missing", "full-race"}:
        (library / "apps-index.json").unlink()
    if mode in {"index-version", "index-channel"}:
        old_index["datasetVersion" if mode == "index-version" else "channel"] = "wrong"
        (library / "apps-index.json").write_text(json.dumps(old_index), encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    original_state = state_path.read_bytes()
    original_trees = {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for root in (media, library, snapshots)
        for path in root.rglob("*")
        if path.is_file()
    }
    for name, value in {
        "WEBSOFT9_MEDIA_ROOT": media,
        "WEBSOFT9_LIBRARY_ROOT": library,
        "WEBSOFT9_MEDIA_MARKER": media / "json" / "product_en.json",
        "WEBSOFT9_LIBRARY_MARKER": library / "apps",
        "WEBSOFT9_APP_STORE_SNAPSHOT_ROOT": snapshots,
        "WEBSOFT9_APP_STORE_SYNC_STATE": state_path,
        "WEBSOFT9_APPSTORE_SYNC_LOCK_FILE": tmp_path / "sync.lock",
        "WEBSOFT9_APPSTORE_SYNC_PID_FILE": tmp_path / "sync.pid",
    }.items():
        monkeypatch.setenv(name, str(value))
    monkeypatch.setenv("WEBSOFT9_RUNTIME_ASSET_CHANNEL", "dev")
    monkeypatch.setenv("WEBSOFT9_ARTIFACT_BASE", "https://artifact.example.test")
    monkeypatch.delenv("WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC", raising=False)
    monkeypatch.setattr(
        runtime_assets, "_APPSTORE_SYNC_RETRY_ATTEMPTS", 2 if mode in {"index-retry", "dictionary-retry"} else 1
    )
    bundle = _indexed_bundle()
    root_manifest = {
        "schemaVersion": "1",
        "channel": "dev",
        "datasetVersion": "root-new",
        "catalog": {"datasetVersion": "cat-new", "manifest": "catalog/manifest.json"},
        "library": {"datasetVersion": "lib-new", "manifest": "library/manifest.json"},
    }
    library_manifest = bundle["library_manifest"]
    library_manifest.update(fullPackage="full/latest.zip", metadata=_bundle()["library_manifest"]["metadata"])
    library_manifest["checksum"]["fullPackage"] = "full/latest.zip.sha256"
    delta = {
        "schemaVersion": "1",
        "channel": "dev",
        "fromVersion": "lib-old" if mode == "fast" else "lib-middle",
        "toVersion": "lib-new",
        "addedApps": ["add"],
        "changedApps": ["change"],
        "removedApps": ["remove"],
    }
    base = "https://artifact.example.test/appstore/dev"
    payloads = {
        f"{base}/manifests/appstore-manifest.json": root_manifest,
        f"{base}/catalog/manifest.json": {"schemaVersion": "1", "datasetVersion": "cat-new"},
        f"{base}/library/manifest.json": library_manifest,
        f"{base}/library/apps-index.json": _remote_index(new_apps),
        f"{base}/library/apps-delta.json": delta,
    }
    raw_payloads = {url: json.dumps(payload, indent=2).encode() for url, payload in payloads.items()}
    artifacts = {f"{base}/library/metadata/database-types-{DICTIONARY_SHA256}.json": DICTIONARY}
    for key in new_values:
        artifacts[f"{base}/library/apps/{key}/latest.zip"] = _zip_bytes(new_library / "apps" / key, key)
    if mode in {"race", "full-race", "package-fallback-race"}:
        (new_library / "apps" / "change" / ".env").write_bytes(b"newer mutable publication")
        artifacts[f"{base}/library/apps/change/latest.zip"] = _zip_bytes(new_library / "apps" / "change", "change")
    artifacts[f"{base}/library/full/latest.zip"] = _zip_bytes(new_library, "library")
    checksum_bytes = {
        f"{base}/library/index.sha256": raw_payloads[f"{base}/library/apps-index.json"],
        f"{base}/library/delta.sha256": raw_payloads[f"{base}/library/apps-delta.json"],
    }
    checksum_bytes.update({f"{url}.sha256": value for url, value in {**raw_payloads, **artifacts}.items()})
    requests = []
    downloads = []

    def serve(request, **kwargs):
        requests.append(request.full_url)
        if mode == "index-retry" and request.full_url.endswith("apps-index.json") and requests.count(request.full_url) == 1:
            raise TimeoutError("index download timed out")
        return BytesIO(raw_payloads[request.full_url])

    def download(url, target):
        downloads.append(url)
        if (
            mode == "dictionary-retry"
            and url.endswith(f"database-types-{DICTIONARY_SHA256}.json")
            and downloads.count(url) == 1
        ):
            raise runtime_assets.AppStoreTransientError("dictionary download timed out")
        if mode in {"dictionary-failure", "partial-failure"} and url.endswith(f"database-types-{DICTIONARY_SHA256}.json"):
            raise runtime_assets.AppStoreTransientError("dictionary unavailable")
        target.write_bytes(artifacts[url])

    monkeypatch.setattr(runtime_assets.urllib.request, "urlopen", serve)
    monkeypatch.setattr(
        runtime_assets,
        "download_text",
        lambda url: (
            "0" * 64
            if mode == "index-checksum-failure" and url.endswith("index.sha256")
            else hashlib.sha256(checksum_bytes[url]).hexdigest()
        ),
    )
    monkeypatch.setattr(runtime_assets, "download_file", download)
    if mode == "prune-failure":

        def fail_prune(*args):
            raise OSError("snapshot directory unavailable")

        monkeypatch.setattr(runtime_assets, "prune_stale_appstore_datasets", fail_prune)
    if mode in {"package-fallback", "package-fallback-race"}:

        def unavailable_app_artifacts(*args):
            raise RuntimeError("app artifact unavailable")

        monkeypatch.setattr(runtime_assets, "prepare_library_app_artifacts_source", unavailable_app_artifacts)
    real_prepare = runtime_assets.prepare_package_source
    monkeypatch.setattr(
        runtime_assets,
        "prepare_package_source",
        lambda kind, *args: new_media if kind == "media" else real_prepare(kind, *args),
    )
    result = runtime_assets.main()
    if mode in {
        "race",
        "full-race",
        "package-fallback-race",
        "index-checksum-failure",
        "dictionary-failure",
        "partial-failure",
    }:
        assert result == 1
        failed_state = json.loads(state_path.read_bytes())
        assert failed_state["syncStatus"] == "failed"
        assert failed_state["lastSyncError"]
        for key, value in json.loads(original_state).items():
            assert failed_state[key] == value
        restored = {
            str(path.relative_to(tmp_path)): path.read_bytes()
            for root in (media, library, snapshots)
            for path in root.rglob("*")
            if path.is_file()
        }
        assert restored == original_trees
        if mode == "race":
            assert f"{base}/library/full/latest.zip" not in downloads
        return
    assert result == 0
    updated_state = json.loads(state_path.read_bytes())
    assert updated_state["libraryDatasetVersion"] == "lib-new"
    assert "partial" not in updated_state
    assert {path.name for path in (library / "apps").iterdir()} == set(new_values)
    for app in new_apps:
        assert runtime_assets.app_content_fingerprint(library / "apps" / app["app"], app["app"]) == app["hash"]
    if mode in {"skipped", "fast", "index-retry", "dictionary-retry", "prune-failure"}:
        assert sorted(url for url in downloads if url.endswith(".zip")) == [
            f"{base}/library/apps/add/latest.zip",
            f"{base}/library/apps/change/latest.zip",
        ]
    elif mode == "empty":
        assert not any(url.endswith(".zip") for url in downloads)
    else:
        assert f"{base}/library/full/latest.zip" in downloads
    assert requests.count(f"{base}/library/apps-index.json") == (2 if mode == "index-retry" else 1)
    if mode == "dictionary-retry":
        assert downloads.count(f"{base}/library/metadata/database-types-{DICTIONARY_SHA256}.json") == 2
    if mode == "prune-failure":
        assert (snapshots / "releases" / "root-old").exists()
    for target in runtime_assets.library_dictionary_targets(library, updated_state["snapshots"]):
        assert target.read_bytes() == DICTIONARY
        assert json.loads((target.parents[1] / "apps-index.json").read_bytes()) == _remote_index(new_apps)


def test_unchanged_dictionary_copy_failure_propagates_without_redownload(tmp_path, monkeypatch):
    primary = tmp_path / "dictionary.json"
    primary.write_bytes(DICTIONARY)

    def failed_copy(*args):
        raise OSError("disk full")

    monkeypatch.setattr(runtime_assets, "_copy_dictionary", failed_copy)
    monkeypatch.setattr(
        runtime_assets, "download_file", lambda *args: pytest.fail("write failure must not become a read fallback")
    )
    with pytest.raises(OSError, match="disk full"):
        runtime_assets.sync_shared_database_dictionary(_bundle(), [primary, tmp_path / "snapshot.json"])


def test_prefetch_cleans_temporary_directory_if_executor_fails(tmp_path, monkeypatch):
    temporary = tmp_path / "prefetch"
    temporary.mkdir()
    monkeypatch.setattr(runtime_assets.tempfile, "mkdtemp", lambda **kwargs: str(temporary))

    def failed_executor(*args, **kwargs):
        raise RuntimeError("executor unavailable")

    monkeypatch.setattr(runtime_assets, "ThreadPoolExecutor", failed_executor)
    packages = [(kind, tmp_path / kind, tmp_path / kind / "missing") for kind in ("media", "library")]
    with pytest.raises(RuntimeError, match="executor unavailable"):
        runtime_assets.prefetch_pending_packages(
            packages, {"media": True, "library": True}, True, "dev", "https://example.test", None
        )
    assert not temporary.exists()


def test_current_bootstrap_delta_does_not_require_a_previous_version(monkeypatch):
    payload = {
        "schemaVersion": "1",
        "channel": "dev",
        "mode": "bootstrap",
        "fromVersion": None,
        "toVersion": "lib-new",
        "addedApps": [],
        "changedApps": [],
        "removedApps": [],
    }
    _serve_json(monkeypatch, payload)
    assert runtime_assets._fetch_library_json(_indexed_bundle(), "appsDelta") == payload


@pytest.fixture
def contract_v2(tmp_path, monkeypatch):
    base = "https://contract.example.test/appstore/dev"
    source_library = tmp_path / "source-library"
    apps = _write_apps(source_library, {"wordpress": 80})
    (source_library / "library.json").write_text('{"Version":"0.8.8","schemaVersion":"2"}')
    (source_library / "metadata").mkdir()
    (source_library / "metadata/database-types.json").write_bytes(DICTIONARY)
    (source_library / "metadata/secret-rules.json").write_bytes(SECRET_RULES)
    source_media = tmp_path / "source-media"
    (source_media / "json").mkdir(parents=True)
    for locale in ("en", "zh"):
        (source_media / "json" / f"product_{locale}.json").write_text('[{"key":"wordpress","title":"WordPress"}]')
        (source_media / "json" / f"catalog_{locale}.json").write_text("[]")
    catalog_content = ",".join(
        f"{name}={hashlib.sha256((source_media / 'json' / name).read_bytes()).hexdigest()}"
        for name in ("catalog_en.json", "catalog_zh.json", "product_en.json", "product_zh.json")
    )
    catalog_version = hashlib.sha256(catalog_content.encode() + b"\0").hexdigest()[:16]
    metadata = {
        "databaseTypes": {"path": "metadata/database-types-test.json", "sha256": DICTIONARY_SHA256},
        "secretRules": {"path": "metadata/secret-rules-test.json", "sha256": SECRET_RULES_SHA256},
    }
    root = {
        "schemaVersion": "2",
        "channel": "dev",
        "datasetVersion": "a" * 16,
        "catalog": {"schemaVersion": "1", "datasetVersion": catalog_version, "manifest": "catalog/manifest.json"},
        "library": {"schemaVersion": "2", "datasetVersion": "b" * 16, "manifest": "library/manifest.json"},
    }
    payloads = {
        f"{base}/manifests/appstore-manifest.json": root,
        f"{base}/catalog/manifest.json": {
            "schemaVersion": "1",
            "datasetVersion": catalog_version,
            "fullPackage": "full/latest.zip",
            "checksum": {"fullPackage": "full/latest.zip.sha256"},
        },
        f"{base}/library/manifest.json": {
            "schemaVersion": "2",
            "channel": "dev",
            "datasetVersion": "b" * 16,
            "fullPackage": "full/latest.zip",
            "appsIndex": "apps-index.json",
            "appsDelta": "apps-delta.json",
            "supportsPartialUpdate": True,
            "metadata": metadata,
            "checksum": {
                "fullPackage": "full/latest.zip.sha256",
                "appsIndex": "apps-index.json.sha256",
                "appsDelta": "apps-delta.json.sha256",
            },
        },
        f"{base}/library/apps-index.json": {
            "schemaVersion": "2",
            "channel": "dev",
            "datasetVersion": "b" * 16,
            "apps": apps,
            "metadata": metadata,
        },
        f"{base}/library/apps-delta.json": {
            "schemaVersion": "2",
            "channel": "dev",
            "fromVersion": "initial",
            "toVersion": "b" * 16,
            "addedApps": ["wordpress"],
            "changedApps": [],
            "removedApps": [],
        },
    }
    artifacts = {
        f"{base}/catalog/full/latest.zip": _zip_bytes(source_media / "json", "catalog"),
        f"{base}/library/full/latest.zip": _zip_bytes(source_library, "library"),
        f"{base}/library/apps/wordpress/latest.zip": _zip_bytes(source_library / "apps/wordpress", "wordpress"),
        f"{base}/library/{metadata['databaseTypes']['path']}": DICTIONARY,
        f"{base}/library/{metadata['secretRules']['path']}": SECRET_RULES,
    }
    requests, downloads = [], []

    def raw(url):
        if url in payloads:
            return json.dumps(payloads[url], indent=2).encode()
        return artifacts[url]

    def serve(request, **kwargs):
        requests.append(request.full_url)
        return BytesIO(raw(request.full_url))

    def checksum(url):
        requests.append(url)
        return hashlib.sha256(raw(url.removesuffix(".sha256"))).hexdigest()

    def download(url, target):
        downloads.append(url)
        target.write_bytes(raw(url))

    for name, value in {
        "WEBSOFT9_MEDIA_ROOT": tmp_path / "media",
        "WEBSOFT9_LIBRARY_ROOT": tmp_path / "library",
        "WEBSOFT9_MEDIA_MARKER": tmp_path / "media/json/product_en.json",
        "WEBSOFT9_LIBRARY_MARKER": tmp_path / "library/apps",
        "WEBSOFT9_APP_STORE_SNAPSHOT_ROOT": tmp_path / "snapshots",
        "WEBSOFT9_APP_STORE_SYNC_STATE": tmp_path / "state.json",
        "WEBSOFT9_APPSTORE_SYNC_LOCK_FILE": tmp_path / "sync.lock",
        "WEBSOFT9_APPSTORE_SYNC_PID_FILE": tmp_path / "sync.pid",
    }.items():
        monkeypatch.setenv(name, str(value))
    monkeypatch.setenv("WEBSOFT9_ARTIFACT_BASE", "https://contract.example.test")
    monkeypatch.setenv("WEBSOFT9_RUNTIME_ASSET_CHANNEL", "dev")
    monkeypatch.delenv("WEBSOFT9_RUNTIME_ASSET_FORCE_SYNC", raising=False)
    monkeypatch.delenv("WEBSOFT9_RUNTIME_ASSET_SYNC_MODE", raising=False)
    monkeypatch.setattr(runtime_assets, "_APPSTORE_SYNC_RETRY_ATTEMPTS", 1)
    monkeypatch.setattr(runtime_assets.urllib.request, "urlopen", serve)
    monkeypatch.setattr(runtime_assets, "download_text", checksum)
    monkeypatch.setattr(runtime_assets, "download_file", download)
    return base, payloads, artifacts, requests, downloads


def test_v2_cold_start_activates_full_contract_and_reuses_verified_manifests(tmp_path, contract_v2):
    base, _, _, requests, downloads = contract_v2
    assert runtime_assets.main() == 0
    state = json.loads((tmp_path / "state.json").read_bytes())
    assert state["schemaVersion"] == "2"
    assert state["catalogSchemaVersion"] == "1"
    assert state["librarySchemaVersion"] == "2"
    assert state["manifests"]["appsIndex"]["schemaVersion"] == "2"
    assert f"{base}/library/full/latest.zip" in downloads
    assert not any(url.endswith("apps-delta.json") for url in requests)
    for locale in ("en", "zh"):
        display = json.loads((tmp_path / f"media/json/app-store-manifest_{locale}.json").read_bytes())
        assert display["schemaVersion"] == "1"
        assert display["apps"][0]["key"] == "wordpress"
    requests.clear()
    downloads.clear()
    assert runtime_assets.main() == 0
    assert requests == [
        f"{base}/manifests/appstore-manifest.json",
        f"{base}/manifests/appstore-manifest.json.sha256",
    ]
    assert downloads == []


@pytest.mark.parametrize("old_schema", ["1", None])
def test_contract_migration_requires_full_even_with_identical_app_hashes(tmp_path, contract_v2, old_schema):
    base, payloads, _, requests, downloads = contract_v2
    assert runtime_assets.main() == 0
    state_path = tmp_path / "state.json"
    state = json.loads(state_path.read_bytes())
    state["schemaVersion"] = "1"
    state["datasetVersion"] = "old-root"
    state.pop("librarySchemaVersion")
    index = json.loads((tmp_path / "library/apps-index.json").read_bytes())
    if old_schema:
        index["schemaVersion"] = old_schema
    else:
        index.pop("schemaVersion")
    (tmp_path / "library/apps-index.json").write_text(json.dumps(index))
    state_path.write_text(json.dumps(state))
    payloads[f"{base}/library/apps-delta.json"]["fromVersion"] = "b" * 16
    requests.clear()
    downloads.clear()
    assert runtime_assets.main() == 0
    assert f"{base}/library/full/latest.zip" in downloads
    assert not any(url.endswith("apps-delta.json") for url in requests)
    assert json.loads(state_path.read_bytes())["librarySchemaVersion"] == "2"


def test_v2_bootstrap_flag_cannot_be_bypassed_by_index_reconciliation(tmp_path, contract_v2):
    base, payloads, _, requests, downloads = contract_v2
    assert runtime_assets.main() == 0
    payloads[f"{base}/manifests/appstore-manifest.json"]["datasetVersion"] = "d" * 16
    payloads[f"{base}/library/manifest.json"]["supportsPartialUpdate"] = False
    requests.clear()
    downloads.clear()
    assert runtime_assets.main() == 0
    assert f"{base}/library/full/latest.zip" in downloads
    assert not any(url.endswith("apps-delta.json") for url in requests)


@pytest.mark.parametrize("change", ["app", "dictionary", "app-fallback"])
def test_v2_same_contract_keeps_incremental_and_dictionary_only_updates(tmp_path, monkeypatch, contract_v2, change):
    base, payloads, artifacts, _, downloads = contract_v2
    assert runtime_assets.main() == 0
    root = payloads[f"{base}/manifests/appstore-manifest.json"]
    root["datasetVersion"] = "d" * 16
    root["library"]["datasetVersion"] = "e" * 16
    manifest = payloads[f"{base}/library/manifest.json"]
    manifest["datasetVersion"] = "e" * 16
    index = payloads[f"{base}/library/apps-index.json"]
    index["datasetVersion"] = "e" * 16
    delta = payloads[f"{base}/library/apps-delta.json"]
    delta.update(fromVersion="b" * 16, toVersion="e" * 16, addedApps=[])
    if change.startswith("app"):
        app = tmp_path / "source-library/apps/wordpress"
        (app / ".env").write_text("W9_HTTP_PORT_SET=90\n")
        index["apps"][0]["hash"] = runtime_assets.app_content_fingerprint(app, "wordpress")
        artifacts[f"{base}/library/apps/wordpress/latest.zip"] = _zip_bytes(app, "wordpress")
        artifacts[f"{base}/library/full/latest.zip"] = _zip_bytes(tmp_path / "source-library", "library")
        delta["changedApps"] = ["wordpress"]
    else:
        dictionary = DICTIONARY + b"\n"
        digest = hashlib.sha256(dictionary).hexdigest()
        manifest["metadata"]["databaseTypes"] = {"path": "metadata/database-types-next.json", "sha256": digest}
        artifacts[f"{base}/library/metadata/database-types-next.json"] = dictionary
    real_download = runtime_assets.download_file

    def download_while_ready(url, target):
        assert runtime_assets.load_sync_state(runtime_assets.runtime_assets_status_path())["status"] == "ready"
        real_download(url, target)

    monkeypatch.setattr(runtime_assets, "download_file", download_while_ready)
    if change == "app-fallback":

        def unavailable_app_artifacts(*args):
            raise RuntimeError("app artifact unavailable")

        monkeypatch.setattr(runtime_assets, "prepare_library_app_artifacts_source", unavailable_app_artifacts)
    downloads.clear()
    assert runtime_assets.main() == 0
    assert (f"{base}/library/full/latest.zip" in downloads) == (change == "app-fallback")
    if change.startswith("app"):
        if change == "app":
            assert f"{base}/library/apps/wordpress/latest.zip" in downloads
        assert (tmp_path / "library/apps/wordpress/.env").read_text() == "W9_HTTP_PORT_SET=90\n"
    else:
        assert downloads == [f"{base}/library/metadata/database-types-next.json"]
        assert (tmp_path / "library/metadata/database-types.json").read_bytes() == DICTIONARY + b"\n"
    state = json.loads((tmp_path / "state.json").read_bytes())
    assert state["syncStatus"] == "ready"
    assert state["libraryDatasetVersion"] == "e" * 16


def test_old_root_and_library_remain_supported_after_v2(tmp_path, contract_v2):
    base, payloads, artifacts, _, downloads = contract_v2
    assert runtime_assets.main() == 0
    root = payloads[f"{base}/manifests/appstore-manifest.json"]
    root["schemaVersion"] = "1"
    root["datasetVersion"] = "old-root"
    root["library"].pop("schemaVersion")
    root["catalog"].pop("schemaVersion")
    payloads[f"{base}/library/manifest.json"]["schemaVersion"] = "1"
    payloads[f"{base}/library/apps-index.json"]["schemaVersion"] = "1"
    (tmp_path / "source-library/library.json").write_text('{"Version":"0.8.7","schemaVersion":"1"}')
    artifacts[f"{base}/library/full/latest.zip"] = _zip_bytes(tmp_path / "source-library", "library")
    downloads.clear()
    assert runtime_assets.main() == 0
    state = json.loads((tmp_path / "state.json").read_bytes())
    assert state["schemaVersion"] == "1"
    assert state["librarySchemaVersion"] == "1"
    assert state["syncStatus"] == "ready"
    assert "incompatibility" not in state
    assert f"{base}/library/full/latest.zip" in downloads


@pytest.mark.parametrize("component", ["root", "catalog", "library"])
@pytest.mark.parametrize("mode", ["runtime", "build"])
def test_unknown_contract_is_rejected_before_no_change_or_payload_downloads(
    tmp_path, monkeypatch, contract_v2, component, mode
):
    base, payloads, _, _, downloads = contract_v2
    assert runtime_assets.main() == 0
    state_path = tmp_path / "state.json"
    previous = json.loads(state_path.read_bytes())
    root = payloads[f"{base}/manifests/appstore-manifest.json"]
    if component == "root":
        root["schemaVersion"] = "999"
    else:
        root[component]["schemaVersion"] = "999"
    monkeypatch.setenv("WEBSOFT9_RUNTIME_ASSET_SYNC_MODE", mode)
    downloads.clear()
    assert runtime_assets.main() == 1
    state = json.loads(state_path.read_bytes())
    assert state["syncStatus"] == "incompatible"
    assert state["datasetVersion"] == previous["datasetVersion"]
    assert state["manifests"] == previous["manifests"]
    assert state["incompatibility"]["upgradeRequired"] is False
    assert downloads == []


@pytest.mark.parametrize(
    "object_name",
    ["root", "catalog", "library", "index", "future-leaf-schema", "embedded-schema", "embedded-dictionary", "catalog-content"],
)
def test_v2_torn_publication_keeps_previous_complete_snapshot(tmp_path, contract_v2, object_name):
    base, payloads, artifacts, _, _ = contract_v2
    assert runtime_assets.main() == 0
    previous = json.loads((tmp_path / "state.json").read_bytes())
    trees = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for name in ("media", "library", "snapshots")
        for p in (tmp_path / name).rglob("*")
        if p.is_file()
    }
    root = payloads[f"{base}/manifests/appstore-manifest.json"]
    root["datasetVersion"] = "d" * 16
    if object_name == "root":
        root["library"]["schemaVersion"] = "1"
    elif object_name == "catalog":
        payloads[f"{base}/catalog/manifest.json"]["datasetVersion"] = "e" * 16
    elif object_name == "library":
        payloads[f"{base}/library/manifest.json"]["schemaVersion"] = "1"
    elif object_name == "index":
        payloads[f"{base}/library/apps-index.json"]["metadata"] = {}
    elif object_name == "future-leaf-schema":
        payloads[f"{base}/library/manifest.json"]["schemaVersion"] = "999"
    elif object_name == "catalog-content":
        root["catalog"]["datasetVersion"] = "e" * 16
        payloads[f"{base}/catalog/manifest.json"]["datasetVersion"] = "e" * 16
    else:
        source = tmp_path / "source-library"
        if object_name == "embedded-schema":
            (source / "library.json").write_text('{"schemaVersion":"1"}')
        else:
            (source / "metadata/secret-rules.json").write_text("{}")
        artifacts[f"{base}/library/full/latest.zip"] = _zip_bytes(source, "library")
        payloads[f"{base}/library/manifest.json"]["supportsPartialUpdate"] = False
    assert runtime_assets.main() == 1
    state = json.loads((tmp_path / "state.json").read_bytes())
    assert state["syncStatus"] == "failed"
    assert state["datasetVersion"] == previous["datasetVersion"]
    assert state["manifests"] == previous["manifests"]
    assert trees == {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for name in ("media", "library", "snapshots")
        for p in (tmp_path / name).rglob("*")
        if p.is_file()
    }


@pytest.mark.parametrize(
    "path", ["manifests/appstore-manifest.json", "catalog/manifest.json", "library/manifest.json", "library/apps-index.json"]
)
def test_v2_checksum_404_is_not_an_optional_legacy_checksum(tmp_path, monkeypatch, contract_v2, path):
    base, _, _, _, _ = contract_v2
    original = runtime_assets.download_text

    def missing_checksum(url):
        if url == f"{base}/{path}.sha256":
            raise runtime_assets.AppStoreTransientError("checksum absent") from runtime_assets.urllib.error.HTTPError(
                url, 404, "missing", {}, None
            )
        return original(url)

    monkeypatch.setattr(runtime_assets, "download_text", missing_checksum)
    assert runtime_assets.main() == 1
    state = json.loads((tmp_path / "state.json").read_bytes())
    assert state["syncStatus"] == "failed"
    assert "datasetVersion" not in state
    assert not (tmp_path / "library/apps").exists()


@pytest.mark.parametrize("status", ["failed", "incompatible"])
def test_a_successful_retry_clears_failed_attempt_status_and_preserves_no_change_fast_path(tmp_path, contract_v2, status):
    base, _, _, requests, downloads = contract_v2
    assert runtime_assets.main() == 0
    state_path = tmp_path / "state.json"
    previous = json.loads(state_path.read_bytes())
    previous.update(
        syncStatus=status,
        lastSyncError="previous checksum failure",
        incompatibility={"message": "previous unsupported contract"},
    )
    state_path.write_text(json.dumps(previous))
    requests.clear()
    downloads.clear()
    assert runtime_assets.main() == 0
    state = json.loads(state_path.read_bytes())
    assert state["syncStatus"] == "ready"
    assert "lastSyncError" not in state
    assert "incompatibility" not in state
    assert requests == [f"{base}/manifests/appstore-manifest.json", f"{base}/manifests/appstore-manifest.json.sha256"]
    assert downloads == []


def test_root_404_never_uses_legacy_zip_fallback(tmp_path, monkeypatch, contract_v2):
    def absent(url, *args):
        raise runtime_assets.AppStoreTransientError("root absent") from runtime_assets.urllib.error.HTTPError(
            url, 404, "missing", {}, None
        )

    monkeypatch.setattr(runtime_assets, "download_verified_json", absent)
    monkeypatch.setattr(runtime_assets, "download_file", lambda *args: pytest.fail("must not download legacy ZIPs"))
    assert runtime_assets.main() == 1
    assert json.loads((tmp_path / "state.json").read_bytes())["syncStatus"] == "failed"


@pytest.mark.parametrize(
    "manifest",
    [
        {"fullPackage": None},
        {"fullPackage": {}},
        {"fullPackage": "full.zip", "checksum": None},
        {"fullPackage": "full.zip", "checksum": {"fullPackage": None}},
    ],
)
def test_malformed_declared_archive_fields_are_not_legacy(manifest):
    bundle = {"library_manifest_url": "https://example.test/library/manifest.json", "library_manifest": manifest}
    with pytest.raises(runtime_assets.AppStoreTransientError):
        runtime_assets.resolve_package_artifact("library", "dev", "https://example.test", bundle)

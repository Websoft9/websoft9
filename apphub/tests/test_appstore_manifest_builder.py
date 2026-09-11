import importlib.util
import json
import threading
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "docker" / "scripts" / "platform-sync-runtime-assets.py"
MODULE_SPEC = importlib.util.spec_from_file_location("platform_sync_runtime_assets_test", SCRIPT_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
runtime_assets = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(runtime_assets)


def _write_product(path: Path, key: str = "wordpress") -> None:
    path.write_text(
        json.dumps([{"key": key, "title": "WordPress", "catalogBindings": {"community": "wordpress"}}]),
        encoding="utf-8",
    )


def _write_wordpress_library(library_root: Path) -> None:
    wordpress = library_root / "apps" / "wordpress"
    wordpress.mkdir(parents=True)
    (wordpress / ".env").write_text("W9_HTTP_PORT_SET=8080\nW9_URL=http://example.test:${W9_HTTP_PORT_SET}\n", encoding="utf-8")
    (wordpress / ".env.external-db").write_text("W9_DATABASE_MODE=external\nW9_DATABASE_PORT_SET=3306\n", encoding="utf-8")
    (wordpress / "variables.json").write_text(
        json.dumps({"edition": [{"dist": "community", "version": "6.6"}], "help": {"en": "https://example.test/help"}}),
        encoding="utf-8",
    )


def _write_catalogs(media_json: Path) -> None:
    catalog = [{"key": "collaboration", "title": "Collaboration", "linkedFrom": {"catalogCollection": {"items": [{"key": "document", "title": "Documents", "position": 1}]}}}]
    (media_json / "catalog_en.json").write_text(json.dumps(catalog), encoding="utf-8")
    (media_json / "catalog_zh.json").write_text(json.dumps([{**catalog[0], "title": "协作", "linkedFrom": {"catalogCollection": {"items": [{"key": "document", "title": "文档", "position": 1}]}}}]), encoding="utf-8")


def test_published_manifests_are_valid_only_when_both_locales_match_platform_schema(tmp_path):
    media_root = tmp_path / "media"
    media_json = media_root / "json"
    media_json.mkdir(parents=True)
    for locale in ("zh", "en"):
        (media_json / f"app-store-manifest_{locale}.json").write_text(
            json.dumps({"schemaVersion": "1", "locale": locale, "apps": []}),
            encoding="utf-8",
        )

    assert runtime_assets.has_valid_published_app_store_manifests(media_root) is True

    (media_json / "app-store-manifest_en.json").write_text("not json", encoding="utf-8")

    assert runtime_assets.has_valid_published_app_store_manifests(media_root) is False


def test_published_schema_version_requires_matching_locales(tmp_path):
    media_root = tmp_path / "media"
    media_json = media_root / "json"
    media_json.mkdir(parents=True)
    for locale, schema_version in (("zh", "1"), ("en", "2")):
        (media_json / f"app-store-manifest_{locale}.json").write_text(
            json.dumps({"schemaVersion": schema_version, "locale": locale, "apps": []}),
            encoding="utf-8",
        )

    with pytest.raises(runtime_assets.AppStoreCompatibilityError, match="different schemaVersions"):
        runtime_assets.get_published_app_store_schema_version(media_root)


def test_published_schema_version_uses_the_available_locale_when_the_other_is_missing(tmp_path):
    media_root = tmp_path / "media"
    manifest_path = media_root / "json" / "app-store-manifest_zh.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"schemaVersion": "1", "locale": "zh", "apps": []}),
        encoding="utf-8",
    )

    assert runtime_assets.get_published_app_store_schema_version(media_root) == "1"


def test_build_manifests_includes_complete_wordpress_metadata(tmp_path):
    media_root = tmp_path / "media"
    media_json = media_root / "json"
    media_json.mkdir(parents=True)
    _write_product(media_json / "product_zh.json")
    _write_product(media_json / "product_en.json")
    library_root = tmp_path / "library"
    _write_wordpress_library(library_root)

    runtime_assets.build_and_publish_app_store_manifests(media_root, library_root)

    wordpress = json.loads((media_json / "app-store-manifest_en.json").read_text(encoding="utf-8"))["apps"][0]
    assert wordpress["catalogBindings"] == {"community": "wordpress"}
    assert wordpress["distribution"] == [{"key": "community", "value": ["6.6"]}]
    assert wordpress["settings"]["W9_HTTP_PORT_SET"] == "8080"
    assert wordpress["is_web_app"] is True
    assert wordpress["profiles"]["external-db"]["is_external_database"] is True
    assert wordpress["help"] == {"en": "https://example.test/help"}


def test_build_manifest_adds_library_catalog_metadata_without_changing_product_entries(tmp_path):
    media_root = tmp_path / "media"
    media_json = media_root / "json"
    media_json.mkdir(parents=True)
    _write_product(media_json / "product_zh.json", "official")
    _write_product(media_json / "product_en.json", "official")
    _write_catalogs(media_json)
    library_root = tmp_path / "library"
    official = library_root / "apps" / "official"
    official.mkdir(parents=True)
    (official / ".env").write_text("W9_HTTP_PORT_SET=8080\n", encoding="utf-8")
    (official / "variables.json").write_text(json.dumps({"edition": [{"dist": "community", "version": "1.0"}]}), encoding="utf-8")
    _write_wordpress_library(library_root)
    metadata_root = library_root / "metadata" / "catalog"
    metadata_root.mkdir(parents=True)
    (metadata_root / "wordpress.json").write_text(
        json.dumps({"trademark": "WordPress", "summary": "English summary", "catalogBindings": [{"parentKey": "collaboration", "childKey": "document"}], "translations": {"zh": {"summary": "中文简介"}}}),
        encoding="utf-8",
    )

    runtime_assets.build_and_publish_app_store_manifests(media_root, library_root)

    en_apps = json.loads((media_json / "app-store-manifest_en.json").read_text(encoding="utf-8"))["apps"]
    zh_apps = json.loads((media_json / "app-store-manifest_zh.json").read_text(encoding="utf-8"))["apps"]
    assert [app["key"] for app in en_apps] == ["official", "wordpress"]
    assert [app["key"] for app in zh_apps] == ["official", "wordpress"]
    en_app = en_apps[1]
    zh_app = zh_apps[1]
    assert en_app["summary"] == "English summary"
    assert zh_app["summary"] == "中文简介"
    assert en_app["catalogCollection"]["items"][0]["title"] == "Collaboration"
    assert zh_app["catalogCollection"]["items"][0]["title"] == "协作"


def test_build_manifest_uses_metadata_base_fields_when_translations_are_absent(tmp_path):
    media_root = tmp_path / "media"
    media_json = media_root / "json"
    media_json.mkdir(parents=True)
    _write_product(media_json / "product_zh.json", "official")
    _write_product(media_json / "product_en.json", "official")
    _write_catalogs(media_json)
    library_root = tmp_path / "library"
    official = library_root / "apps" / "official"
    official.mkdir(parents=True)
    (official / ".env").write_text("W9_HTTP_PORT_SET=8080\n", encoding="utf-8")
    (official / "variables.json").write_text(json.dumps({"edition": [{"dist": "community", "version": "1.0"}]}), encoding="utf-8")
    _write_wordpress_library(library_root)
    metadata_root = library_root / "metadata" / "catalog"
    metadata_root.mkdir(parents=True)
    (metadata_root / "wordpress.json").write_text(
        json.dumps({"trademark": "WordPress", "summary": "Shared summary", "catalogBindings": [{"parentKey": "collaboration", "childKey": "document"}]}),
        encoding="utf-8",
    )

    runtime_assets.build_and_publish_app_store_manifests(media_root, library_root)

    for locale in ("en", "zh"):
        apps = json.loads((media_json / f"app-store-manifest_{locale}.json").read_text(encoding="utf-8"))["apps"]
        assert apps[1]["summary"] == "Shared summary"
        assert apps[1]["app_origin"] == "development"


def test_manifest_publish_preserves_existing_locales_when_one_locale_is_invalid(tmp_path):
    media_root = tmp_path / "media"
    media_json = media_root / "json"
    media_json.mkdir(parents=True)
    _write_product(media_json / "product_zh.json")
    (media_json / "product_en.json").write_text('[{"key":"wordpress"},{"key":"wordpress"}]', encoding="utf-8")
    (media_json / "app-store-manifest_zh.json").write_text('{"previous":"zh"}', encoding="utf-8")
    (media_json / "app-store-manifest_en.json").write_text('{"previous":"en"}', encoding="utf-8")
    library_root = tmp_path / "library"
    _write_wordpress_library(library_root)

    with pytest.raises(RuntimeError, match="duplicate app key"):
        runtime_assets.build_and_publish_app_store_manifests(media_root, library_root)

    assert (media_json / "app-store-manifest_zh.json").read_text(encoding="utf-8") == '{"previous":"zh"}'
    assert (media_json / "app-store-manifest_en.json").read_text(encoding="utf-8") == '{"previous":"en"}'


def test_build_manifest_rejects_nonempty_product_with_no_valid_entries_and_logs_missing_media(tmp_path, capsys):
    media_json = tmp_path / "media" / "json"
    media_json.mkdir(parents=True)
    _write_product(media_json / "product_en.json", "missing-template")
    library_root = tmp_path / "library" / "apps"
    (library_root / "wordpress").mkdir(parents=True)

    with pytest.raises(RuntimeError, match="no valid app entries"):
        runtime_assets.build_app_store_manifest(media_json, library_root, "en")

    output = capsys.readouterr().out
    assert "missing-template: missing Library template" in output
    assert "wordpress: missing media entry in product_en.json" in output


def test_manifest_rejects_invalid_display_metadata(tmp_path):
    media_json = tmp_path / "media" / "json"
    media_json.mkdir(parents=True)
    (media_json / "product_en.json").write_text('[{"key":"wordpress","title":0}]', encoding="utf-8")
    library_root = tmp_path / "library"
    _write_wordpress_library(library_root)

    with pytest.raises(RuntimeError, match="invalid display title"):
        runtime_assets.build_app_store_manifest(media_json, library_root / "apps", "en")


def test_manifest_allows_null_optional_screenshots(tmp_path):
    media_json = tmp_path / "media" / "json"
    media_json.mkdir(parents=True)
    (media_json / "product_en.json").write_text(
        '[{"key":"wordpress","title":"WordPress","screenshots":null}]',
        encoding="utf-8",
    )
    library_root = tmp_path / "library"
    _write_wordpress_library(library_root)

    manifest = runtime_assets.build_app_store_manifest(media_json, library_root / "apps", "en")

    assert manifest["apps"][0]["screenshots"] is None


def test_appstore_compatibility_allows_matching_schema_and_minimum_version():
    runtime_assets.check_appstore_compatibility({"schemaVersion": "1"}, "1", "2.4.0")
    runtime_assets.check_appstore_compatibility({"schemaVersion": "1", "minWebsoft9Version": "2.4.1"}, "1", "2.4.1")


def test_appstore_compatibility_rejects_newer_websoft9_requirement():
    with pytest.raises(runtime_assets.AppStoreCompatibilityError, match="requires Websoft9 >= 2.4.1"):
        runtime_assets.check_appstore_compatibility({"schemaVersion": "1", "minWebsoft9Version": "2.4.1"}, "1", "2.4.0")


def test_appstore_compatibility_rejects_mismatched_schema_without_legacy_fallback():
    with pytest.raises(runtime_assets.AppStoreCompatibilityError, match="does not match the active local schemaVersion"):
        runtime_assets.check_appstore_compatibility({"schemaVersion": "2"}, "1", "2.4.1")


def test_fetch_appstore_manifests_downloads_root_manifest_once(monkeypatch):
    artifact_base = "https://artifact.example.test"
    root_url = "https://artifact.example.test/appstore/dev/manifests/appstore-manifest.json"
    catalog_url = "https://artifact.example.test/appstore/dev/catalog/manifest.json"
    library_url = "https://artifact.example.test/appstore/dev/library/manifest.json"
    downloads = []
    payloads = {
        root_url: {
            "schemaVersion": "1",
            "catalog": {"manifest": "catalog/manifest.json"},
            "library": {"manifest": "library/manifest.json"},
        },
        catalog_url: {},
        library_url: {},
    }

    def download_json(url):
        downloads.append(url)
        return payloads[url]

    monkeypatch.setattr(runtime_assets, "download_json", download_json)

    runtime_assets.fetch_appstore_manifests(artifact_base, "dev", "1")

    assert downloads == [root_url, catalog_url, library_url]


def test_fetch_appstore_manifests_downloads_component_manifests_concurrently(monkeypatch):
    artifact_base = "https://artifact.example.test"
    root_url = "https://artifact.example.test/appstore/dev/manifests/appstore-manifest.json"
    catalog_url = "https://artifact.example.test/appstore/dev/catalog/manifest.json"
    library_url = "https://artifact.example.test/appstore/dev/library/manifest.json"
    component_started = threading.Event()
    release_components = threading.Event()
    component_urls = []

    def download_json(url):
        if url == root_url:
            return {
                "schemaVersion": "1",
                "catalog": {"manifest": "catalog/manifest.json"},
                "library": {"manifest": "library/manifest.json"},
            }
        component_urls.append(url)
        if len(component_urls) == 2:
            component_started.set()
        else:
            assert component_started.wait(timeout=1)
        assert release_components.wait(timeout=1)
        return {}

    monkeypatch.setattr(runtime_assets, "download_json", download_json)

    worker = threading.Thread(
        target=runtime_assets.fetch_appstore_manifests,
        args=(artifact_base, "dev", "1"),
    )
    worker.start()
    assert component_started.wait(timeout=1)
    release_components.set()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert set(component_urls) == {catalog_url, library_url}


def test_main_records_remote_schema_after_comparing_existing_local_manifests(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    library_root = tmp_path / "library"
    media_json = media_root / "json"
    media_json.mkdir(parents=True)
    (library_root / "apps").mkdir(parents=True)
    for locale in ("zh", "en"):
        (media_json / f"app-store-manifest_{locale}.json").write_text(
            json.dumps({"schemaVersion": "1", "locale": locale, "apps": []}),
            encoding="utf-8",
        )

    state_path = tmp_path / "state.json"

    def fetch_matching_remote_manifest(_artifact_base, _channel, local_schema_version):
        assert local_schema_version == "1"
        return {
            "appstore_manifest": {
                "schemaVersion": "1",
                "datasetVersion": "2026.09.11.120000",
                "catalog": {"datasetVersion": "catalog-1"},
                "library": {"datasetVersion": "library-1"},
            },
            "catalog_manifest": {},
            "library_manifest": {},
        }

    monkeypatch.setenv("WEBSOFT9_MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(library_root))
    monkeypatch.setenv("WEBSOFT9_MEDIA_MARKER", str(media_json / "product_en.json"))
    monkeypatch.setenv("WEBSOFT9_LIBRARY_MARKER", str(library_root / "apps"))
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SNAPSHOT_ROOT", str(tmp_path / "appstore"))
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))
    monkeypatch.setattr(runtime_assets, "fetch_appstore_manifests", fetch_matching_remote_manifest)
    monkeypatch.setattr(runtime_assets, "sync_package", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime_assets, "build_and_publish_app_store_manifests", lambda *_args: None)

    assert runtime_assets.main() == 0
    assert json.loads(state_path.read_text(encoding="utf-8"))["schemaVersion"] == "1"


def test_main_skips_delta_requests_when_all_component_versions_are_active(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    library_root = tmp_path / "library"
    media_json = media_root / "json"
    media_json.mkdir(parents=True)
    (library_root / "apps").mkdir(parents=True)
    for locale in ("zh", "en"):
        (media_json / f"app-store-manifest_{locale}.json").write_text(
            json.dumps({"schemaVersion": "1", "locale": locale, "apps": []}),
            encoding="utf-8",
        )
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1",
                "datasetVersion": "2026.09.11.120000",
                "catalogDatasetVersion": "catalog-1",
                "libraryDatasetVersion": "library-1",
            }
        ),
        encoding="utf-8",
    )

    def fetch_unchanged_manifest(*_args):
        return {
            "appstore_manifest": {
                "schemaVersion": "1",
                "datasetVersion": "2026.09.11.120000",
                "catalog": {"datasetVersion": "catalog-1"},
                "library": {"datasetVersion": "library-1"},
            },
            "catalog_manifest": {},
            "library_manifest": {},
        }

    def fail_delta_request(*_args):
        pytest.fail("unchanged Appstore data must not request delta metadata")

    monkeypatch.setenv("WEBSOFT9_MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(library_root))
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SNAPSHOT_ROOT", str(tmp_path / "appstore"))
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))
    monkeypatch.setattr(runtime_assets, "fetch_appstore_manifests", fetch_unchanged_manifest)
    monkeypatch.setattr(runtime_assets, "determine_package_sync_plan", fail_delta_request)
    monkeypatch.setattr(runtime_assets, "resolve_library_delta_context", fail_delta_request)
    monkeypatch.setattr(runtime_assets, "build_and_publish_app_store_manifests", fail_delta_request)
    monkeypatch.setattr(runtime_assets, "backup_trees", fail_delta_request)

    assert runtime_assets.main() == 0


def test_main_backs_up_assets_when_unchanged_data_requires_manifest_rebuild(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    library_root = tmp_path / "library"
    media_json = media_root / "json"
    media_json.mkdir(parents=True)
    (library_root / "apps").mkdir(parents=True)
    for locale in ("zh", "en"):
        (media_json / f"app-store-manifest_{locale}.json").write_text(
            json.dumps({"schemaVersion": "1", "locale": locale, "apps": []}),
            encoding="utf-8",
        )
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1",
                "datasetVersion": "2026.09.11.120000",
                "catalogDatasetVersion": "catalog-1",
                "libraryDatasetVersion": "library-1",
            }
        ),
        encoding="utf-8",
    )
    backup_calls = []

    def fetch_unchanged_manifest(*_args):
        return {
            "appstore_manifest": {
                "schemaVersion": "1",
                "datasetVersion": "2026.09.11.120000",
                "catalog": {"datasetVersion": "catalog-1"},
                "library": {"datasetVersion": "library-1"},
            },
            "catalog_manifest": {},
            "library_manifest": {},
        }

    def record_backup(targets, backup_root):
        backup_calls.append((targets, backup_root))
        return {}

    monkeypatch.setenv("WEBSOFT9_MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(library_root))
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SNAPSHOT_ROOT", str(tmp_path / "appstore"))
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))
    monkeypatch.setattr(runtime_assets, "fetch_appstore_manifests", fetch_unchanged_manifest)
    monkeypatch.setattr(runtime_assets, "has_valid_published_app_store_manifests", lambda _media_root: False)
    monkeypatch.setattr(runtime_assets, "backup_trees", record_backup)
    monkeypatch.setattr(runtime_assets, "build_and_publish_app_store_manifests", lambda *_args: None)

    assert runtime_assets.main() == 0
    assert len(backup_calls) == 1


def test_main_rejects_runtime_update_without_any_local_schema(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    library_root = tmp_path / "library"
    (media_root / "json").mkdir(parents=True)
    (library_root / "apps").mkdir(parents=True)
    state_path = tmp_path / "state.json"

    def fail_if_remote_manifest_is_requested(*_args):
        pytest.fail("runtime update must not request a remote manifest without local schema information")

    monkeypatch.setenv("WEBSOFT9_MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(library_root))
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SNAPSHOT_ROOT", str(tmp_path / "appstore"))
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))
    monkeypatch.setattr(runtime_assets, "fetch_appstore_manifests", fail_if_remote_manifest_is_requested)

    assert runtime_assets.main() == 1
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["syncStatus"] == "incompatible"
    assert "schemaVersion is unavailable" in state["incompatibility"]["message"]


def test_main_preserves_current_assets_when_appstore_is_incompatible(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    library_root = tmp_path / "library"
    (media_root / "json").mkdir(parents=True)
    (library_root / "apps").mkdir(parents=True)
    (media_root / "json" / "product_en.json").write_text('[{"key":"current"}]', encoding="utf-8")
    (media_root / "json" / "product_zh.json").write_text('[{"key":"current"}]', encoding="utf-8")
    for locale in ("zh", "en"):
        (media_root / "json" / f"app-store-manifest_{locale}.json").write_text(
            json.dumps({"schemaVersion": "1", "locale": locale, "apps": []}),
            encoding="utf-8",
        )
    version_path = tmp_path / "version.json"
    version_path.write_text('{"version":"2.4.0"}', encoding="utf-8")
    state_path = tmp_path / "state.json"

    def reject_manifest(*_args):
        raise runtime_assets.AppStoreCompatibilityError("appstore requires Websoft9 >= 2.4.1")

    def fail_legacy_sync(*_args, **_kwargs):
        pytest.fail("incompatible appstore must not fall back to legacy package sync")

    monkeypatch.setenv("WEBSOFT9_MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("WEBSOFT9_LIBRARY_ROOT", str(library_root))
    monkeypatch.setenv("WEBSOFT9_MEDIA_MARKER", str(media_root / "json" / "product_en.json"))
    monkeypatch.setenv("WEBSOFT9_LIBRARY_MARKER", str(library_root / "apps"))
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SNAPSHOT_ROOT", str(tmp_path / "appstore"))
    monkeypatch.setenv("WEBSOFT9_APP_STORE_SYNC_STATE", str(state_path))
    monkeypatch.setenv("WEBSOFT9_VERSION_FILE", str(version_path))
    monkeypatch.setattr(runtime_assets, "fetch_appstore_manifests", reject_manifest)
    monkeypatch.setattr(runtime_assets, "sync_package", fail_legacy_sync)

    assert runtime_assets.main() == 1
    assert (media_root / "json" / "product_en.json").read_text(encoding="utf-8") == '[{"key":"current"}]'
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["syncStatus"] == "incompatible"
    assert "requires Websoft9 >= 2.4.1" in state["incompatibility"]["message"]


def test_replace_and_restore_tree_preserves_symbolic_link_target(tmp_path):
    active_media = tmp_path / "data" / "media"
    active_media.mkdir(parents=True)
    (active_media / "version.txt").write_text("old", encoding="utf-8")
    runtime_media = tmp_path / "runtime" / "media"
    runtime_media.parent.mkdir()
    runtime_media.symlink_to(active_media, target_is_directory=True)

    updated_media = tmp_path / "updated-media"
    updated_media.mkdir()
    (updated_media / "version.txt").write_text("new", encoding="utf-8")
    rollback_root = tmp_path / "rollback"

    backups = runtime_assets.backup_trees([runtime_media], rollback_root)
    runtime_assets.replace_tree(updated_media, runtime_media)

    assert runtime_media.is_symlink()
    assert (runtime_media / "version.txt").read_text(encoding="utf-8") == "new"

    runtime_assets.restore_trees(backups)

    assert runtime_media.is_symlink()
    assert (runtime_media / "version.txt").read_text(encoding="utf-8") == "old"
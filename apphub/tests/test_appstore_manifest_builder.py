import importlib.util
import json
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
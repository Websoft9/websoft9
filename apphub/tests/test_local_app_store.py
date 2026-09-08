import json
import sys
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services import local_app_store
from src.services.local_app_store import get_local_app_store_apps, local_manifest_path, refresh_local_app_store, refresh_local_app_store_catalog, resolve_local_app_store_root


def _write_app(root: Path, key: str, media: Optional[object] = None) -> None:
    media_root = root / "catalog"
    app_root = root / "apps" / key
    media_root.mkdir(parents=True, exist_ok=True)
    app_root.mkdir(parents=True, exist_ok=True)
    payload = media if media is not None else {"title": "Canvas", "catalogBindings": [{"parentKey": "productivity", "childKey": "whiteboard"}]}
    (media_root / f"{key}.json").write_text(json.dumps(payload), encoding="utf-8")
    (app_root / ".env").write_text("W9_URL=https://$W9_URL\nW9_HTTP_PORT_SET=8080\n", encoding="utf-8")
    (app_root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (app_root / "variables.json").write_text(json.dumps({"edition": [{"dist": "community", "version": "1.0.0"}]}), encoding="utf-8")


def test_refresh_builds_and_reads_single_local_manifest(tmp_path):
    _write_app(tmp_path, "canvas")

    report = refresh_local_app_store(tmp_path)

    assert report == {"loaded": 1, "skipped": 0, "errors": []}
    apps = get_local_app_store_apps(tmp_path)
    assert apps[0]["key"] == "canvas"
    assert apps[0]["app_origin"] == "local"
    assert apps[0]["catalogCollection"]["items"][0]["key"] == "whiteboard"
    assert apps[0]["catalogCollection"]["items"][0]["catalogCollection"]["items"][0]["key"] == "productivity"
    assert local_manifest_path(tmp_path).is_file()


def test_refresh_skips_invalid_app_and_keeps_valid_apps(tmp_path):
    _write_app(tmp_path, "canvas")
    _write_app(tmp_path, "broken", media=[])

    report = refresh_local_app_store(tmp_path)

    assert report["loaded"] == 1
    assert report["skipped"] == 1
    assert report["errors"] == [{"app": "broken", "error": "media file must contain a JSON object"}]
    assert [app["key"] for app in get_local_app_store_apps(tmp_path)] == ["canvas"]


def test_refresh_preserves_previous_manifest_when_no_valid_apps_exist(tmp_path):
    _write_app(tmp_path, "canvas")
    refresh_local_app_store(tmp_path)
    _write_app(tmp_path, "broken", media=[])

    (tmp_path / "media" / "canvas.json").unlink()

    try:
        refresh_local_app_store(tmp_path)
    except ValueError as exc:
        assert "previous manifest was preserved" in str(exc)
    else:
        raise AssertionError("expected refresh to preserve the previous manifest")

    assert [app["key"] for app in get_local_app_store_apps(tmp_path)] == ["canvas"]


def test_resolve_local_app_store_root_uses_configured_root(tmp_path, monkeypatch):
    configured_root = tmp_path / "localapps"
    monkeypatch.setattr(local_app_store, "LOCAL_APP_STORE_ROOT", configured_root)

    assert resolve_local_app_store_root() == configured_root


def test_resolve_local_app_store_root_prefers_explicit_environment_path(tmp_path, monkeypatch):
    configured_root = tmp_path / "custom-local-apps"
    monkeypatch.setenv("WEBSOFT9_LOCAL_APP_STORE_ROOT", str(configured_root))
    monkeypatch.setattr(local_app_store, "LOCAL_APP_STORE_ROOT", configured_root)

    assert resolve_local_app_store_root() == configured_root


def test_catalog_refresh_rebuilds_official_and_custom_catalogs(tmp_path, monkeypatch):
    _write_app(tmp_path, "canvas")
    monkeypatch.setattr(local_app_store, "_refresh_official_app_store", lambda: {"loaded": {"zh": 2, "en": 2}, "errors": []})

    report = refresh_local_app_store_catalog(tmp_path)

    assert report == {
        "official": {"loaded": {"zh": 2, "en": 2}, "errors": []},
        "custom": {"loaded": 1, "skipped": 0, "errors": []},
    }


def test_catalog_refresh_preserves_each_catalog_failure_in_its_report(tmp_path, monkeypatch):
    monkeypatch.setattr(local_app_store, "_refresh_official_app_store", lambda: (_ for _ in ()).throw(RuntimeError("invalid official metadata")))
    _write_app(tmp_path, "broken", media=[])

    report = refresh_local_app_store_catalog(tmp_path)

    assert report["official"]["errors"] == [{"error": "invalid official metadata"}]
    assert report["custom"]["skipped"] == 1
    assert "previous manifest was preserved" in report["custom"]["errors"][0]["error"]
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


LOCAL_APP_STORE_ROOT = Path(os.getenv("WEBSOFT9_LOCAL_APP_STORE_ROOT", "/opt/websoft9/data/local-apps"))
_APP_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def local_manifest_path(root: Path = LOCAL_APP_STORE_ROOT) -> Path:
    return root / "manifest" / "app-store-manifest.json"


def _load_env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _get_distribution(metadata: object) -> list[dict[str, object]]:
    if not isinstance(metadata, list):
        return []

    distributions: dict[str, list[str]] = {}
    for item in metadata:
        if not isinstance(item, dict):
            continue
        dist = item.get("dist")
        versions = item.get("version")
        if isinstance(versions, str):
            versions = [versions]
        if not isinstance(dist, str) or not isinstance(versions, list):
            continue
        cleaned_versions = [value.strip() for value in versions if isinstance(value, str) and value.strip()]
        if cleaned_versions:
            distributions.setdefault(dist.strip(), []).extend(cleaned_versions)
    return [{"key": key, "value": value} for key, value in distributions.items() if key]


def _catalog_collection(bindings: object) -> dict[str, object]:
    items: dict[str, dict[str, object]] = {}
    if not isinstance(bindings, list):
        return {"items": []}
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        parent_key = binding.get("parentKey")
        child_key = binding.get("childKey")
        if not isinstance(parent_key, str) or not parent_key.strip():
            continue
        parent = items.setdefault(parent_key.strip(), {"key": parent_key.strip(), "catalogCollection": {"items": []}})
        if isinstance(child_key, str) and child_key.strip():
            parent["catalogCollection"]["items"].append({"key": child_key.strip()})
    return {"items": list(items.values())}


def _discover_profiles(app_dir: Path) -> dict[str, dict[str, object]]:
    profiles: dict[str, dict[str, object]] = {}
    for env_path in sorted(app_dir.glob(".env.*")):
        match = re.fullmatch(r"\.env\.([a-z0-9][a-z0-9-]*)", env_path.name)
        if not match or match.group(1) == "example":
            continue
        values = _load_env_values(env_path)
        profile: dict[str, object] = {
            "settings": {key: value for key, value in values.items() if key.startswith("W9_") and key.endswith("_SET")},
        }
        if values.get("W9_DATABASE_MODE") == "external":
            profile["is_external_database"] = True
        profiles[match.group(1)] = profile
    return profiles


def _build_app(media_path: Path, library_root: Path) -> dict[str, object]:
    app_key = media_path.stem
    if not _APP_KEY_PATTERN.fullmatch(app_key):
        raise ValueError("file name must be a lowercase application key")
    media = json.loads(media_path.read_text(encoding="utf-8"))
    if not isinstance(media, dict):
        raise ValueError("media file must contain a JSON object")
    if "screenshots" in media and media["screenshots"] is not None and not isinstance(media["screenshots"], list):
        raise ValueError("screenshots must be an array or null")

    app_dir = library_root / app_key
    env_path = app_dir / ".env"
    variables_path = app_dir / "variables.json"
    compose_path = app_dir / "docker-compose.yml"
    if not env_path.is_file() or not variables_path.is_file() or not compose_path.is_file():
        raise ValueError("Library requires .env, docker-compose.yml, and variables.json")
    variables = json.loads(variables_path.read_text(encoding="utf-8"))
    if not isinstance(variables, dict):
        raise ValueError("variables.json must contain a JSON object")
    distribution = _get_distribution(variables.get("edition"))
    if not distribution:
        raise ValueError("variables.json has no valid edition")

    env_values = _load_env_values(env_path)
    manifest = dict(media)
    manifest.pop("catalogBindings", None)
    manifest.update({
        "key": app_key,
        "catalogCollection": _catalog_collection(media.get("catalogBindings")),
        "distribution": distribution,
        "settings": {key: value for key, value in env_values.items() if key.startswith("W9_") and key.endswith("_SET")},
        "is_web_app": "W9_URL" in env_values,
        "app_origin": "local",
    })
    profiles = _discover_profiles(app_dir)
    if profiles:
        manifest["profiles"] = profiles
    if isinstance(variables.get("help"), dict):
        manifest["help"] = variables["help"]
    return manifest


def refresh_local_app_store(root: Path = LOCAL_APP_STORE_ROOT) -> dict[str, Any]:
    media_root = root / "media"
    library_root = root / "library" / "apps"
    apps: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    if media_root.is_dir():
        for media_path in sorted(media_root.glob("*.json")):
            try:
                apps.append(_build_app(media_path, library_root))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append({"app": media_path.stem, "error": str(exc)})
    if errors and not apps:
        raise ValueError("no valid local applications were found; the previous manifest was preserved")
    manifest: dict[str, object] = {"schemaVersion": "1", "locale": "local", "apps": apps}
    target_path = local_manifest_path(root)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target_path.parent, delete=False) as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(target_path)
    return {"loaded": len(apps), "skipped": len(errors), "errors": errors}


def get_local_app_store_apps(root: Path = LOCAL_APP_STORE_ROOT) -> list[dict[str, object]]:
    manifest_path = local_manifest_path(root)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"local app store manifest is unavailable: {exc}") from exc
    apps = manifest.get("apps") if isinstance(manifest, dict) else None
    if manifest.get("schemaVersion") != "1" or manifest.get("locale") != "local" or not isinstance(apps, list):
        raise ValueError("local app store manifest has an unsupported schema")
    if any(not isinstance(app, dict) or app.get("app_origin") != "local" for app in apps):
        raise ValueError("local app store manifest contains an invalid app")
    return apps
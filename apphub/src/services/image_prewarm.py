"""Prepare application images from an App Store library template."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import docker
import yaml

from src.core.config import ConfigManager
from src.core.exception import CustomException
from src.services.image_pull import (
    ImagePullError,
    collect_compose_images,
    pull_error_detail,
    pull_with_fallback,
    validate_image_reference,
)


class ImagePrewarmService:
    """Pull all images required by one supported application version."""

    def __init__(self, library_path: str | None = None, docker_client=None):
        self.library_path = Path(
            library_path
            or ConfigManager("system.ini").get_value("docker_library", "path")
        )
        self.docker_client = docker_client

    def prewarm(self, app_name: str, version: str, on_progress=None) -> dict[str, Any]:
        images = self._images_for(app_name, version)
        client = self.docker_client or docker.DockerClient(base_url="unix://var/run/docker.sock")
        pulled: list[str] = []
        present: list[str] = []
        for image in images:
            try:
                client.images.get(image)
                present.append(image)
                if on_progress is not None:
                    on_progress({"event": "image-ready", "image": image})
                continue
            except docker.errors.ImageNotFound:
                pass
            if on_progress is not None:
                on_progress({"event": "image-pull-started", "image": image})
            try:
                pull_with_fallback(client, image, on_progress=on_progress)
                pulled.append(image)
                if on_progress is not None:
                    on_progress({"event": "image-pull-completed", "image": image})
            except ImagePullError as exc:
                raise CustomException(500, "Image Prewarm Error", pull_error_detail(exc)) from exc

        return {
            "app": app_name,
            "version": version,
            "images": images,
            "pulled": pulled,
            "already_present": present,
        }

    def status(self, app_name: str, version: str) -> dict[str, Any]:
        images = self._images_for(app_name, version)
        client = self.docker_client or docker.DockerClient(base_url="unix://var/run/docker.sock")
        missing: list[str] = []
        for image in images:
            try:
                client.images.get(image)
            except docker.errors.ImageNotFound:
                missing.append(image)
        return {"app": app_name, "version": version, "ready": not missing, "images": images, "missing": missing}

    def _images_for(self, app_name: str, version: str) -> list[str]:
        app_name = str(app_name or "").strip()
        version = str(version or "").strip()
        app_directory = self.library_path / app_name
        self._validate(app_directory, app_name, version)

        compose_path = app_directory / "docker-compose.yml"
        env_values = self._read_env(app_directory / ".env")
        env_values["W9_VERSION"] = version
        try:
            compose = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise CustomException(500, "Image Prewarm Error", "Unable to read the application compose template.") from exc

        images = collect_compose_images(compose, env_values)
        if not images:
            raise CustomException(500, "Image Prewarm Error", "The application has no pullable images.")
        try:
            return [validate_image_reference(image) for image in images]
        except ImagePullError as exc:
            raise CustomException(500, "Image Prewarm Error", pull_error_detail(exc)) from exc

    @staticmethod
    def _read_env(path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
        return values

    @staticmethod
    def _validate(app_directory: Path, app_name: str, version: str) -> None:
        try:
            variables = json.loads((app_directory / "variables.json").read_text(encoding="utf-8"))
            editions = variables.get("edition", [])
            supported = any(
                isinstance(entry, dict)
                and entry.get("dist") == "community"
                and version in entry.get("version", [])
                for entry in editions
            )
        except (OSError, json.JSONDecodeError, AttributeError, TypeError) as exc:
            raise CustomException(400, "Invalid Prewarm Request", f"Application '{app_name}' is not available.") from exc
        if not supported:
            raise CustomException(400, "Invalid Prewarm Request", f"Application version '{version}' is not supported.")
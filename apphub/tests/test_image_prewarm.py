import json
import sys
from pathlib import Path

import docker
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.image_prewarm import ImagePrewarmService


@pytest.mark.parametrize("refresh", [False, True])
def test_prewarm_uses_requested_version_and_skips_present_image(monkeypatch, tmp_path, refresh):
    app_directory = tmp_path / "library" / "wordpress"
    app_directory.mkdir(parents=True)
    (app_directory / ".env").write_text("W9_VERSION=old\n", encoding="utf-8")
    (app_directory / "variables.json").write_text(
        json.dumps({"edition": [{"dist": "community", "version": ["6.3"]}]}),
        encoding="utf-8",
    )
    (app_directory / "docker-compose.yml").write_text(
        "services:\n  app:\n    image: wordpress:${W9_VERSION}\n  db:\n    image: mariadb:11\n",
        encoding="utf-8",
    )

    class Images:
        def get(self, image):
            if image == "wordpress:6.3":
                return object()
            raise docker.errors.ImageNotFound("missing")

    class Client:
        images = Images()

    pulled = []
    monkeypatch.setattr(
        "src.services.image_prewarm.pull_with_fallback", lambda _client, image, **_kwargs: pulled.append(image)
    )

    result = ImagePrewarmService(library_path=str(tmp_path / "library"), docker_client=Client()).prewarm(
        "wordpress", "6.3", refresh=refresh
    )

    assert result["images"] == ["wordpress:6.3", "mariadb:11"]
    assert result["already_present"] == ([] if refresh else ["wordpress:6.3"])
    assert result["pulled"] == (["wordpress:6.3", "mariadb:11"] if refresh else ["mariadb:11"])
    assert pulled == result["pulled"]


@pytest.mark.parametrize("status", ["unavailable", "updating"])
def test_prewarm_requires_verified_official_assets_unless_explicit_library_is_given(monkeypatch, tmp_path, status):
    import os

    from src.api.v1.routers import app as app_router
    from src.core.exception import CustomException
    from src.schemas.scheduledTasks import ImagePrewarmRequest

    app_directory = tmp_path / "library" / "wordpress"
    app_directory.mkdir(parents=True)
    (app_directory / ".env").write_text("W9_VERSION=6.3\n", encoding="utf-8")
    (app_directory / "variables.json").write_text(
        json.dumps({"edition": [{"dist": "community", "version": ["6.3"]}]}),
        encoding="utf-8",
    )
    (app_directory / "docker-compose.yml").write_text("services:\n  app:\n    image: wordpress:6.3\n", encoding="utf-8")

    class Images:
        def get(self, _image):
            return object()

    class Client:
        images = Images()

    Path(os.environ["WEBSOFT9_APPSTORE_RUNTIME_STATE_FILE"]).write_text(json.dumps({"status": status}))

    with pytest.raises(CustomException) as prewarm_err:
        ImagePrewarmService(docker_client=Client()).status("wordpress", "6.3")
    assert prewarm_err.value.status_code == 503
    assert prewarm_err.value.message == "App Store Assets Unavailable"

    class FakeAuth:
        def _require_authenticated_operator(self, _token):
            return {"id": "op-1"}

    class FakeTasks:
        auth_service = FakeAuth()

    monkeypatch.setattr(app_router, "ScheduledTaskService", lambda: FakeTasks())
    with pytest.raises(CustomException) as router_err:
        app_router.enqueue_app_image_prewarm(
            ImagePrewarmRequest(app_name="wordpress", version="6.3", refresh=False), "valid-token"
        )
    assert router_err.value.status_code == 503
    assert router_err.value.message == "App Store Assets Unavailable"

    explicit = ImagePrewarmService(library_path=str(tmp_path / "library"), docker_client=Client()).status("wordpress", "6.3")
    assert explicit["ready"] is True

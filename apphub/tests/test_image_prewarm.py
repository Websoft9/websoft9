import json
import sys
from pathlib import Path

import docker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.image_prewarm import ImagePrewarmService


def test_prewarm_uses_requested_version_and_skips_present_image(monkeypatch, tmp_path):
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
    monkeypatch.setattr("src.services.image_prewarm.pull_with_fallback", lambda _client, image, **_kwargs: pulled.append(image))

    result = ImagePrewarmService(library_path=str(tmp_path / "library"), docker_client=Client()).prewarm("wordpress", "6.3")

    assert result["images"] == ["wordpress:6.3", "mariadb:11"]
    assert result["already_present"] == ["wordpress:6.3"]
    assert result["pulled"] == ["mariadb:11"]
    assert pulled == ["mariadb:11"]
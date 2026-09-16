import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services import image_pull
from src.services.image_pull import (
    DEFAULT_IMAGE_REPO,
    ECR_PUBLIC_IMAGE_REPO,
    ImagePullError,
    ecr_candidates,
    load_image_accelerators,
    parse_accelerator_entries,
    pull_with_fallback,
    require_local_image,
    split_reference,
)


def version_tar(version: str) -> bytes:
    payload = json.dumps({"version": version, "channel": "release"}).encode("utf-8")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo("version.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


class FakeImage:
    def __init__(self, image_id: str, digest: str = ""):
        self.id = image_id
        self.attrs = {"RepoDigests": [f"registry.example.test/websoft9/websoft9@{digest}"] if digest else []}


class FakeImages:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.pulled: list[str] = []
        self.removed: list[str] = []
        self.local: dict[str, FakeImage] = {}

    def pull(self, reference):
        self.pulled.append(reference)
        outcome = self.outcomes.get(reference)
        if outcome is None:
            raise RuntimeError(f"pull failed: {reference}")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def get(self, reference):
        image = self.local.get(reference)
        if image is None:
            raise RuntimeError(f"No such image: {reference}")
        return image

    def remove(self, reference, force=False, noprune=False):
        self.removed.append(reference)


class FakeApi:
    """Serves the version probe (`/websoft9/version.json`) without running a container."""

    def __init__(self, versions=None):
        self.tags: list[tuple] = []
        self.versions = versions or {}
        self.probed: list[str] = []
        self.removed_containers: list[str] = []

    def tag(self, image, repository, tag=None, force=False):
        self.tags.append((image, repository, tag))

    def create_container(self, reference, command=None):
        self.probed.append(reference)
        return {"Id": f"probe-{len(self.probed)}"}

    def get_archive(self, container_id, path):
        reference = self.probed[int(container_id.rsplit("-", 1)[-1]) - 1]
        version = self.versions.get(reference, "")
        if not version:
            raise RuntimeError(f"no version file in {reference}")
        return iter([version_tar(version)]), {}

    def remove_container(self, container_id, force=False):
        self.removed_containers.append(container_id)


class FakeClient:
    def __init__(self, outcomes, versions=None):
        self.images = FakeImages(outcomes)
        self.api = FakeApi(versions)


class FakeConfig:
    def __init__(self, value=""):
        self.value = value
        self.written = None

    def get_value(self, section, key):
        return self.value

    def set_value(self, section, key, value):
        self.written = (section, key, value)
        self.value = value


def test_split_reference_keeps_a_registry_port_out_of_the_tag():
    assert split_reference("websoft9dev/websoft9:2.4.1") == ("websoft9dev/websoft9", "2.4.1")
    assert split_reference("docker:27.3-cli@sha256:" + "a" * 64) == ("docker", "27.3-cli")
    assert split_reference("localhost:5000/websoft9:2.4.1") == ("localhost:5000/websoft9", "2.4.1")
    assert split_reference("localhost:5000/websoft9") == ("localhost:5000/websoft9", "")


def test_direct_pull_wins_and_needs_no_alias():
    digest = "sha256:" + "a" * 64
    client = FakeClient({"websoft9dev/websoft9:2.4.1": FakeImage("sha256:local", digest)})

    result = pull_with_fallback(client, "websoft9dev/websoft9:2.4.1", accelerators=["mirror.example.test"])

    assert result.source == "direct"
    assert result.digest == digest
    assert client.images.pulled == ["websoft9dev/websoft9:2.4.1"]
    # The plain tag is always ensured, because a digest pull can leave the image untagged.
    assert client.api.tags == [("sha256:local", "websoft9dev/websoft9", "2.4.1")]


def test_pull_falls_back_to_amazon_ecr_public_for_a_pinned_release_via_its_alias():
    digest = "sha256:" + "b" * 64
    alias_reference = f"{ECR_PUBLIC_IMAGE_REPO}:2.4"
    client = FakeClient(
        {alias_reference: FakeImage("sha256:ecr", digest)},
        {alias_reference: "2.4.1"},
    )

    result = pull_with_fallback(
        client,
        f"{DEFAULT_IMAGE_REPO}:2.4.1",
        expected_version="2.4.1",
        alias_tags=["websoft9dev/websoft9:latest", "websoft9dev/websoft9:2.4"],
        accelerators=[],
    )

    assert result.source == alias_reference
    assert result.digest == digest
    assert client.images.pulled == [f"{DEFAULT_IMAGE_REPO}:2.4.1", alias_reference]
    assert client.api.tags == [("sha256:ecr", DEFAULT_IMAGE_REPO, "2.4.1")]


def test_ecr_alias_is_rejected_when_it_already_moved_to_a_newer_patch():
    alias_reference = f"{ECR_PUBLIC_IMAGE_REPO}:2.4"
    mirror_reference = "mirror.example.test/websoft9dev/websoft9:2.4.1"
    client = FakeClient(
        {
            alias_reference: FakeImage("sha256:ecr", "sha256:" + "c" * 64),
            mirror_reference: FakeImage("sha256:mirror", "sha256:" + "d" * 64),
        },
        {alias_reference: "2.4.3", mirror_reference: "2.4.1"},
    )

    result = pull_with_fallback(
        client,
        f"{DEFAULT_IMAGE_REPO}:2.4.1",
        expected_version="2.4.1",
        alias_tags=["2.4"],
        accelerators=["mirror.example.test"],
    )

    assert result.source == mirror_reference
    assert client.images.removed == [alias_reference]
    assert client.api.removed_containers


def test_ecr_is_skipped_for_foreign_repositories():
    client = FakeClient({})

    with pytest.raises(ImagePullError):
        pull_with_fallback(client, "other/image:2.4.1", accelerators=[])

    assert not any("ecr.aws" in reference for reference in client.images.pulled)
    assert ecr_candidates("other/image:2.4.1", ["latest"]) == []


def test_ecr_candidates_cover_the_docker_hub_official_mirror():
    digest = "sha256:" + "a" * 64

    assert ecr_candidates(f"docker:29.8.0-cli@{digest}") == [
        f"public.ecr.aws/docker/library/docker:29.8.0-cli@{digest}"
    ]
    assert ecr_candidates("alpine:3.20") == ["public.ecr.aws/docker/library/alpine:3.20"]
    # Namespaced Docker Hub images are not mirrored there.
    assert ecr_candidates("websoft9dev/other:1.0") == []


def test_runner_image_falls_back_to_the_ecr_library_mirror():
    digest = "sha256:" + "b" * 64
    reference = f"docker:29.8.0-cli@{digest}"
    ecr_reference = f"public.ecr.aws/docker/library/docker:29.8.0-cli@{digest}"
    client = FakeClient({ecr_reference: FakeImage("sha256:mirror", digest)})

    result = pull_with_fallback(client, reference, accelerators=[])

    assert result.source == ecr_reference
    assert result.digest == digest
    assert client.api.tags == [("sha256:mirror", "docker", "29.8.0-cli")]


def test_ecr_alias_order_prefers_the_minor_alias_over_latest():
    assert ecr_candidates("websoft9dev/websoft9:2.4.1", ["websoft9dev/websoft9:latest"]) == [
        f"{ECR_PUBLIC_IMAGE_REPO}:2.4",
        f"{ECR_PUBLIC_IMAGE_REPO}:latest",
    ]
    assert ecr_candidates("websoft9dev/websoft9:2.4-dev", []) == [f"{ECR_PUBLIC_IMAGE_REPO}:2.4-dev"]


def test_accelerated_pull_tries_the_library_prefix_for_official_images():
    digest = "sha256:" + "c" * 64
    reference = "docker:27.3-cli@" + digest
    mirror_reference = f"mirror.example.test/library/docker:27.3-cli@{digest}"
    client = FakeClient({mirror_reference: FakeImage("sha256:mirror", "sha256:" + "d" * 64)})

    result = pull_with_fallback(client, reference, accelerators=["mirror.example.test"])

    assert result.source == mirror_reference
    assert result.digest == "sha256:" + "d" * 64
    assert client.images.pulled == [
        reference,
        f"public.ecr.aws/docker/library/docker:27.3-cli@{digest}",
        f"mirror.example.test/docker:27.3-cli@{digest}",
        mirror_reference,
    ]
    assert client.api.tags == [("sha256:mirror", "docker", "27.3-cli")]


def test_accelerators_are_tried_in_order_until_one_answers():
    mirror_reference = "mirror-b.example.test/websoft9dev/websoft9:2.4.1"
    client = FakeClient({mirror_reference: FakeImage("sha256:mirror-b", "sha256:" + "e" * 64)})

    result = pull_with_fallback(
        client,
        "websoft9dev/websoft9:2.4.1",
        accelerators=["mirror-a.example.test", "mirror-b.example.test"],
    )

    assert result.source == mirror_reference
    assert "mirror-a.example.test" in " ".join(client.images.pulled)
    assert client.api.tags == [("sha256:mirror-b", "websoft9dev/websoft9", "2.4.1")]


def test_every_failed_source_is_reported():
    client = FakeClient({})

    with pytest.raises(ImagePullError) as error:
        pull_with_fallback(
            client,
            "websoft9dev/websoft9:2.4-dev",
            accelerators=["mirror.example.test"],
        )

    message = str(error.value)
    assert "direct pull" in message
    assert "Amazon ECR Public" in message
    assert "mirror mirror.example.test" in message


def test_an_unreadable_version_probe_does_not_block_the_upgrade():
    reference = f"{ECR_PUBLIC_IMAGE_REPO}:2.4"
    client = FakeClient({reference: FakeImage("sha256:ecr", "sha256:" + "f" * 64)}, {})

    result = pull_with_fallback(
        client,
        f"{DEFAULT_IMAGE_REPO}:2.4.1",
        expected_version="2.4.1",
        alias_tags=["2.4"],
        accelerators=[],
    )

    assert result.source == reference
    assert client.images.removed == []


def test_accelerator_entries_are_normalized_and_deduplicated():
    config = FakeConfig("mirror-a.example.test\nmirror-a.example.test, mirror-b.example.test/")

    assert load_image_accelerators(config=config) == ["mirror-a.example.test", "mirror-b.example.test"]


def test_accelerator_url_is_resolved_and_cached(monkeypatch):
    config = FakeConfig("https://artifact.example.test/mirrors.json")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"mirrors": ["http://mirror-c.example.test/"]}

    monkeypatch.setattr(image_pull.requests, "get", lambda url, timeout=None: Response())

    assert load_image_accelerators(config=config) == ["mirror-c.example.test"]
    assert config.written is not None
    assert config.written[0] == "docker_mirror"


def test_unreachable_accelerator_url_falls_back_to_the_bundled_mirrors(monkeypatch, tmp_path):
    config = FakeConfig("https://artifact.example.test/mirrors.json")
    local_file = tmp_path / "mirrors.json"
    local_file.write_text(json.dumps({"mirrors": ["mirror-d.example.test"]}), encoding="utf-8")
    monkeypatch.setattr(image_pull, "LOCAL_MIRROR_FILE", str(local_file))

    def offline(url, timeout=None):
        raise RuntimeError("offline")

    monkeypatch.setattr(image_pull.requests, "get", offline)

    assert load_image_accelerators(config=config) == ["mirror-d.example.test"]


def test_parse_accelerator_entries_drops_empty_values():
    assert parse_accelerator_entries("\n , mirror.example.test \n") == ["mirror.example.test"]


def test_require_local_image_resolves_the_tag_and_checks_the_digest():
    digest = "sha256:" + "a" * 64
    client = FakeClient({})
    client.images.local["docker:27.3-cli"] = FakeImage("sha256:local", digest)

    image = require_local_image(client, f"docker:27.3-cli@{digest}", digest)

    assert image.id == "sha256:local"


def test_require_local_image_rejects_a_missing_pin():
    client = FakeClient({})
    client.images.local["docker:27.3-cli"] = FakeImage("sha256:local", "sha256:" + "0" * 64)

    with pytest.raises(ImagePullError, match="does not carry the pinned digest"):
        require_local_image(client, "docker:27.3-cli", "sha256:" + "a" * 64)


def test_require_local_image_reports_an_absent_image():
    client = FakeClient({})

    with pytest.raises(ImagePullError, match="is not available locally"):
        require_local_image(client, "docker:27.3-cli", "sha256:" + "a" * 64)


def test_require_local_image_falls_back_to_the_pinned_reference():
    digest = "sha256:" + "a" * 64
    client = FakeClient({})
    # An image pulled by digest alone is reachable through the digest, not through the tag.
    client.images.local[f"docker:27.3-cli@{digest}"] = FakeImage("sha256:local", digest)

    image = require_local_image(client, f"docker:27.3-cli@{digest}", digest)

    assert image.id == "sha256:local"

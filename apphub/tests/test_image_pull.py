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
from src.services.docker_mirror_store import DockerMirrorStore
from src.services.image_pull import (
    DEFAULT_IMAGE_REPO,
    ECR_PUBLIC_IMAGE_REPO,
    MAX_REASON_LENGTH,
    ImagePullError,
    build_pull_plan,
    concise_reason,
    describe_pull_failure,
    ecr_candidates,
    load_image_accelerators,
    pull_error_detail,
    pull_with_fallback,
    pull_with_fallback_async,
    require_local_image,
    split_reference,
    validate_image_reference,
)
from src.services.mirror_registry import Accelerator, MirrorRegistry


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
        self.auth: list[dict | None] = []
        self.removed: list[str] = []
        self.local: dict[str, FakeImage] = {}

    def pull(self, reference, **kwargs):
        self.pulled.append(reference)
        self.auth.append(kwargs.get("auth_config"))
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

    def pull(self, reference, stream=False, decode=False, auth_config=None):
        """Yield one progress line per pull, like the daemon does."""
        yield {"status": "pulling", "id": reference}

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
        use_ecr_public=True,
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
        use_ecr_public=True,
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

    result = pull_with_fallback(client, reference, accelerators=[], use_ecr_public=True)

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

    result = pull_with_fallback(
        client, reference, accelerators=["mirror.example.test"], use_ecr_public=True
    )

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
            use_ecr_public=True,
        )

    message = str(error.value)
    assert "direct pull" in message
    assert "Amazon ECR Public" in message
    assert "mirror mirror.example.test" in message


def test_failure_message_lists_every_source_with_its_reason():
    client = FakeClient({})

    with pytest.raises(ImagePullError) as error:
        pull_with_fallback(
            client,
            "websoft9dev/websoft9:2.4.1",
            accelerators=["mirror-a.example.test", "mirror-b.example.test"],
        )

    message = str(error.value)
    assert message.startswith("Unable to pull image 'websoft9dev/websoft9:2.4.1'.")
    assert "Tried 3 source(s), in order:" in message
    # Every source is named with the reference it actually requested, so the operator can tell
    # which accelerator to look at first.
    assert "  - direct pull [websoft9dev/websoft9:2.4.1]: " in message
    assert "  - mirror mirror-a.example.test [mirror-a.example.test/websoft9dev/websoft9:2.4.1]: " in message
    assert "  - mirror mirror-b.example.test [mirror-b.example.test/websoft9dev/websoft9:2.4.1]: " in message
    assert "Settings > Image Accelerator" in message


@pytest.mark.asyncio
async def test_async_failure_message_lists_every_source_with_its_reason():
    class AsyncImages:
        def pull(self, reference, **_kwargs):
            async def stream():
                raise RuntimeError(f"no such manifest: {reference}")
                yield  # pragma: no cover - makes this an async generator

            return stream()

    class AsyncClient:
        images = AsyncImages()

    with pytest.raises(ImagePullError) as error:
        await pull_with_fallback_async(
            AsyncClient(),
            "websoft9dev/websoft9:2.4.1",
            accelerators=["mirror-a.example.test"],
        )

    message = str(error.value)
    assert "direct pull [websoft9dev/websoft9:2.4.1]: no such manifest" in message
    assert "mirror mirror-a.example.test" in message


def test_a_multi_line_reason_is_collapsed_to_one_bounded_line():
    noisy = "manifest unknown\n" + "detail " * 200

    reason = concise_reason(RuntimeError(noisy))

    assert "\n" not in reason
    assert len(reason) <= MAX_REASON_LENGTH
    assert reason.endswith("…")


def test_a_docker_api_error_drops_the_transport_url_it_repeats():
    raw = (
        "404 Client Error for http+docker://localhost/v1.55/images/create?tag=0.0.1"
        "&fromImage=websoft9dev%2Fmissing: Not Found (\"pull access denied\")"
    )

    # The reference is already named next to the reason, so the daemon URL only adds noise.
    assert concise_reason(RuntimeError(raw)) == 'Not Found ("pull access denied")'


def test_failure_message_without_any_source_still_explains_itself():
    message = describe_pull_failure("websoft9dev/websoft9:2.4.1", [])

    assert "No pull source was available for this image." in message
    assert "Settings > Image Accelerator" in message


def test_pull_error_detail_prefers_the_specific_text_the_exception_carries():
    class WithDetails(Exception):
        details = "direct pull: connection refused"

    assert pull_error_detail(WithDetails("ignored")) == "direct pull: connection refused"
    assert pull_error_detail(RuntimeError("boom")) == "boom"
    # A bare exception carries nothing an operator can act on, so the caller's wording is kept.
    assert pull_error_detail(RuntimeError("")) == "Pulling the application images failed"
    assert pull_error_detail(RuntimeError("Internal Server Error")) == (
        "Pulling the application images failed"
    )


def test_an_invalid_reference_names_the_likely_cause():
    with pytest.raises(ImagePullError) as error:
        validate_image_reference("${IMAGE_REPO}:latest")

    assert "missing from the application's .env" in str(error.value)


def test_an_unreadable_version_probe_does_not_block_the_upgrade():
    reference = f"{ECR_PUBLIC_IMAGE_REPO}:2.4"
    client = FakeClient({reference: FakeImage("sha256:ecr", "sha256:" + "f" * 64)}, {})

    result = pull_with_fallback(
        client,
        f"{DEFAULT_IMAGE_REPO}:2.4.1",
        expected_version="2.4.1",
        alias_tags=["2.4"],
        accelerators=[],
        use_ecr_public=True,
    )

    assert result.source == reference
    assert client.images.removed == []


def test_load_image_accelerators_answers_from_the_registry(tmp_path):
    registry = MirrorRegistry(
        store=DockerMirrorStore(tmp_path / "platform.sqlite"), data_root=tmp_path
    )
    registry.store.replace_entries(
        [{"url": "registry.example.test", "username": "ops", "password": "s3cret"}]
    )

    accelerators = load_image_accelerators(registry=registry)

    assert [item.url for item in accelerators] == ["registry.example.test"]
    assert accelerators[0].auth_config() == {"username": "ops", "password": "s3cret"}


@pytest.mark.asyncio
async def test_async_pull_uses_default_accelerator_when_no_addresses_are_configured(tmp_path):
    registry = MirrorRegistry(
        store=DockerMirrorStore(tmp_path / "platform.sqlite"), data_root=tmp_path
    )
    registry.default_list_file.parent.mkdir(parents=True, exist_ok=True)
    registry.default_list_file.write_text(
        json.dumps({"mirrors": ["default.example.test"]}), encoding="utf-8"
    )
    pulled: list[str] = []
    tagged: list[tuple[str, str, str]] = []

    class AsyncImages:
        def pull(self, reference, **_kwargs):
            async def stream():
                if reference != "default.example.test/other/image:1.0":
                    raise RuntimeError("direct pull failed")
                pulled.append(reference)
                yield {"status": "pulled", "id": reference}

            return stream()

        async def tag(self, source, repo, tag):
            tagged.append((source, repo, tag))

    class AsyncClient:
        images = AsyncImages()

    served = await pull_with_fallback_async(
        AsyncClient(),
        "other/image:1.0",
        accelerators=load_image_accelerators(registry=registry),
    )

    assert served == "default.example.test/other/image:1.0"
    assert pulled == [served]
    assert tagged == [(served, "other/image", "1.0")]


def test_pull_plan_orders_direct_ecr_then_accelerators_with_credentials():
    plan = build_pull_plan(
        "websoft9dev/websoft9:2.4.1",
        alias_tags=["2.4"],
        accelerators=[Accelerator("registry.example.test", "ops", "s3cret")],
        use_ecr_public=True,
    )

    assert [attempt.source for attempt in plan][:2] == [
        "direct",
        "public.ecr.aws/w6g2g5k1/websoft9:2.4",
    ]
    assert plan[0].auth_config is None
    assert plan[-1].reference == "registry.example.test/websoft9dev/websoft9:2.4.1"
    assert plan[-1].auth_config == {"username": "ops", "password": "s3cret"}


def test_application_pull_plan_does_not_try_ecr_public_for_docker_hub_images():
    plan = build_pull_plan("wordpress:7.1", accelerators=["mirror.example.test"])

    assert [attempt.reference for attempt in plan] == [
        "wordpress:7.1",
        "mirror.example.test/wordpress:7.1",
        "mirror.example.test/library/wordpress:7.1",
    ]


def test_accelerated_pull_sends_the_configured_credentials():
    client = FakeClient(
        {"mirror.example.test/other/image:1.0": FakeImage("sha256:local")}
    )

    pull_with_fallback(
        client,
        "other/image:1.0",
        accelerators=[Accelerator("mirror.example.test", "ops", "s3cret")],
    )

    assert client.images.auth == [None, {"username": "ops", "password": "s3cret"}]


def test_progress_callback_receives_the_streamed_lines():
    client = FakeClient({})
    client.images.local["other/image:1.0"] = FakeImage("sha256:local")
    lines = []

    pull_with_fallback(
        client, "other/image:1.0", accelerators=[], on_progress=lines.append
    )

    assert lines == [{"status": "pulling", "id": "other/image:1.0"}]


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

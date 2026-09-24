"""Image pulls that follow the same fallback order as the host installer.

A console download and `install.sh` must reach the same registries in the same order:
pull directly first, then Amazon ECR Public for the official product repository, and
finally the accelerator prefixes the operator configured. An accelerated pull is only
another source for the same image, so the result is tagged back to the requested
reference: the deployment keeps using the reference recorded in `.env`, and the upgrade
runner verifies the image through the digest of the source it was pulled from.

Where the accelerators come from is not decided here: `MirrorRegistry` owns that answer,
including the credentials an accelerator may need. This module turns the answer into an
ordered plan (`build_pull_plan`) and runs it on either Docker client.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import json
import re
import tarfile
from typing import Mapping, Sequence

import yaml

from src.core.logger import logger
from src.services.docker_mirror_store import (
    normalize_mirror_url,
    parse_mirror_entries,
)
from src.services.mirror_registry import Accelerator, MirrorRegistry

DEFAULT_IMAGE_REPO = "websoft9dev/websoft9"
ECR_PUBLIC_IMAGE_REPO = "public.ecr.aws/w6g2g5k1/websoft9"
# Amazon ECR Public also mirrors the Docker Hub official images one to one, digest included,
# which gives the runner image a first-party fallback in networks that cannot reach Hub.
ECR_PUBLIC_LIBRARY_REPO = "public.ecr.aws/docker/library"
# Amazon ECR Public keeps only the tags it can share across patch releases: the channel
# aliases (`latest`, `dev`) and the two-part alias (`2.4`, `2.4-dev`). A pinned release tag
# (`2.4.1`) therefore has to go through its alias, which is only safe because the pulled
# image is checked against the version it is supposed to carry.
ECR_PUBLIC_TAG_PATTERN = re.compile(r"^(latest|dev|\d+\.\d+|\d+\.\d+-dev)$")
ECR_PUBLIC_ALIAS_PATTERN = re.compile(r"^(latest|\d+\.\d+)$")
VERSION_FILE_PATH = "/websoft9/version.json"
LOCAL_MIRROR_FILE = "/websoft9/mirrors.json"
# An image reference carries no scheme, and a value that needs quirks (whitespace, a URL)
# is not something any registry can serve - better to reject it than to pull something else.
IMAGE_REFERENCE_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._\-/:@]*$")


class ImagePullError(Exception):
    """Raised when every pull strategy failed."""


@dataclass(frozen=True)
class PulledImage:
    reference: str
    image: object
    digest: str
    source: str


def split_reference(reference: str) -> tuple[str, str]:
    """Split `repo[:tag][@digest]` while keeping a registry port out of the tag."""
    head = str(reference).split("@", 1)[0]
    repository, separator, tag = head.rpartition(":")
    if not separator or "/" in tag:
        return head, ""
    return repository, tag


def load_image_accelerators(
    *, registry: MirrorRegistry | None = None
) -> list[Accelerator]:
    """Accelerators to try, resolved by the registry in one place.

    The operator's table wins when it has entries; the default list is used only when nothing
    was configured, and a list with every entry switched off means no acceleration at all.
    """
    return (registry or MirrorRegistry()).accelerators()


def resolve_accelerators(
    accelerators: "Sequence[str | Accelerator] | None",
) -> list[Accelerator]:
    """Normalise explicit accelerators, or ask the registry when none were given."""
    if accelerators is None:
        return load_image_accelerators()
    resolved: list[Accelerator] = []
    for item in accelerators:
        if isinstance(item, Accelerator):
            resolved.append(item)
        else:
            url = normalize_mirror_url(item)
            if url:
                resolved.append(Accelerator(url))
    return resolved


def validate_image_reference(image: str) -> str:
    """Reject a reference no registry could serve, before it reaches a pull.

    A compose file may interpolate a variable that the `.env` never defines, and the result
    would otherwise be pulled literally.
    """
    candidate = str(image or "").strip()
    if not candidate or not IMAGE_REFERENCE_PATTERN.match(candidate):
        raise ImagePullError(f"Invalid image reference: {image!r}")
    return candidate


def collect_compose_images(compose_payload, env_values: "Mapping[str, str] | None" = None) -> list[str]:
    """List the images a compose file will need, in file order, variables substituted.

    Services that build from source are skipped: the platform has no build context for them.
    """
    if isinstance(compose_payload, str):
        try:
            compose_payload = yaml.safe_load(compose_payload) or {}
        except Exception as exc:
            logger.warning(f"Unable to parse the compose file while collecting images: {exc}")
            return []
    services = (compose_payload or {}).get("services", {}) if isinstance(compose_payload, dict) else {}
    images: list[str] = []
    for service in services.values():
        if not isinstance(service, dict) or "build" in service:
            continue
        image = service.get("image")
        if not image:
            continue
        images.append(_substitute_env(str(image), env_values or {}))
    return list(dict.fromkeys(images))


def _substitute_env(text: str, env_values: "Mapping[str, str]") -> str:
    def _replace(match: "re.Match[str]") -> str:
        return str(env_values.get(match.group(1) or match.group(2), ""))

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", _replace, text)


@dataclass(frozen=True)
class PullAttempt:
    """One candidate for one image: what to pull, why, and with which credentials."""

    reference: str
    label: str
    source: str
    auth_config: dict[str, str] | None = None


def build_pull_plan(
    reference: str,
    *,
    accelerators: "Sequence[str | Accelerator] | None" = None,
    alias_tags: list[str] | None = None,
) -> list[PullAttempt]:
    """Order the candidates: direct, Amazon ECR Public, then the operator's accelerators.

    Both the synchronous and the asynchronous pull share this list, so the order and the
    credentials cannot drift apart between the install path and the redeploy path.
    """
    plan = [PullAttempt(reference=reference, label="direct pull", source="direct")]
    for ecr_reference in ecr_candidates(reference, alias_tags):
        plan.append(
            PullAttempt(
                reference=ecr_reference,
                label=f"Amazon ECR Public ({ecr_reference})",
                source=ecr_reference,
            )
        )
    for accelerator in resolve_accelerators(accelerators):
        for candidate in _accelerated_references(accelerator.url, reference):
            plan.append(
                PullAttempt(
                    reference=candidate,
                    label=f"mirror {accelerator.url}",
                    source=candidate,
                    auth_config=accelerator.auth_config(),
                )
            )
    return plan


def first_digest(image) -> str:
    """Return the first repository digest recorded on a pulled image."""
    attributes = getattr(image, "attrs", None) or {}
    for entry in attributes.get("RepoDigests") or []:
        _repository, separator, digest = str(entry).rpartition("@")
        if separator and digest.startswith("sha256:"):
            return digest
    return ""


def read_image_version(client, reference: str) -> str:
    """Read the release version an image declares, without starting a container.

    Returns an empty string when the image cannot be inspected: that case is inconclusive
    rather than a rejection, so a probe failure never blocks an otherwise valid upgrade.
    """
    container_id = ""
    try:
        created = client.api.create_container(reference, command=["true"])
        container_id = str(created.get("Id") or "")
        if not container_id:
            return ""
        stream, _stat = client.api.get_archive(container_id, VERSION_FILE_PATH)
        with tarfile.open(fileobj=io.BytesIO(b"".join(stream)), mode="r") as archive:
            member = next((item for item in archive.getmembers() if item.name.endswith("version.json")), None)
            if member is None:
                return ""
            handle = archive.extractfile(member)
            payload = json.loads(handle.read().decode("utf-8")) if handle else {}
        return str(payload.get("version") or "").strip() if isinstance(payload, dict) else ""
    except Exception as exc:
        logger.warning(f"Unable to read the release version from {reference}: {exc}")
        return ""
    finally:
        if container_id:
            try:
                client.api.remove_container(container_id, force=True)
            except Exception:
                logger.debug("Unable to remove the temporary version probe container")


def image_digest_values(image) -> list[str]:
    """Return the digest values recorded for a local image, whoever served it."""
    attributes = getattr(image, "attrs", None) or {}
    return [
        str(entry).rsplit("@", 1)[-1]
        for entry in attributes.get("RepoDigests") or []
        if "@sha256:" in str(entry)
    ]


def require_local_image(client, reference: str, digest: str = ""):
    """Resolve an image that must already be present locally, verified against its pin.

    Pulling records the digest under the registry that served the image, so resolving
    `repo:tag@sha256:...` only works for that same registry: a mirror pull would leave the
    canonical reference unresolvable. Resolving through the tag and checking the digest value
    keeps the pin meaningful no matter which source won the fallback.
    """
    repository, tag = split_reference(reference)
    candidates = [f"{repository}:{tag}"] if tag else []
    if reference not in candidates:
        candidates.append(reference)
    image = None
    failure = ""
    for candidate in candidates:
        try:
            image = client.images.get(candidate)
            break
        except Exception as exc:
            failure = str(exc)
    if image is None:
        raise ImagePullError(f"{reference} is not available locally: {failure}")
    if digest and digest not in image_digest_values(image):
        raise ImagePullError(f"{reference} does not carry the pinned digest {digest}")
    return image


def ecr_candidates(reference: str, alias_tags: list[str] | None = None) -> list[str]:
    """Map an image onto its Amazon ECR Public equivalent, when one exists.

    Two families are mirrored there: the product repository (under its own name, and only with
    floating aliases) and the Docker Hub official images (one to one, digest included).
    """
    repository, tag = split_reference(reference)
    if not tag:
        return []
    if repository == DEFAULT_IMAGE_REPO:
        if ECR_PUBLIC_TAG_PATTERN.match(tag):
            return [f"{ECR_PUBLIC_IMAGE_REPO}:{tag}"]
        return [f"{ECR_PUBLIC_IMAGE_REPO}:{alias}" for alias in _alias_tags(tag, alias_tags)]
    if "/" not in repository:
        # Docker Hub official image (`docker`, `alpine`, ...). The mirror follows the digest, so
        # a pinned reference stays pinned through it.
        tail = reference[len(repository) + 1:]
        return [f"{ECR_PUBLIC_LIBRARY_REPO}/{repository}:{tail}"]
    return []


def _alias_tags(tag: str, alias_tags: list[str] | None) -> list[str]:
    """Two-part alias first, then `latest`, both of which ECR keeps up to date."""
    names: list[str] = []
    parts = str(tag).split(".")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        names.append(f"{parts[0]}.{parts[1]}")
    for entry in alias_tags or []:
        name = str(entry).rsplit(":", 1)[-1].strip()
        if name:
            names.append(name)
    names.append("latest")
    return [
        name
        for name in dict.fromkeys(names)
        if ECR_PUBLIC_ALIAS_PATTERN.match(name) and name != tag
    ]


def pull_with_fallback(
    client,
    reference: str,
    *,
    expected_version: str = "",
    alias_tags: list[str] | None = None,
    accelerators: "Sequence[str | Accelerator] | None" = None,
    on_progress=None,
) -> PulledImage:
    """Pull `reference`, trying direct, Amazon ECR Public and the accelerators in order.

    When `expected_version` is given, every candidate has to declare that version inside the
    image; a source that moved on to another patch release is discarded instead of being
    installed under the wrong version. `on_progress` receives the raw progress lines when a
    caller wants to surface them (the install log does).
    """
    errors: list[str] = []
    plan = build_pull_plan(reference, accelerators=accelerators, alias_tags=alias_tags)

    for attempt in plan:
        image = _pull_checked(client, attempt, expected_version, errors, on_progress)
        if image is not None:
            return _pulled(client, reference, image, attempt.source)

    raise ImagePullError("; ".join(errors) or f"Unable to pull {reference}")


async def pull_with_fallback_async(
    client,
    reference: str,
    *,
    alias_tags: list[str] | None = None,
    accelerators: "Sequence[str | Accelerator] | None" = None,
    log=None,
) -> str:
    """The same plan, driven by the asynchronous Docker client.

    The redeploy path streams pull progress into the install log, so it cannot use the
    synchronous client; sharing `build_pull_plan` keeps the order and the credentials
    identical between the two transports. Returns the reference that served the image, which
    is always tagged back to `reference` for the deployment to keep using.
    """
    errors: list[str] = []
    for attempt in build_pull_plan(reference, accelerators=accelerators, alias_tags=alias_tags):
        try:
            if log is not None:
                await log(f"Pulling image: {attempt.reference}")
            stream = client.images.pull(
                attempt.reference, stream=True, auth=attempt.auth_config
            )
            async for line in stream:
                if log is not None:
                    await log(line)
        except Exception as exc:
            errors.append(f"{attempt.label}: {exc}")
            logger.warning(f"Image pull failed ({attempt.label}): {exc}")
            continue
        await _tag_back_async(client, reference, attempt.reference)
        return attempt.reference

    raise ImagePullError("; ".join(errors) or f"Unable to pull {reference}")


async def _tag_back_async(client, reference: str, served: str) -> None:
    """Make the requested name resolve after an accelerated pull."""
    repository, tag = split_reference(reference)
    if not (repository and tag) or served == reference:
        return
    try:
        await client.images.tag(served, repo=repository, tag=tag)
    except Exception as exc:
        logger.debug(f"Unable to tag {served} as {reference}: {exc}")


def _pull_checked(
    client, attempt: PullAttempt, expected_version: str, errors: list[str], on_progress=None
):
    image = _pull(client, attempt, errors, on_progress)
    if image is None or not expected_version:
        return image
    declared = read_image_version(client, attempt.reference)
    if declared and declared != expected_version:
        errors.append(
            f"{attempt.label}: the image declares {declared} instead of {expected_version}"
        )
        logger.warning(
            f"Discarding {attempt.reference}: it carries {declared}, expected {expected_version}"
        )
        try:
            client.images.remove(attempt.reference)
        except Exception:
            logger.debug(f"Unable to drop the rejected image {attempt.reference}")
        return None
    return image


def _pull(client, attempt: PullAttempt, errors: list[str], on_progress=None):
    try:
        if on_progress is None:
            return client.images.pull(
                attempt.reference, auth_config=attempt.auth_config
            )
        for line in client.api.pull(
            attempt.reference,
            stream=True,
            decode=True,
            auth_config=attempt.auth_config,
        ):
            on_progress(line)
        return client.images.get(attempt.reference)
    except Exception as exc:
        errors.append(f"{attempt.label}: {exc}")
        logger.warning(f"Image pull failed ({attempt.label}): {exc}")
        return None


def _pulled(client, reference: str, image, source: str) -> PulledImage:
    repository, tag = split_reference(reference)
    if repository and tag:
        # Make sure the plain tag resolves as well. A digest pull can leave the image untagged,
        # and a mirror pull records its own repository for the digest, so neither form can be
        # assumed: the tag is the one reference both paths share. The source tag is kept so the
        # digest recorded in the task stays verifiable on the local image.
        client.api.tag(image.id, repository=repository, tag=tag)
    return PulledImage(reference=reference, image=image, digest=first_digest(image), source=source)


def _accelerated_references(accelerator: str, reference: str) -> list[str]:
    repository, tag = split_reference(reference)
    if not tag:
        return [f"{accelerator}/{reference}"]
    tail = reference[len(repository) + 1:]
    candidates = [f"{accelerator}/{repository}:{tail}"]
    if "/" not in repository:
        # Docker Hub official images need the library/ prefix on some mirrors.
        candidates.append(f"{accelerator}/library/{repository}:{tail}")
    return candidates

"""Image pulls that follow the same fallback order as the host installer.

A console download and `install.sh` must reach the same registries in the same order:
pull directly first, then Amazon ECR Public for the official product repository, and
finally the accelerator prefixes the operator configured. An accelerated pull is only
another source for the same image, so the result is tagged back to the requested
reference: the deployment keeps using the reference recorded in `.env`, and the upgrade
runner verifies the image through the digest of the source it was pulled from.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import json
import re
import tarfile

import requests

from src.core.config import ConfigManager
from src.core.logger import logger

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
MIRROR_LIST_TIMEOUT_SECONDS = 10


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


def normalize_accelerator(value: str) -> str:
    normalized = str(value or "").strip().rstrip("/")
    for scheme in ("http://", "https://"):
        if normalized.startswith(scheme):
            normalized = normalized[len(scheme):]
    return normalized


def parse_accelerator_entries(configured: str) -> list[str]:
    entries = [
        normalize_accelerator(item)
        for item in str(configured or "").replace("\n", ",").split(",")
    ]
    return list(dict.fromkeys(entry for entry in entries if entry))


def load_local_mirror_entries() -> list[str]:
    """Read the mirror list shipped inside the image."""
    try:
        with open(LOCAL_MIRROR_FILE, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return []
    mirrors = payload.get("mirrors", []) if isinstance(payload, dict) else []
    return [entry for entry in (normalize_accelerator(item) for item in mirrors) if entry]


def load_image_accelerators(*, config: ConfigManager | None = None) -> list[str]:
    """Read the operator's accelerator prefixes.

    `docker_mirror.url` holds either the prefixes themselves (newline or comma separated)
    or a URL that serves the mirror list. A successful fetch is cached back into
    config.ini, and an unreachable URL falls back to the mirrors bundled with the image.
    """
    manager = config or ConfigManager("config.ini")
    try:
        configured = str(manager.get_value("docker_mirror", "url") or "").strip()
    except Exception as exc:
        logger.error(f"Unable to read the docker mirror configuration: {exc}")
        return []
    if not configured:
        return []
    if not configured.startswith(("http://", "https://")):
        return parse_accelerator_entries(configured)

    try:
        response = requests.get(configured, timeout=MIRROR_LIST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        entries = payload.get("mirrors", []) if isinstance(payload, dict) else []
    except Exception:
        return load_local_mirror_entries()

    resolved = [entry for entry in (normalize_accelerator(item) for item in entries) if entry]
    if resolved:
        try:
            manager.set_value("docker_mirror", "url", "\n".join(resolved))
        except Exception:
            logger.debug("Unable to cache the resolved mirror list")
    return resolved


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
    accelerators: list[str] | None = None,
) -> PulledImage:
    """Pull `reference`, trying direct, Amazon ECR Public and the accelerators in order.

    When `expected_version` is given, every candidate has to declare that version inside the
    image; a source that moved on to another patch release is discarded instead of being
    installed under the wrong version.
    """
    errors: list[str] = []

    image = _pull_checked(client, reference, "direct pull", expected_version, errors)
    if image is not None:
        return _pulled(client, reference, image, "direct")

    for ecr_reference in ecr_candidates(reference, alias_tags):
        image = _pull_checked(client, ecr_reference, f"Amazon ECR Public ({ecr_reference})", expected_version, errors)
        if image is not None:
            return _pulled(client, reference, image, ecr_reference)

    # Reading the list touches config.ini and possibly the network, so it stays lazy: a
    # direct pull never pays for it.
    for accelerator in load_image_accelerators() if accelerators is None else accelerators:
        for candidate in _accelerated_references(accelerator, reference):
            image = _pull_checked(client, candidate, f"mirror {accelerator}", expected_version, errors)
            if image is not None:
                return _pulled(client, reference, image, candidate)

    raise ImagePullError("; ".join(errors) or f"Unable to pull {reference}")


def _pull_checked(client, reference: str, label: str, expected_version: str, errors: list[str]):
    image = _pull(client, reference, label, errors)
    if image is None or not expected_version:
        return image
    declared = read_image_version(client, reference)
    if declared and declared != expected_version:
        errors.append(f"{label}: the image declares {declared} instead of {expected_version}")
        logger.warning(f"Discarding {reference}: it carries {declared}, expected {expected_version}")
        try:
            client.images.remove(reference)
        except Exception:
            logger.debug(f"Unable to drop the rejected image {reference}")
        return None
    return image


def _pull(client, reference: str, label: str, errors: list[str]):
    try:
        return client.images.pull(reference)
    except Exception as exc:
        errors.append(f"{label}: {exc}")
        logger.warning(f"Image pull failed ({label}): {exc}")
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

"""The single answer to "which Docker accelerators should this pull try?".

Four places used to answer that question on their own: ``image_pull``, ``app_manager``,
``back_manager`` and ``settings_manager`` each read ``config.ini``, each decided what a blank
value means, and each wrote its answer back. They disagreed about fallbacks, so the answer
depended on which code path ran. Everything now asks this registry: the operator's table when
it has entries, the shipped list when the operator configured nothing, and nothing at all when
every entry is switched off - a disabled list means "do not accelerate", which is a different
statement from "not configured".
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path

import requests

from src.core.logger import logger
from src.services.docker_mirror_store import (
    DockerMirrorStore,
    MirrorEntry,
    normalize_mirror_url,
)
from src.services.sqlite_store import resolve_data_root

BUNDLED_MIRROR_FILE = "/websoft9/mirrors.json"
REGION_MARKER_FILE = "/websoft9/region.json"
DEFAULT_LIST_URL_TEMPLATE = "https://artifact.websoft9.com/websoft9/{channel}/{suffix}mirrors.json"
DEFAULT_LIST_TIMEOUT_SECONDS = 5
DEFAULT_LIST_TTL_SECONDS = 24 * 3600
# A failed refresh is retried at most this often, so a pull never stalls on a dead endpoint
# twice in a row.
REFRESH_ATTEMPT_INTERVAL_SECONDS = 300

_LAST_REFRESH_ATTEMPT: dict[str, float] = {}


@dataclass(frozen=True)
class Accelerator:
    """One prefix to try, with the credentials that belong to it."""

    url: str
    username: str = ""
    password: str = ""

    @property
    def registry_host(self) -> str:
        return self.url.split("/", 1)[0]

    @property
    def has_credentials(self) -> bool:
        return bool(self.username or self.password)

    def auth_config(self) -> dict[str, str] | None:
        if not self.has_credentials:
            return None
        return {"username": self.username, "password": self.password}


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write through a temporary file so a reader never sees a half-written list."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), prefix=".mirrors-", delete=False
    )
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(handle.name, path)
    except Exception:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def _read_mirror_payload(path: Path) -> list[str]:
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return []
    except Exception as exc:
        logger.warning(f"Unable to read the mirror list {path}: {exc}")
        return []
    mirrors = payload.get("mirrors", []) if isinstance(payload, dict) else []
    entries = [normalize_mirror_url(item) for item in mirrors]
    return list(dict.fromkeys(entry for entry in entries if entry))


def read_region() -> str:
    """Return the build's region marker, empty when the image does not declare one."""
    override = (os.getenv("WEBSOFT9_REGION") or "").strip().lower()
    if override:
        return override
    try:
        with open(REGION_MARKER_FILE, encoding="utf-8") as handle:
            payload = json.load(handle)
        return str(payload.get("region") or "").strip().lower() if isinstance(payload, dict) else ""
    except FileNotFoundError:
        return ""
    except Exception as exc:
        logger.debug(f"Unable to read {REGION_MARKER_FILE}: {exc}")
        return ""


class MirrorRegistry:
    """Resolve the accelerator list, cache it, and keep the host-side copy in step."""

    def __init__(
        self,
        store: DockerMirrorStore | None = None,
        data_root: str | Path | None = None,
    ):
        self.store = store or DockerMirrorStore()
        self.data_root = Path(data_root) if data_root else resolve_data_root()
        self._import_lock = threading.Lock()
        self._import_checked = False
        self._refresh_lock = threading.Lock()

    # ── Answers ───────────────────────────────────────────────────────────────

    @property
    def default_list_file(self) -> Path:
        return self.data_root / "config" / "mirrors.json"

    @property
    def host_visible_file(self) -> Path:
        return self.data_root / "config" / "docker-mirror.host.json"

    def accelerators(self, *, refresh: bool = True) -> list[Accelerator]:
        """Accelerators to try, in order: the operator's list, or the default one."""
        self._ensure_legacy_import()
        entries = self.store.list_entries()
        if entries:
            return [
                Accelerator(entry.url, entry.username, entry.password)
                for entry in entries
                if entry.enabled
            ]
        if refresh:
            self.refresh_default_list()
        return [Accelerator(url) for url in self.default_entries()]

    def source(self) -> str:
        """Where the current answer comes from, for the console to display."""
        self._ensure_legacy_import()
        entries = self.store.list_entries()
        if not entries:
            return "default"
        return "operator" if any(entry.enabled for entry in entries) else "disabled"

    def default_entries(self) -> list[str]:
        """The channel list fetched into the data root, or the one shipped in the image."""
        cached = _read_mirror_payload(self.default_list_file)
        if cached:
            return cached
        return _read_mirror_payload(Path(BUNDLED_MIRROR_FILE))

    def credentials_for(self, registry_host: str) -> dict[str, str] | None:
        """Credentials configured for one registry host, and only that host."""
        wanted = normalize_mirror_url(registry_host).split("/", 1)[0]
        for entry in self.store.list_enabled_entries():
            if entry.registry_host == wanted and entry.has_credentials:
                return entry.auth_config()
        return None

    def probe(self, accelerator: Accelerator) -> dict:
        """Check an accelerator without pulling an image layer.

        A 401 is usually not a fault: Docker Hub style registries answer the version endpoint
        with a challenge and hand out a token, and the Docker daemon follows that flow on its
        own. So a plain 401 is reported as "login required" - usable without credentials -
        while configured credentials are only called rejected when the token endpoint refuses
        them too.
        """
        url = f"https://{accelerator.registry_host}/v2/"
        auth = (
            (accelerator.username, accelerator.password)
            if accelerator.has_credentials
            else None
        )
        started = time.monotonic()
        try:
            response = requests.get(url, timeout=DEFAULT_LIST_TIMEOUT_SECONDS, auth=auth)
        except Exception as exc:
            return self._probe_result(
                accelerator, started, reachable=False, reason="unreachable", detail=str(exc)
            )

        if response.status_code < 400:
            return self._probe_result(
                accelerator, started, reachable=True, reason="ok", status=response.status_code
            )

        if response.status_code == 401:
            challenge = str(response.headers.get("Www-Authenticate") or "")
            if auth is not None:
                if challenge.lower().startswith("bearer"):
                    verdict = self._token_accepted(challenge, auth)
                    if verdict is True:
                        return self._probe_result(
                            accelerator,
                            started,
                            reachable=True,
                            reason="ok",
                            status=response.status_code,
                        )
                    if verdict is None:
                        # The registry asked for a token and its token service could not be
                        # asked. That says nothing about the password, so it must not be
                        # reported as a rejection.
                        return self._probe_result(
                            accelerator,
                            started,
                            reachable=True,
                            reason="error",
                            status=response.status_code,
                            detail="The registry token endpoint could not be reached, so the credentials were not verified",
                        )
                return self._probe_result(
                    accelerator,
                    started,
                    reachable=True,
                    reason="credentials-rejected",
                    status=response.status_code,
                    detail="The registry rejected the credentials",
                )
            return self._probe_result(
                accelerator,
                started,
                reachable=True,
                reason="credentials-required",
                status=response.status_code,
                detail="The registry asks for a login token, which Docker negotiates by itself",
            )

        return self._probe_result(
            accelerator,
            started,
            reachable=True,
            reason="error",
            status=response.status_code,
            detail=f"The registry answered HTTP {response.status_code}",
        )

    def _probe_result(
        self,
        accelerator: Accelerator,
        started: float,
        *,
        reachable: bool,
        reason: str,
        status: int | None = None,
        detail: str = "",
    ) -> dict:
        """The probe answer, with the verdict decided here rather than in the console."""
        return {
            "url": accelerator.url,
            "reachable": reachable,
            "authorized": reason == "ok",
            # "Usable" is the question the operator is really asking: a mirror that wants a
            # token still accelerates pulls, so it counts as usable.
            "usable": reason in {"ok", "credentials-required"},
            "reason": reason,
            "status": status,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "detail": detail,
        }

    @staticmethod
    def _token_accepted(challenge: str, auth: tuple[str, str]) -> bool | None:
        """Ask the challenge's token endpoint with the same credentials.

        Returns True when the endpoint handed out a token, False when it refused the
        credentials, and None when it could not be asked at all: an unreachable or broken token
        service says nothing about the password, and calling it a rejection would send the
        operator chasing the wrong problem.
        """
        parameters = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
        realm = parameters.get("realm", "")
        if not realm:
            return None
        query = {key: parameters[key] for key in ("service", "scope") if parameters.get(key)}
        try:
            response = requests.get(
                realm, params=query, auth=auth, timeout=DEFAULT_LIST_TIMEOUT_SECONDS
            )
        except Exception as exc:
            logger.debug(f"Unable to reach the registry token endpoint {realm}: {exc}")
            return None
        if response.status_code >= 500:
            logger.warning(
                f"The registry token endpoint {realm} answered {response.status_code}"
            )
            return None
        if response.status_code >= 400:
            return False
        try:
            payload = response.json()
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("token") or payload.get("access_token"):
            return True
        return None

    # ── Legacy import ─────────────────────────────────────────────────────────

    def _ensure_legacy_import(self) -> None:
        """Move a ``config.ini`` list into the table, once per process.

        Installations configured before the table existed must not lose their accelerators on
        upgrade, and the import is guarded by "the table is empty", so an operator who sets the
        console list keeps it.
        """
        if self._import_checked:
            return
        with self._import_lock:
            if self._import_checked:
                return
            try:
                self.store.import_from_config()
            except Exception as exc:
                logger.warning(f"Unable to import the legacy Docker mirror list: {exc}")
            self._import_checked = True

    # ── Default list refresh ──────────────────────────────────────────────────

    def refresh_default_list(self, *, force: bool = False) -> bool:
        """Fetch the channel's default list when it is missing or older than its TTL."""
        if not force and not self._is_stale():
            return False
        with self._refresh_lock:
            if not force and not self._is_stale():
                return False
            marker = str(self.default_list_file)
            last_attempt = _LAST_REFRESH_ATTEMPT.get(marker, 0.0)
            if not force and time.time() - last_attempt < REFRESH_ATTEMPT_INTERVAL_SECONDS:
                return False
            _LAST_REFRESH_ATTEMPT[marker] = time.time()

            mirrors, origin = self._fetch_default_list()
            if mirrors is None:
                # The previous list, if any, stays in place: a dead endpoint must not empty
                # the accelerator configuration of a working host.
                logger.warning("Unable to refresh the default Docker mirror list")
                return False
            _atomic_write_json(
                self.default_list_file,
                {"source": origin, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mirrors": mirrors},
            )
            logger.info(f"Refreshed the default Docker mirror list from {origin}")
            if not self.store.has_entries():
                self.export_host_visible_list()
            return True

    def _is_stale(self) -> bool:
        path = self.default_list_file
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            return True
        return age > DEFAULT_LIST_TTL_SECONDS

    def _fetch_default_list(self) -> tuple[list[str] | None, str]:
        """Try the region-aware path first, then the long-standing channel path."""
        for url in self.default_list_urls():
            try:
                response = requests.get(
                    url,
                    timeout=DEFAULT_LIST_TIMEOUT_SECONDS,
                    headers={"User-Agent": "Websoft9-Product-Bootstrap/1.0"},
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                logger.debug(f"Default mirror list unavailable at {url}: {exc}")
                continue
            mirrors = payload.get("mirrors", []) if isinstance(payload, dict) else []
            entries = [normalize_mirror_url(item) for item in mirrors]
            entries = list(dict.fromkeys(entry for entry in entries if entry))
            if entries:
                return entries, url
        return None, ""

    def default_list_urls(self) -> list[str]:
        region = read_region()
        try:
            from src.services.product_runtime_state import read_release_channel

            channel = read_release_channel()
        except Exception:
            channel = "release"
        urls: list[str] = []
        if region:
            urls.append(DEFAULT_LIST_URL_TEMPLATE.format(channel=channel, suffix=f"{region}/"))
        urls.append(DEFAULT_LIST_URL_TEMPLATE.format(channel=channel, suffix=""))
        return urls

    # ── Host-side hand-off ────────────────────────────────────────────────────

    def export_host_visible_list(self) -> Path | None:
        """Write the effective prefixes where the host scripts can read them.

        The host pulls the new platform image during an upgrade, when this container is about
        to be replaced and its database is not a usable dependency. The export therefore holds
        addresses only: a host ``docker pull`` cannot present per-registry credentials anyway,
        and writing secrets to a file outside the container would widen their exposure for no
        gain.
        """
        try:
            entries = self.store.list_entries()
            if entries:
                mirrors = [entry.url for entry in entries if entry.enabled]
                source = "operator"
            else:
                mirrors = self.default_entries()
                source = "default"
            _atomic_write_json(
                self.host_visible_file,
                {
                    "source": source,
                    "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "mirrors": mirrors,
                },
            )
            return self.host_visible_file
        except Exception as exc:
            logger.warning(f"Unable to export the host-visible mirror list: {exc}")
            return None

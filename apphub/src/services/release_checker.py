from __future__ import annotations

import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests


ARTIFACT_BASE_URL = "https://artifact.websoft9.com/websoft9"

# The daily cron and the startup refresh keep the cache warm; this only bounds how long a
# cached answer is trusted when those did not run.
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60
# Callers inside an HTTP request must not wait for the full network timeout.
REQUEST_TIMEOUT_SECONDS = 3
# Background callers (startup, cron, manual refresh) can afford the full timeout.
BACKGROUND_TIMEOUT_SECONDS = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _age_seconds(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed).total_seconds()


class ReleaseVersionChecker:
    """Keeps the latest published release version in a small on-disk cache.

    The artifact server is an external dependency, so every entry point funnels through
    ``ensure_latest_version``: a fresh cache is served without any network call and only a
    missing or stale entry triggers a request. Failed attempts are throttled too, so an
    unreachable artifact server cannot turn every console request into a slow timeout.
    """

    def __init__(self, *, data_root: str | None = None, artifact_base_url: str = ARTIFACT_BASE_URL):
        self.data_root = Path(data_root or os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data"))
        self.upgrade_root = self.data_root / "upgrade"
        self.artifact_base_url = artifact_base_url.rstrip("/")

    @property
    def cache_file(self) -> Path:
        return self.upgrade_root / "latest-version.json"

    @property
    def lock_file(self) -> Path:
        return self.upgrade_root / "latest-version.lock"

    def read_cache(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_cache(self, payload: dict[str, Any]) -> None:
        self.upgrade_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.upgrade_root, delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=True, separators=(",", ":"))
            handle.write("\n")
            temporary_path = Path(handle.name)
        os.replace(temporary_path, self.cache_file)

    def fetch_remote_version(self, channel: str, *, timeout: int) -> str:
        response = requests.get(
            f"{self.artifact_base_url}/{channel}/version.json",
            timeout=timeout,
            headers={"Cache-Control": "no-cache"},
        )
        response.raise_for_status()
        return str(json.loads(response.text).get("version", "")).strip()

    @staticmethod
    def _matches_channel(cache: dict[str, Any], channel: str) -> bool:
        return str(cache.get("channel") or "") == channel

    def _cached_version(self, cache: dict[str, Any], channel: str) -> Optional[str]:
        if not self._matches_channel(cache, channel):
            return None
        return str(cache.get("version") or "").strip() or None

    def _is_fresh(self, cache: dict[str, Any], channel: str, max_age_seconds: int) -> bool:
        if self._cached_version(cache, channel) is None:
            return False
        age = _age_seconds(cache.get("checked_at"))
        return age is not None and age <= max_age_seconds

    def _attempt_is_throttled(self, cache: dict[str, Any], channel: str, max_age_seconds: int) -> bool:
        if not self._matches_channel(cache, channel):
            return False
        age = _age_seconds(cache.get("last_attempt_at"))
        return age is not None and age <= max_age_seconds

    def _acquire_refresh_lock(self, *, blocking: bool):
        """Take the refresh lock, or return None when another refresh already owns it."""
        self.upgrade_root.mkdir(parents=True, exist_ok=True)
        handle = open(self.lock_file, "a", encoding="utf-8")
        flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        try:
            fcntl.flock(handle.fileno(), flags)
        except BlockingIOError:
            handle.close()
            return None
        return handle

    def ensure_latest_version(
        self,
        *,
        channel: str,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
        force: bool = False,
        background: bool = True,
    ) -> Optional[str]:
        """Return the latest version for ``channel``, refreshing the cache when needed."""
        cache = self.read_cache()
        if not force and (
            self._is_fresh(cache, channel, max_age_seconds)
            or self._attempt_is_throttled(cache, channel, max_age_seconds)
        ):
            return self._cached_version(cache, channel)

        # A request-path caller must never queue behind a background refresh that may take the
        # full background timeout: it answers from the cache and lets the daily check or a
        # manual refresh catch up. Background callers serialize on the lock as usual.
        lock_handle = self._acquire_refresh_lock(blocking=background)
        if lock_handle is None:
            return self._cached_version(cache, channel)
        try:
            # Another worker may have refreshed the cache while we waited for the lock.
            cache = self.read_cache()
            if not force and (
                self._is_fresh(cache, channel, max_age_seconds)
                or self._attempt_is_throttled(cache, channel, max_age_seconds)
            ):
                return self._cached_version(cache, channel)

            previous_version = self._cached_version(cache, channel)
            timeout = BACKGROUND_TIMEOUT_SECONDS if background else REQUEST_TIMEOUT_SECONDS
            try:
                version = self.fetch_remote_version(channel, timeout=timeout)
                if not version:
                    raise ValueError("the release manifest does not contain a version")
            except Exception as exc:
                # A transient failure must not look like "this platform is up to date":
                # keep the previous answer and only record that an attempt happened.
                self._write_cache({
                    "channel": channel,
                    "version": previous_version or "",
                    "checked_at": cache.get("checked_at") if self._matches_channel(cache, channel) else None,
                    "last_attempt_at": _utc_now(),
                    "last_error": str(exc),
                })
                return previous_version

            checked_at = _utc_now()
            self._write_cache({
                "channel": channel,
                "version": version,
                "checked_at": checked_at,
                "last_attempt_at": checked_at,
                "last_error": None,
            })
            return version
        finally:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            finally:
                lock_handle.close()

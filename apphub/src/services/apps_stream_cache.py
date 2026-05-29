from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder

from src.core.logger import logger


@dataclass(frozen=True)
class AppsStreamSnapshot:
    apps: list[dict[str, Any]]
    digest: str
    event_json: str
    refresh_interval_seconds: float


class AppsStreamCache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[tuple[int | None, str], dict[str, Any]] = {}

    def get_snapshot(
        self,
        endpoint_id: Optional[int],
        locale: str,
        *,
        force_refresh: bool = False,
    ) -> AppsStreamSnapshot:
        cache_key = (endpoint_id, locale)
        now = time.monotonic()

        with self._lock:
            entry = self._entries.get(cache_key)
            should_refresh = force_refresh or entry is None or now >= entry['next_refresh_at']
            if not should_refresh:
                return self._entry_to_snapshot(entry)

            try:
                apps = jsonable_encoder(_build_app_manager().get_apps(endpoint_id, locale))
                digest = self._compute_digest(apps)
                refresh_interval_seconds = self._resolve_refresh_interval_seconds(apps)
                event_json = json.dumps(
                    {
                        'apps': apps,
                        'digest': digest,
                        'refresh_hint_ms': int(refresh_interval_seconds * 1000),
                    },
                    ensure_ascii=False,
                    separators=(',', ':'),
                )
                entry = {
                    'apps': apps,
                    'digest': digest,
                    'event_json': event_json,
                    'refresh_interval_seconds': refresh_interval_seconds,
                    'next_refresh_at': now + refresh_interval_seconds,
                }
                self._entries[cache_key] = entry
                return self._entry_to_snapshot(entry)
            except Exception as exc:
                if entry is not None:
                    entry['next_refresh_at'] = now + min(float(entry['refresh_interval_seconds']), 5.0)
                    logger.warning(f'Apps stream refresh failed, serving stale snapshot: {exc}')
                    return self._entry_to_snapshot(entry)
                raise

    @staticmethod
    def _entry_to_snapshot(entry: dict[str, Any]) -> AppsStreamSnapshot:
        return AppsStreamSnapshot(
            apps=entry['apps'],
            digest=str(entry['digest']),
            event_json=str(entry['event_json']),
            refresh_interval_seconds=float(entry['refresh_interval_seconds']),
        )

    @staticmethod
    def _compute_digest(apps: list[dict[str, Any]]) -> str:
        payload = json.dumps(apps, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    @staticmethod
    def _resolve_refresh_interval_seconds(apps: list[dict[str, Any]]) -> float:
        has_installing_app = any(isinstance(app, dict) and app.get('status') == 3 for app in apps)
        return 3.0 if has_installing_app else 15.0


def _build_app_manager():
    from src.services.app_manager import AppManger

    return AppManger()


apps_stream_cache = AppsStreamCache()
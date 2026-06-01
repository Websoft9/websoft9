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
class OverviewStreamSnapshot:
    overview: dict[str, Any]
    digest: str
    event_json: str
    refresh_interval_seconds: float


class OverviewStreamCache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[Optional[str], dict[str, Any]] = {}
        self._overview_service = _build_overview_service()

    def get_snapshot(
        self,
        session_token: Optional[str],
        *,
        force_refresh: bool = False,
    ) -> OverviewStreamSnapshot:
        cache_key = session_token or '__anonymous__'
        now = time.monotonic()

        with self._lock:
            entry = self._entries.get(cache_key)
            should_refresh = force_refresh or entry is None or now >= entry['next_refresh_at']
            if not should_refresh:
                return self._entry_to_snapshot(entry)

            if entry is not None and not force_refresh:
                if not entry.get('refreshing', False):
                    entry['refreshing'] = True
                    thread = threading.Thread(
                        target=self._refresh_entry_in_background,
                        args=(cache_key, session_token),
                        daemon=True,
                    )
                    thread.start()
                return self._entry_to_snapshot(entry)

        try:
            refreshed_entry = self._build_entry(session_token=session_token, now=now)
        except Exception as exc:
            with self._lock:
                entry = self._entries.get(cache_key)
                if entry is not None:
                    entry['next_refresh_at'] = now + min(float(entry['refresh_interval_seconds']), 5.0)
                    entry['refreshing'] = False
                    logger.warning(f'Overview stream refresh failed, serving stale snapshot: {exc}')
                    return self._entry_to_snapshot(entry)
            raise

        with self._lock:
            refreshed_entry['refreshing'] = False
            self._entries[cache_key] = refreshed_entry
            return self._entry_to_snapshot(refreshed_entry)

    def get_overview(self, session_token: Optional[str], *, force_refresh: bool = False) -> dict[str, Any]:
        return self.get_snapshot(session_token, force_refresh=force_refresh).overview

    def _refresh_entry_in_background(self, cache_key: Optional[str], session_token: Optional[str]) -> None:
        now = time.monotonic()
        try:
            refreshed_entry = self._build_entry(session_token=session_token, now=now)
        except Exception as exc:
            with self._lock:
                entry = self._entries.get(cache_key)
                if entry is not None:
                    entry['refreshing'] = False
                    entry['next_refresh_at'] = now + min(float(entry['refresh_interval_seconds']), 5.0)
            logger.warning(f'Overview stream background refresh failed: {exc}')
            return

        with self._lock:
            refreshed_entry['refreshing'] = False
            self._entries[cache_key] = refreshed_entry

    def _build_entry(self, session_token: Optional[str], *, now: float) -> dict[str, Any]:
        overview = jsonable_encoder(self._overview_service.get_overview(session_token=session_token))
        digest = self._compute_digest(overview)
        refresh_interval_seconds = self._resolve_refresh_interval_seconds(overview)
        event_json = json.dumps(
            {
                'overview': overview,
                'digest': digest,
                'refresh_hint_ms': int(refresh_interval_seconds * 1000),
            },
            ensure_ascii=False,
            separators=(',', ':'),
        )
        return {
            'overview': overview,
            'digest': digest,
            'event_json': event_json,
            'refresh_interval_seconds': refresh_interval_seconds,
            'next_refresh_at': now + refresh_interval_seconds,
            'refreshing': False,
        }

    @staticmethod
    def _entry_to_snapshot(entry: dict[str, Any]) -> OverviewStreamSnapshot:
        return OverviewStreamSnapshot(
            overview=entry['overview'],
            digest=str(entry['digest']),
            event_json=str(entry['event_json']),
            refresh_interval_seconds=float(entry['refresh_interval_seconds']),
        )

    @staticmethod
    def _compute_digest(overview: dict[str, Any]) -> str:
        payload = json.dumps(overview, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    @staticmethod
    def _resolve_refresh_interval_seconds(overview: dict[str, Any]) -> float:
        apps = overview.get('apps') if isinstance(overview, dict) else None
        tasks = overview.get('tasks') if isinstance(overview, dict) else None
        installing_count = apps.get('installing_count', 0) if isinstance(apps, dict) else 0
        task_items = tasks.get('items', []) if isinstance(tasks, dict) else []
        has_running_task = any(isinstance(item, dict) and item.get('status') == 'running' for item in task_items)
        return 3.0 if installing_count or has_running_task else 10.0


def _build_overview_service():
    from src.services.overview_service import OverviewService

    return OverviewService()


overview_stream_cache = OverviewStreamCache()
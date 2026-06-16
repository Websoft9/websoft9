from __future__ import annotations

import configparser
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from src.core.product_catalog import resolve_product_edition_definition
from src.services.app_status import InstallStateStore, _utc_now


VERSION_FILE = Path(__file__).resolve().parents[3] / "version.json"
DEFAULT_PRODUCT_EDITION_KEY = "free"
PRODUCT_RUNTIME_SOURCE_INSTALL = "install"
PRODUCT_RUNTIME_SOURCE_LEGACY = "legacy-migration"
PRODUCT_RUNTIME_SOURCE_MANUAL = "manual-support"
SUPPORTED_RELEASE_CHANNELS = ("release", "rc", "dev")


@dataclass(frozen=True)
class ProductRuntimeState:
    version: Optional[str]
    edition_key: str
    edition_name: str
    edition_names: dict[str, str]
    max_apps: Optional[int]
    state_source: str
    updated_by: str
    updated_at: Optional[str]
    note: Optional[str]

    @property
    def key(self) -> str:
        return self.edition_key

    @property
    def name(self) -> str:
        return self.edition_name

    @property
    def names(self) -> dict[str, str]:
        return self.edition_names


def _normalize_max_apps(value) -> Optional[int]:
    if value in (None, "", "null"):
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = int(stripped)
        except ValueError:
            return None
        return parsed if parsed > 0 else None

    return None


def read_release_version_file(file_path: Path | None = None) -> dict[str, Any]:
    target = file_path or VERSION_FILE
    if not target.exists():
        return {}

    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_release_version() -> Optional[str]:
    payload = read_release_version_file()
    version = str(payload.get("version") or "").strip()
    return version or None


def infer_release_channel_from_version(version: Optional[str]) -> str:
    normalized_version = str(version or "").strip().lower()
    if "rc" in normalized_version:
        return "rc"
    if "dev" in normalized_version:
        return "dev"
    return "release"


def normalize_release_channel(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    if normalized in SUPPORTED_RELEASE_CHANNELS:
        return normalized
    return None


def read_release_channel(file_path: Path | None = None) -> str:
    payload = read_release_version_file(file_path)
    channel = normalize_release_channel(payload.get("channel"))
    if channel:
        return channel
    return infer_release_channel_from_version(payload.get("version"))


def supported_product_edition_keys() -> tuple[str, ...]:
    return ("free", "starter", "standard", "enterprise")


def normalize_product_edition_key(value: Optional[str]) -> str:
    return resolve_product_edition_definition(value).key


def infer_product_edition_key_from_max_apps(max_apps: Optional[int]) -> Optional[str]:
    if max_apps == 2:
        return "free"
    if max_apps == 3:
        return "starter"
    if max_apps == 10:
        return "standard"
    if max_apps is None:
        return "enterprise"
    if isinstance(max_apps, int) and max_apps >= 10000:
        return "enterprise"
    return None


def read_legacy_system_ini_max_apps(file_path: str) -> Optional[int]:
    if not os.path.exists(file_path):
        return None

    config = configparser.ConfigParser()
    try:
        config.read(file_path, encoding="utf-8")
    except OSError:
        return None

    if not config.has_option("max_apps", "key"):
        return None

    return _normalize_max_apps(config.get("max_apps", "key", fallback=None))


class ProductRuntimeStateStore(InstallStateStore):
    _state_lock = threading.RLock()

    def _ensure_storage(self) -> None:
        super()._ensure_storage()
        with self._db_connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS product_runtime_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    edition_key TEXT NOT NULL,
                    max_apps INTEGER,
                    state_source TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    note TEXT
                );
                """
            )
            connection.commit()

    def get_runtime_state_row(self) -> dict[str, Any] | None:
        with self._state_lock, self._db_connect() as connection:
            row = connection.execute(
                "SELECT id, edition_key, max_apps, state_source, updated_by, updated_at, note FROM product_runtime_state WHERE id = 1"
            ).fetchone()
        return dict(row) if row is not None else None

    def write_runtime_state(
        self,
        *,
        edition_key: str,
        max_apps: Optional[int],
        state_source: str,
        updated_by: str,
        note: Optional[str] = None,
    ) -> None:
        canonical_key = resolve_product_edition_definition(edition_key).key
        normalized_max_apps = _normalize_max_apps(max_apps)
        with self._state_lock, self._db_connect() as connection:
            connection.execute(
                """
                INSERT INTO product_runtime_state (id, edition_key, max_apps, state_source, updated_by, updated_at, note)
                VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    edition_key = excluded.edition_key,
                    max_apps = excluded.max_apps,
                    state_source = excluded.state_source,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at,
                    note = excluded.note
                """,
                (canonical_key, normalized_max_apps, state_source, updated_by, _utc_now(), note),
            )
            connection.commit()


def read_product_runtime_state() -> ProductRuntimeState:
    store = ProductRuntimeStateStore()
    row = store.get_runtime_state_row()
    release_version = read_release_version()

    if row is None:
        edition = resolve_product_edition_definition(DEFAULT_PRODUCT_EDITION_KEY)
        return ProductRuntimeState(
            version=release_version,
            edition_key=edition.key,
            edition_name=edition.names.get("en") or edition.key,
            edition_names=dict(edition.names),
            max_apps=edition.max_apps,
            state_source=PRODUCT_RUNTIME_SOURCE_INSTALL,
            updated_by="system",
            updated_at=None,
            note=None,
        )

    edition = resolve_product_edition_definition(str(row.get("edition_key") or DEFAULT_PRODUCT_EDITION_KEY))
    max_apps = _normalize_max_apps(row.get("max_apps"))
    effective_max_apps = max_apps if max_apps is not None else edition.max_apps
    return ProductRuntimeState(
        version=release_version,
        edition_key=edition.key,
        edition_name=edition.names.get("en") or edition.key,
        edition_names=dict(edition.names),
        max_apps=effective_max_apps,
        state_source=str(row.get("state_source") or PRODUCT_RUNTIME_SOURCE_INSTALL),
        updated_by=str(row.get("updated_by") or "system"),
        updated_at=row.get("updated_at"),
        note=row.get("note"),
    )


def initialize_product_runtime_state() -> ProductRuntimeState:
    store = ProductRuntimeStateStore()
    row = store.get_runtime_state_row()
    if row is None:
        edition = resolve_product_edition_definition(DEFAULT_PRODUCT_EDITION_KEY)
        store.write_runtime_state(
            edition_key=edition.key,
            max_apps=edition.max_apps,
            state_source=PRODUCT_RUNTIME_SOURCE_INSTALL,
            updated_by="system",
            note="default install initialization",
        )
    return read_product_runtime_state()


def migrate_product_runtime_state(
    *,
    version: Optional[str] = None,
    source_state: Optional[dict[str, Any]] = None,
    legacy_system_ini_file: Optional[str] = None,
    fallback_edition_key: str = DEFAULT_PRODUCT_EDITION_KEY,
    updated_by: str = "system",
    note: Optional[str] = None,
) -> ProductRuntimeState:
    store = ProductRuntimeStateStore()
    existing_row = store.get_runtime_state_row()

    if source_state:
        source_edition_key = source_state.get("edition_key")
        if isinstance(source_edition_key, str) and source_edition_key.strip():
            edition = resolve_product_edition_definition(source_edition_key)
            store.write_runtime_state(
                edition_key=edition.key,
                max_apps=source_state.get("max_apps", edition.max_apps),
                state_source=str(source_state.get("state_source") or PRODUCT_RUNTIME_SOURCE_MANUAL),
                updated_by=str(source_state.get("updated_by") or updated_by),
                note=source_state.get("note") or note,
            )
            return read_product_runtime_state()

    if existing_row is not None and legacy_system_ini_file is None:
        return read_product_runtime_state()

    if legacy_system_ini_file:
        legacy_max_apps = read_legacy_system_ini_max_apps(legacy_system_ini_file)
        inferred_edition_key = infer_product_edition_key_from_max_apps(legacy_max_apps)
        if inferred_edition_key is None:
            raise ValueError(f"Unsupported legacy max_apps value in {legacy_system_ini_file}")
        store.write_runtime_state(
            edition_key=inferred_edition_key,
            max_apps=legacy_max_apps,
            state_source=PRODUCT_RUNTIME_SOURCE_LEGACY,
            updated_by=updated_by,
            note=note,
        )
        return read_product_runtime_state()

    edition = resolve_product_edition_definition(fallback_edition_key)
    store.write_runtime_state(
        edition_key=edition.key,
        max_apps=edition.max_apps,
        state_source=PRODUCT_RUNTIME_SOURCE_INSTALL,
        updated_by=updated_by,
        note=note,
    )
    return read_product_runtime_state()


def set_product_runtime_edition(
    edition_key: str,
    *,
    updated_by: str = "support",
    state_source: str = PRODUCT_RUNTIME_SOURCE_MANUAL,
    note: Optional[str] = None,
) -> ProductRuntimeState:
    edition = resolve_product_edition_definition(edition_key)
    store = ProductRuntimeStateStore()
    store.write_runtime_state(
        edition_key=edition.key,
        max_apps=edition.max_apps,
        state_source=state_source,
        updated_by=updated_by,
        note=note,
    )
    return read_product_runtime_state()
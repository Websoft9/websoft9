"""The operator's Docker registry accelerators, credentials included.

These prefixes used to live in ``config.ini [docker_mirror] url``, where the single value had
two meanings: either the prefixes themselves, or a URL that serves a list. Readers cached the
remote answer back into the same key, so the effective configuration depended on who read it
last and a failed fetch could leave the file pointing at something nobody chose. The list now
lives in one ordered table, so "what did the operator configure?" has a single answer, and an
accelerator that needs credentials can carry them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import threading
from typing import Any, Iterable, Mapping

from src.core.logger import logger
from src.services.sqlite_store import SqliteStore, resolve_data_root

SCHEMA_VERSION = 2

# "The legacy config.ini list was already considered" is a different fact from "the table is
# empty": an operator who clears every row must not have the old value reappear on the next
# request, so the marker is persisted rather than held in memory.
LEGACY_IMPORT_META_KEY = "legacy_config_imported"

SCHEMA = """
CREATE TABLE IF NOT EXISTS docker_mirror_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position INTEGER NOT NULL,
    url TEXT NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    password TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_docker_mirror_entries_url ON docker_mirror_entries(url);
CREATE INDEX IF NOT EXISTS idx_docker_mirror_entries_position ON docker_mirror_entries(position);

CREATE TABLE IF NOT EXISTS platform_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
"""

MIGRATIONS = {
    2: """
CREATE TABLE IF NOT EXISTS platform_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
""",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_mirror_url(value: str) -> str:
    """Return the bare accelerator prefix: no scheme, no trailing slash.

    Docker has no scheme in an image reference, so ``https://docker.1ms.run/`` and
    ``docker.1ms.run`` have to end up as the same value or the same mirror would be stored
    twice and tried twice.
    """
    normalized = str(value or "").strip().rstrip("/")
    for scheme in ("http://", "https://"):
        if normalized.lower().startswith(scheme):
            normalized = normalized[len(scheme):]
    return normalized.strip().rstrip("/")


def parse_mirror_entries(raw: str) -> list[str]:
    """Split a newline/comma separated list into unique accelerator prefixes."""
    entries = [
        normalize_mirror_url(item)
        for item in str(raw or "").replace("\n", ",").split(",")
    ]
    return list(dict.fromkeys(entry for entry in entries if entry))


# An accelerator is a registry host with an optional port and an optional path prefix, which
# is exactly what Docker accepts in an image reference before the repository name. A single
# label (``mirror``) is deliberately rejected: Docker reads that as a repository path, so the
# rewritten reference would address the wrong registry.
MIRROR_URL_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    r"(?::\d{1,5})?(?:/[A-Za-z0-9._~\-/]*)?$",
    re.IGNORECASE,
)


def is_valid_mirror_url(value: str) -> bool:
    """Whether a prefix can be prepended to an image reference."""
    return bool(MIRROR_URL_PATTERN.match(str(value or "")))


def validate_mirror_url(value: str) -> str:
    """Return the prefix, or raise ``ValueError`` explaining why it cannot be used.

    A prefix reaches Docker concatenated with a repository name, so a value that is not a
    registry host fails at pull time with a message about an invalid reference - long after the
    operator saved it. It is rejected here instead, where the console can still show why.
    """
    normalized = normalize_mirror_url(value)
    lowered = str(value or "").strip().lower()
    if lowered.startswith("http://"):
        # Docker cannot speak plain HTTP to a registry unless the host daemon is told to, so
        # this is refused instead of being silently rewritten into an HTTPS address.
        raise ValueError(
            "Accelerators are reached over HTTPS only: enter the address without a scheme, "
            "for example docker.1ms.run"
        )
    if "://" in lowered and not lowered.startswith("https://"):
        raise ValueError(
            "Only HTTPS accelerators are supported: enter the address without a scheme"
        )
    if not normalized:
        raise ValueError("An accelerator address is required")
    if not is_valid_mirror_url(normalized):
        raise ValueError(
            f"'{normalized}' is not a usable accelerator address: expected a registry host "
            "such as docker.1ms.run"
        )
    return normalized


def is_mirror_list_url(value: str) -> bool:
    """Whether the legacy value points at a list to fetch instead of listing prefixes."""
    return str(value or "").strip().lower().startswith(("http://", "https://"))


@dataclass(frozen=True)
class MirrorEntry:
    """One accelerator, used in the order `position` dictates."""

    url: str
    position: int = 0
    id: int | None = None
    username: str = ""
    password: str = ""
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""

    @property
    def registry_host(self) -> str:
        """The registry this entry addresses: credentials belong to this host alone."""
        return self.url.split("/", 1)[0]

    @property
    def has_credentials(self) -> bool:
        return bool(self.username or self.password)

    def auth_config(self) -> dict[str, str] | None:
        """Credentials in the shape the Docker SDK expects, when this entry needs them."""
        if not self.has_credentials:
            return None
        return {"username": self.username, "password": self.password}

    def masked(self) -> dict[str, Any]:
        """The entry as the console may see it: never the stored password."""
        return {
            "id": self.id,
            "position": self.position,
            "url": self.url,
            "username": self.username,
            "password_set": bool(self.password),
            "enabled": self.enabled,
            "updated_at": self.updated_at,
        }


def _normalize_incoming(
    raw: "Mapping[str, Any] | MirrorEntry",
) -> tuple[str, str, str | None, bool | None, int | None]:
    """Unpack one incoming entry, keeping "absent password" distinct from "empty password".

    The id travels with the entry because it, not the address, identifies the row an edit
    applies to: an operator who renames a host keeps the credentials they already saved.
    """
    if isinstance(raw, MirrorEntry):
        return raw.url, raw.username, raw.password or None, raw.enabled, raw.id
    data = dict(raw)
    raw_id = data.get("id", None)
    try:
        entry_id = int(raw_id) if raw_id is not None else None
    except (TypeError, ValueError):
        entry_id = None
    return (
        str(data.get("url") or ""),
        str(data.get("username") or ""),
        data.get("password", None),
        data.get("enabled", None),
        entry_id,
    )


def _row_to_entry(row) -> MirrorEntry:
    return MirrorEntry(
        id=int(row["id"]),
        position=int(row["position"]),
        url=str(row["url"]),
        username=str(row["username"] or ""),
        password=str(row["password"] or ""),
        enabled=bool(row["enabled"]),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
    )


class DockerMirrorStore(SqliteStore):
    """Ordered accelerator entries, plus the one-way import of the legacy config.ini list."""

    def __init__(self, database_file: str | Path | None = None):
        if database_file is None:
            override = (os.getenv("WEBSOFT9_PLATFORM_DB_PATH") or "").strip()
            database_file = (
                Path(override)
                if override
                else resolve_data_root() / "config" / "platform" / "platform.sqlite"
            )
        super().__init__(
            database_file,
            schema_version=SCHEMA_VERSION,
            schema=SCHEMA,
            migrations=MIGRATIONS,
        )
        self._cache_lock = threading.RLock()
        self._cache: list[MirrorEntry] | None = None

    # ── Reads ─────────────────────────────────────────────────────────────────

    def list_entries(self) -> list[MirrorEntry]:
        """Every configured entry, enabled or not, in the order they must be tried."""
        self.initialize()
        with self._cache_lock:
            if self._cache is not None:
                return list(self._cache)
        rows = self.query_all(
            "SELECT * FROM docker_mirror_entries ORDER BY position ASC, id ASC"
        )
        entries = [_row_to_entry(row) for row in rows]
        with self._cache_lock:
            self._cache = entries
        return list(entries)

    def list_enabled_entries(self) -> list[MirrorEntry]:
        return [entry for entry in self.list_entries() if entry.enabled]

    def has_entries(self) -> bool:
        return bool(self.list_entries())

    def invalidate_cache(self) -> None:
        with self._cache_lock:
            self._cache = None

    # ── Writes ────────────────────────────────────────────────────────────────

    def replace_entries(
        self, entries: Iterable[Mapping[str, Any] | MirrorEntry]
    ) -> list[MirrorEntry]:
        """Replace the whole list in one transaction, keeping the given order.

        A `password` of ``None`` means "leave the stored one alone", which is what the console
        sends when the operator edits an address without retyping the password; an empty
        string clears it. The entry is found by id first, so a renamed address keeps its
        credentials.
        """
        self.initialize()
        stored = self.list_entries()
        by_id = {entry.id: entry for entry in stored if entry.id is not None}
        by_url = {entry.url: entry for entry in stored}

        prepared: list[MirrorEntry] = []
        seen: set[str] = set()
        for index, raw in enumerate(entries):
            raw_url, username, password, enabled, entry_id = _normalize_incoming(raw)
            url = normalize_mirror_url(raw_url)
            if not url:
                continue
            # Validated before the scheme is stripped, otherwise an ``http://`` address would
            # quietly become an HTTPS one the operator never asked for.
            validate_mirror_url(raw_url)
            if url in seen:
                logger.warning(f"Ignoring duplicate Docker accelerator entry: {url}")
                continue
            seen.add(url)
            previous = by_id.get(entry_id) if entry_id is not None else None
            if previous is None:
                previous = by_url.get(url)
            if password is None and previous is not None:
                # The console omits the password when the operator only edited the address.
                password = previous.password
            if str(username or "").strip() and not str(password or ""):
                raise ValueError("A password is required when an accelerator user name is set")
            prepared.append(
                MirrorEntry(
                    url=url,
                    position=index,
                    username=str(username or ""),
                    password=str(password or ""),
                    enabled=True if enabled is None else bool(enabled),
                )
            )

        now = utc_now()
        with self.transaction() as connection:
            connection.execute("DELETE FROM docker_mirror_entries")
            connection.executemany(
                """
                INSERT INTO docker_mirror_entries
                    (position, url, username, password, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry.position,
                        entry.url,
                        entry.username,
                        entry.password,
                        1 if entry.enabled else 0,
                        now,
                        now,
                    )
                    for entry in prepared
                ],
            )

        self.invalidate_cache()
        return self.list_entries()

    # ── Migration ─────────────────────────────────────────────────────────────

    def import_from_config(self, config_manager: Any = None) -> int:
        """Import the legacy ``[docker_mirror] url`` list once per installation.

        The legacy value is only a starting point: it is read when this table has never been
        considered before, and the marker is written whether or not anything was imported. An
        operator who later clears the list therefore keeps an empty list - "use the shipped
        list" - instead of watching the old value come back. A value that points at a list URL
        is not a choice of accelerators, so it is left to the default-list refresh. The
        original value stays in ``config.ini``: it costs nothing to keep and it is the only
        way back if the database has to be dropped.
        """
        if self._read_meta(LEGACY_IMPORT_META_KEY):
            return 0

        raw = self._read_legacy_value(config_manager)
        if not raw or is_mirror_list_url(raw):
            self._write_meta(LEGACY_IMPORT_META_KEY, utc_now())
            return 0

        urls = [url for url in parse_mirror_entries(raw) if is_valid_mirror_url(url)]
        if not urls or self.has_entries():
            # A list configured in the console wins over a stale file: importing here would
            # silently replace the operator's own order and credentials.
            self._write_meta(LEGACY_IMPORT_META_KEY, utc_now())
            return 0

        imported = self.replace_entries([MirrorEntry(url=url) for url in urls])
        self._write_meta(LEGACY_IMPORT_META_KEY, utc_now())
        logger.info(
            f"Imported {len(imported)} Docker accelerator(s) from config.ini"
        )
        return len(imported)

    # ── Meta bookkeeping ──────────────────────────────────────────────────────

    def lookup_password(self, entry_id: int | None, url: str) -> str:
        """The stored password for one entry, found by id and then by address."""
        self.initialize()
        entries = self.list_entries()
        if entry_id is not None:
            for entry in entries:
                if entry.id == entry_id and entry.password:
                    return entry.password
        wanted = normalize_mirror_url(url)
        for entry in entries:
            if entry.url == wanted and entry.password:
                return entry.password
        return ""

    def _read_meta(self, key: str) -> str:
        self.initialize()
        row = self.query_one(
            "SELECT value FROM platform_meta WHERE key = ?", (key,)
        )
        return str(row["value"]) if row is not None else ""

    def _write_meta(self, key: str, value: str) -> None:
        self.initialize()
        with self.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO platform_meta (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, utc_now()),
            )

    @staticmethod
    def _read_legacy_value(config_manager: Any = None) -> str:
        manager = config_manager
        if manager is None:
            try:
                from src.core.config import ConfigManager

                manager = ConfigManager("config.ini")
            except Exception as exc:
                logger.debug(f"Unable to open config.ini for mirror import: {exc}")
                return ""
        try:
            return str(manager.get_value("docker_mirror", "url") or "").strip()
        except Exception:
            # The section is simply absent on a fresh install.
            return ""

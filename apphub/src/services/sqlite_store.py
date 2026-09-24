"""Shared SQLite plumbing for services that own a private database file.

Creating a connection is cheap, but the settings around it are not the same everywhere in
this codebase: only install-tracking sets a busy timeout and WAL, which is enough for a
single-process writer and not for a file that the API process, the CLI and a background
thread all write. A store that skips WAL keeps the default 5 second timeout, so two writers
collide in ``database is locked`` instead of waiting.

This base class fixes the connection contract in one place and gives every caller the same
transaction helper, so a failed write cannot leave a half-applied change behind and a
connection cannot leak. Existing stores keep their own copy of this logic: they already
work, and rewriting four working stores is a larger risk than the inconsistency is worth.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from src.core.logger import logger

# A writer may have to wait for another process to finish its transaction. 30 seconds is
# what install-tracking already uses and is long enough for a settings write to queue
# behind a scheduling sweep.
DEFAULT_BUSY_TIMEOUT_SECONDS = 30.0

DATABASE_FILE_MODE = 0o600


def resolve_data_root() -> Path:
    """Return the persistent data root, honouring the container environment."""
    return Path(os.getenv("WEBSOFT9_DATA_ROOT", "/opt/websoft9/data"))


class SqliteStore:
    """Boilerplate for a service built on exactly one SQLite file.

    Subclasses declare the schema they need and the migrations that bring an older file up
    to date; everything else (connect, initialise once, transact) is handled here.
    """

    def __init__(
        self,
        database_file: str | Path,
        *,
        schema_version: int = 1,
        schema: str = "",
        migrations: dict[int, str] | None = None,
    ):
        self.database_file = Path(database_file)
        self.schema_version = int(schema_version)
        self._schema = schema
        self._migrations = dict(migrations or {})
        self._initialize_lock = threading.Lock()
        self._initialized = False

    # ── Connections ───────────────────────────────────────────────────────────

    def connect(self) -> sqlite3.Connection:
        """Open a connection that waits for other writers instead of failing."""
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.database_file, timeout=DEFAULT_BUSY_TIMEOUT_SECONDS
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Read-only connection: closed on the way out, nothing is committed."""
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Write connection: committed on success, rolled back on any exception."""
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # ── Schema ────────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Create the schema and apply pending migrations, once per process.

        Callers may invoke this before every operation: the work happens only on the first
        call, so a read path does not pay for ``PRAGMA table_info`` and ``executescript``
        on every request.
        """
        if self._initialized:
            return
        with self._initialize_lock:
            if self._initialized:
                return
            fresh = not self.database_file.exists() or self.database_file.stat().st_size == 0
            with self.transaction() as connection:
                if self._schema:
                    connection.executescript(self._schema)
                if fresh:
                    # A new file already matches the current schema; recorded migrations are
                    # for files created by an older build.
                    connection.execute(f"PRAGMA user_version = {self.schema_version}")
                else:
                    self._apply_migrations(connection)
            self._restrict_permissions()
            self._initialized = True

    def _apply_migrations(self, connection: sqlite3.Connection) -> None:
        current = int(connection.execute("PRAGMA user_version").fetchone()[0])
        for version in sorted(self._migrations):
            if version <= current:
                continue
            logger.info(f"Applying {type(self).__name__} schema migration {version}")
            connection.executescript(self._migrations[version])
            connection.execute(f"PRAGMA user_version = {version}")

    def _restrict_permissions(self) -> None:
        """Keep the file readable only by the owner: it holds operator secrets."""
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{self.database_file}{suffix}")
            if not path.exists():
                continue
            try:
                os.chmod(path, DATABASE_FILE_MODE)
            except OSError:
                logger.debug(f"Unable to restrict permissions on {path}")

    # ── Query helpers ─────────────────────────────────────────────────────────

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> int:
        with self.transaction() as connection:
            return connection.execute(sql, parameters).rowcount

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        with self.transaction() as connection:
            connection.executemany(sql, list(rows))

    def query_all(self, sql: str, parameters: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self.connection() as connection:
            return list(connection.execute(sql, parameters).fetchall())

    def query_one(self, sql: str, parameters: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self.connection() as connection:
            return connection.execute(sql, parameters).fetchone()

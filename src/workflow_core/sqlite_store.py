"""Shared sqlite lifecycle for the harness's small stores.

MetricsStore and NfrStore are both tiny file-backed sqlite stores; this base
owns the one thing they genuinely share -- connection lifecycle (parent-dir
creation, schema bootstrap, close, context-manager protocol) -- so each store
keeps only its own schema and queries.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Self

_MEMORY_PATH = ":memory:"


class SqliteStore:
    """Connection lifecycle base; subclasses provide schema and queries."""

    def __init__(
        self,
        path: Path | str,
        *,
        schema: str,
        schema_version: int = 0,
        migrations: Mapping[int, str] | None = None,
    ) -> None:
        if str(path) != _MEMORY_PATH:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._bootstrap_schema(schema, schema_version, migrations or {})

    def _bootstrap_schema(
        self,
        schema: str,
        schema_version: int,
        migrations: Mapping[int, str],
    ) -> None:
        if schema_version < 0:
            raise ValueError("schema_version must be non-negative")
        current = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if current > schema_version:
            self._conn.close()
            raise sqlite3.DatabaseError(
                f"database schema version {current} is newer than supported {schema_version}"
            )
        self._conn.executescript(schema)
        if schema_version:
            for version in range(current + 1, schema_version + 1):
                migration = migrations.get(version)
                if migration:
                    self._conn.executescript(migration)
                elif version != 1:
                    self._conn.close()
                    raise sqlite3.DatabaseError(f"missing sqlite migration for version {version}")
                self._conn.execute(f"PRAGMA user_version = {version}")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

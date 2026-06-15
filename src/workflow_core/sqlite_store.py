"""Shared sqlite lifecycle for the harness's small stores.

MetricsStore and NfrStore are both tiny file-backed sqlite stores; this base
owns the one thing they genuinely share -- connection lifecycle (parent-dir
creation, schema bootstrap, close, context-manager protocol) -- so each store
keeps only its own schema and queries.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self

_MEMORY_PATH = ":memory:"


class SqliteStore:
    """Connection lifecycle base; subclasses provide schema and queries."""

    def __init__(self, path: Path | str, *, schema: str) -> None:
        if str(path) != _MEMORY_PATH:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(schema)
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

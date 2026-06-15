"""Append-only JSONL trace writer (Plan-N0002 R14).

Writer only: ``trace ingest`` into sqlite is not in the v2 deliverable list
and stays deferred. ``seq`` resumes from the existing line count so appends
across processes stay monotonic within one session file.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

EVENTS = frozenset(
    {
        "tool_call",
        "tool_result",
        "command",
        "diff_applied",
        "file_touched",
        "decision",
        "check_result",
        "metric_recorded",
        "verdict",
        "gate_result",
        "escalation",
    }
)


class TraceWriter:
    """Appends R14 event envelopes to one session-scoped JSONL file."""

    def __init__(self, path: Path | str, *, session_id: str, actor: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._session_id = session_id
        self._actor = actor
        self._seq = self._existing_lines()

    def _existing_lines(self) -> int:
        if not self._path.exists():
            return 0
        with self._path.open("r", encoding="utf-8") as fh:
            return sum(1 for _ in fh)

    def emit(
        self,
        event: str,
        payload: Mapping[str, object] | None = None,
        refs: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        if event not in EVENTS:
            raise ValueError(f"unknown trace event {event!r}; expected one of {sorted(EVENTS)}")
        self._seq += 1
        envelope: dict[str, object] = {
            "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "session_id": self._session_id,
            "seq": self._seq,
            "actor": self._actor,
            "event": event,
            "payload": dict(payload or {}),
            "refs": dict(refs or {}),
        }
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(envelope, sort_keys=True) + "\n")
        return envelope

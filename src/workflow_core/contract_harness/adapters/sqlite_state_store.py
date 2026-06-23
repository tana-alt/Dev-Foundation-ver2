from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from workflow_core.contract_harness.domain.errors import IntegrityError
from workflow_core.contract_harness.domain.models import ArtifactRef, StateEvent, WorkflowPhase
from workflow_core.contract_harness.hashing import (
    canonical_json,
    hash_json,
    sha256_bytes,
    sha256_text,
)
from workflow_core.contract_harness.ports.evidence_store import EvidenceStore


class SQLiteStateStore:
    def __init__(self, path: Path, *, evidence_store: EvidenceStore | None = None) -> None:
        self.path = path
        self.evidence_store = evidence_store
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def append_event(
        self,
        *,
        task_id: str,
        candidate_id: str | None,
        event_type: str,
        from_phase: WorkflowPhase | str | None,
        to_phase: WorkflowPhase | str,
        payload: dict[str, Any],
        actor: str,
    ) -> StateEvent:
        payload_json = canonical_json(payload)
        payload_sha256 = sha256_text(payload_json)
        created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        from_value = _phase_value(from_phase)
        to_value = _phase_value(to_phase) or WorkflowPhase.UNKNOWN.value
        with self._connect(immediate=True) as db:
            previous = _latest_event_sha(db)
            event_payload = _event_payload(
                task_id=task_id,
                candidate_id=candidate_id,
                event_type=event_type,
                from_value=from_value,
                to_value=to_value,
                payload_sha256=payload_sha256,
                previous=previous,
                actor=actor,
                created_at=created_at,
            )
            event_sha256 = hash_json(event_payload)
            event_id = _insert_event(db, event_payload, payload_json, event_sha256)
            _upsert_task_event(db, task_id, to_value, candidate_id, event_sha256)
            if candidate_id is not None:
                _upsert_candidate_event(
                    db,
                    task_id=task_id,
                    candidate_id=candidate_id,
                    payload=payload,
                    to_value=to_value,
                    created_at=created_at,
                )
            return _state_event(event_id, event_payload, payload_json, event_sha256)

    def record_artifact(
        self,
        *,
        task_id: str,
        artifact_type: str,
        ref: ArtifactRef,
        compatibility_path: str | None = None,
    ) -> None:
        created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._connect(immediate=True) as db:
            db.execute(
                """
                INSERT INTO artifacts (
                    sha256, task_id, artifact_type, media_type, size_bytes,
                    storage_uri, compatibility_path, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sha256) DO UPDATE SET
                    task_id = excluded.task_id,
                    artifact_type = excluded.artifact_type,
                    media_type = excluded.media_type,
                    size_bytes = excluded.size_bytes,
                    storage_uri = excluded.storage_uri,
                    compatibility_path = excluded.compatibility_path
                """,
                (
                    ref.sha256,
                    task_id,
                    artifact_type,
                    ref.media_type,
                    ref.size_bytes,
                    ref.storage_uri,
                    compatibility_path,
                    created_at,
                ),
            )

    def create_session(
        self,
        *,
        session_id: str,
        task_id: str | None,
        role: str,
        agent_id: str,
        capabilities: list[str],
        token_hash: str,
        created_at: str,
        expires_at: str | None,
    ) -> None:
        with self._connect(immediate=True) as db:
            db.execute(
                """
                INSERT INTO sessions (
                    session_id, task_id, role, agent_id, capabilities_json,
                    token_hash, status, created_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    session_id,
                    task_id,
                    role,
                    agent_id,
                    json.dumps(capabilities, sort_keys=True),
                    token_hash,
                    created_at,
                    expires_at,
                ),
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return None if row is None else _session_from_row(row)

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM sessions ORDER BY created_at, session_id").fetchall()
        return [_session_from_row(row) for row in rows]

    def revoke_session(self, session_id: str) -> bool:
        with self._connect(immediate=True) as db:
            cursor = db.execute(
                "UPDATE sessions SET status = 'revoked' WHERE session_id = ?",
                (session_id,),
            )
        return cursor.rowcount > 0

    def request_effect(
        self,
        *,
        effect_type: str,
        task_id: str,
        candidate_id: str | None,
        idempotency_key: str,
        payload: dict[str, Any],
        requested_event_sha256: str | None,
    ) -> dict[str, Any]:
        now = _utc_now()
        effect_id = f"eff_{uuid4().hex}"
        with self._connect(immediate=True) as db:
            existing = db.execute(
                "SELECT * FROM external_effects WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                return _effect_from_row(existing)
            db.execute(
                """
                INSERT INTO external_effects (
                    effect_id, task_id, candidate_id, effect_type, status,
                    idempotency_key, external_ref, observed_hash, payload_json,
                    requested_event_sha256, result_event_sha256, attempt_count,
                    last_error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'requested', ?, NULL, NULL, ?, ?, NULL, 0, NULL, ?, ?)
                """,
                (
                    effect_id,
                    task_id,
                    candidate_id,
                    effect_type,
                    idempotency_key,
                    canonical_json(payload),
                    requested_event_sha256,
                    now,
                    now,
                ),
            )
            row = db.execute(
                "SELECT * FROM external_effects WHERE effect_id = ?",
                (effect_id,),
            ).fetchone()
        if row is None:
            raise IntegrityError("effect insert did not return a row")
        return _effect_from_row(row)

    def get_effect(self, effect_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM external_effects WHERE effect_id = ?",
                (effect_id,),
            ).fetchone()
        return None if row is None else _effect_from_row(row)

    def get_effect_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM external_effects WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return None if row is None else _effect_from_row(row)

    def update_effect(
        self,
        effect_id: str,
        *,
        status: str,
        external_ref: str | None = None,
        observed_hash: str | None = None,
        result_event_sha256: str | None = None,
        last_error: str | None = None,
        increment_attempt: bool = False,
    ) -> dict[str, Any]:
        now = _utc_now()
        with self._connect(immediate=True) as db:
            db.execute(
                """
                UPDATE external_effects
                SET status = ?,
                    external_ref = COALESCE(?, external_ref),
                    observed_hash = COALESCE(?, observed_hash),
                    result_event_sha256 = COALESCE(?, result_event_sha256),
                    last_error = ?,
                    attempt_count = attempt_count + ?,
                    updated_at = ?
                WHERE effect_id = ?
                """,
                (
                    status,
                    external_ref,
                    observed_hash,
                    result_event_sha256,
                    last_error,
                    1 if increment_attempt else 0,
                    now,
                    effect_id,
                ),
            )
            row = db.execute(
                "SELECT * FROM external_effects WHERE effect_id = ?",
                (effect_id,),
            ).fetchone()
        if row is None:
            raise IntegrityError("effect update did not find a row")
        return _effect_from_row(row)

    def list_effects(self, statuses: list[str] | None = None) -> list[dict[str, Any]]:
        params: list[str] = []
        where = ""
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            where = f"WHERE status IN ({placeholders})"
            params.extend(statuses)
        with self._connect() as db:
            rows = db.execute(
                f"SELECT * FROM external_effects {where} ORDER BY created_at, effect_id",
                params,
            ).fetchall()
        return [_effect_from_row(row) for row in rows]

    def current_phase(self, task_id: str) -> WorkflowPhase | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT current_phase FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkflowPhase(str(row["current_phase"]))

    def current_event_sha256(self, task_id: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT current_event_sha256 FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return None if row is None else str(row["current_event_sha256"])

    def latest_event(
        self,
        task_id: str,
        *,
        event_type: str | None = None,
        candidate_id: str | None = None,
    ) -> StateEvent | None:
        where = ["task_id = ?"]
        params: list[str] = [task_id]
        if event_type is not None:
            where.append("event_type = ?")
            params.append(event_type)
        if candidate_id is not None:
            where.append("candidate_id = ?")
            params.append(candidate_id)
        with self._connect() as db:
            row = db.execute(
                f"""
                SELECT * FROM events
                WHERE {" AND ".join(where)}
                ORDER BY id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        return None if row is None else _event_from_row(row)

    def verify_integrity(self) -> dict[str, Any]:
        with self._connect() as db:
            events = db.execute("SELECT * FROM events ORDER BY id").fetchall()
            previous: str | None = None
            for row in events:
                if row["previous_event_sha256"] != previous:
                    raise IntegrityError("event hash chain mismatch")
                payload_json = str(row["payload_json"])
                if sha256_text(payload_json) != row["payload_sha256"]:
                    raise IntegrityError("payload hash mismatch")
                expected_event = hash_json(
                    {
                        "task_id": row["task_id"],
                        "candidate_id": row["candidate_id"],
                        "event_type": row["event_type"],
                        "from_phase": row["from_phase"],
                        "to_phase": row["to_phase"],
                        "payload_sha256": row["payload_sha256"],
                        "previous_event_sha256": row["previous_event_sha256"],
                        "actor": row["actor"],
                        "created_at": row["created_at"],
                    }
                )
                if expected_event != row["event_sha256"]:
                    raise IntegrityError("event hash mismatch")
                self._verify_event_artifact_reference(db, payload_json)
                previous = str(row["event_sha256"])
            self._verify_task_projection(db)
            artifact_count = self._verify_artifacts(db)
        return {
            "status": "pass",
            "event_count": len(events),
            "artifact_count": artifact_count,
        }

    def _verify_task_projection(self, db: sqlite3.Connection) -> None:
        tasks = db.execute("SELECT * FROM tasks ORDER BY task_id").fetchall()
        for task in tasks:
            latest = db.execute(
                """
                SELECT * FROM events
                WHERE task_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (task["task_id"],),
            ).fetchone()
            if latest is None:
                raise IntegrityError("task projection without event")
            if task["current_event_sha256"] != latest["event_sha256"]:
                raise IntegrityError("task current event mismatch")
            if task["current_phase"] != latest["to_phase"]:
                raise IntegrityError("task current phase mismatch")

    def _verify_artifacts(self, db: sqlite3.Connection) -> int:
        rows = db.execute("SELECT * FROM artifacts ORDER BY sha256").fetchall()
        for row in rows:
            sha256 = str(row["sha256"])
            if self.evidence_store is not None and not self.evidence_store.exists(sha256):
                raise IntegrityError(f"missing evidence object: {sha256}")
            if self.evidence_store is not None:
                data = self.evidence_store.get_bytes(sha256)
                if sha256_bytes(data) != sha256:
                    raise IntegrityError(f"evidence hash mismatch: {sha256}")
                if len(data) != int(row["size_bytes"]):
                    raise IntegrityError(f"evidence size mismatch: {sha256}")
        return len(rows)

    def _verify_event_artifact_reference(
        self,
        db: sqlite3.Connection,
        payload_json: str,
    ) -> None:
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError as exc:
            raise IntegrityError("event payload is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise IntegrityError("event payload is not a JSON object")
        artifact_sha = payload.get("artifact_sha256")
        if artifact_sha is None:
            return
        row = db.execute(
            "SELECT sha256 FROM artifacts WHERE sha256 = ?",
            (str(artifact_sha),),
        ).fetchone()
        if row is None:
            raise IntegrityError(f"missing artifact row: {artifact_sha}")

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript(_DDL)
            _migrate_external_effects(db)
        self.path.chmod(0o600)

    @contextmanager
    def _connect(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA journal_mode = WAL")
            if immediate:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        finally:
            db.close()


def _phase_value(value: WorkflowPhase | str | None) -> str | None:
    if value is None:
        return None
    return value.value if isinstance(value, WorkflowPhase) else str(value)


def _latest_event_sha(db: sqlite3.Connection) -> str | None:
    row = db.execute("SELECT event_sha256 FROM events ORDER BY id DESC LIMIT 1").fetchone()
    return None if row is None else str(row["event_sha256"])


def _event_payload(
    *,
    task_id: str,
    candidate_id: str | None,
    event_type: str,
    from_value: str | None,
    to_value: str,
    payload_sha256: str,
    previous: str | None,
    actor: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "candidate_id": candidate_id,
        "event_type": event_type,
        "from_phase": from_value,
        "to_phase": to_value,
        "payload_sha256": payload_sha256,
        "previous_event_sha256": previous,
        "actor": actor,
        "created_at": created_at,
    }


def _insert_event(
    db: sqlite3.Connection,
    event_payload: dict[str, Any],
    payload_json: str,
    event_sha256: str,
) -> int:
    cursor = db.execute(
        """
        INSERT INTO events (
            task_id, candidate_id, event_type, from_phase, to_phase,
            payload_json, payload_sha256, previous_event_sha256,
            event_sha256, actor, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_payload["task_id"],
            event_payload["candidate_id"],
            event_payload["event_type"],
            event_payload["from_phase"],
            event_payload["to_phase"],
            payload_json,
            event_payload["payload_sha256"],
            event_payload["previous_event_sha256"],
            event_sha256,
            event_payload["actor"],
            event_payload["created_at"],
        ),
    )
    event_id = cursor.lastrowid
    if event_id is None:
        raise IntegrityError("event insert did not return an id")
    return event_id


def _upsert_task_event(
    db: sqlite3.Connection,
    task_id: str,
    to_value: str,
    candidate_id: str | None,
    event_sha256: str,
) -> None:
    db.execute(
        """
        INSERT INTO tasks (
            task_id, current_phase, current_candidate_id, current_event_sha256
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(task_id) DO UPDATE SET
            current_phase = excluded.current_phase,
            current_candidate_id = excluded.current_candidate_id,
            current_event_sha256 = excluded.current_event_sha256
        """,
        (task_id, to_value, candidate_id, event_sha256),
    )


def _upsert_candidate_event(
    db: sqlite3.Connection,
    *,
    task_id: str,
    candidate_id: str,
    payload: dict[str, Any],
    to_value: str,
    created_at: str,
) -> None:
    patch_sha = str(payload.get("candidate_diff_sha256") or payload.get("patch_sha256") or "")
    db.execute(
        """
        INSERT INTO candidates (
            candidate_id, task_id, base_sha, patch_sha256, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(candidate_id) DO UPDATE SET status = excluded.status
        """,
        (
            candidate_id,
            task_id,
            str(payload.get("base_sha") or ""),
            patch_sha,
            to_value,
            created_at,
        ),
    )


def _state_event(
    event_id: int,
    event_payload: dict[str, Any],
    payload_json: str,
    event_sha256: str,
) -> StateEvent:
    from_value = event_payload["from_phase"]
    return StateEvent(
        id=event_id,
        task_id=str(event_payload["task_id"]),
        candidate_id=(
            str(event_payload["candidate_id"])
            if event_payload["candidate_id"] is not None
            else None
        ),
        event_type=str(event_payload["event_type"]),
        from_phase=WorkflowPhase(str(from_value)) if from_value else None,
        to_phase=WorkflowPhase(str(event_payload["to_phase"])),
        payload_json=payload_json,
        payload_sha256=str(event_payload["payload_sha256"]),
        previous_event_sha256=(
            str(event_payload["previous_event_sha256"])
            if event_payload["previous_event_sha256"] is not None
            else None
        ),
        event_sha256=event_sha256,
        actor=str(event_payload["actor"]),
        created_at=str(event_payload["created_at"]),
    )


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    data = json.loads(value)
    if not isinstance(data, dict):
        raise IntegrityError("stored JSON payload must be an object")
    return data


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    data = json.loads(value)
    if not isinstance(data, list):
        raise IntegrityError("stored JSON list must be an array")
    return [str(item) for item in data]


def _session_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "session_id": str(row["session_id"]),
        "task_id": str(row["task_id"]) if row["task_id"] is not None else None,
        "role": str(row["role"]),
        "agent_id": str(row["agent_id"]),
        "capabilities": _json_list(str(row["capabilities_json"])),
        "token_hash": str(row["token_hash"]),
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
        "expires_at": str(row["expires_at"]) if row["expires_at"] is not None else None,
    }


def _effect_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "effect_id": str(row["effect_id"]),
        "task_id": str(row["task_id"]),
        "candidate_id": str(row["candidate_id"]) if row["candidate_id"] is not None else None,
        "effect_type": str(row["effect_type"]),
        "status": str(row["status"]),
        "idempotency_key": str(row["idempotency_key"]),
        "external_ref": str(row["external_ref"]) if row["external_ref"] is not None else None,
        "observed_hash": str(row["observed_hash"]) if row["observed_hash"] is not None else None,
        "payload": _json_object(str(row["payload_json"]) if row["payload_json"] else None),
        "requested_event_sha256": (
            str(row["requested_event_sha256"])
            if row["requested_event_sha256"] is not None
            else None
        ),
        "result_event_sha256": (
            str(row["result_event_sha256"]) if row["result_event_sha256"] is not None else None
        ),
        "attempt_count": int(row["attempt_count"] or 0),
        "last_error": str(row["last_error"]) if row["last_error"] is not None else None,
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]) if row["updated_at"] is not None else None,
    }


def _migrate_external_effects(db: sqlite3.Connection) -> None:
    columns = {str(row["name"]) for row in db.execute("PRAGMA table_info(external_effects)")}
    additions = {
        "payload_json": "ALTER TABLE external_effects ADD COLUMN payload_json TEXT DEFAULT '{}'",
        "requested_event_sha256": (
            "ALTER TABLE external_effects ADD COLUMN requested_event_sha256 TEXT"
        ),
        "result_event_sha256": "ALTER TABLE external_effects ADD COLUMN result_event_sha256 TEXT",
        "attempt_count": (
            "ALTER TABLE external_effects ADD COLUMN attempt_count INTEGER DEFAULT 0"
        ),
        "last_error": "ALTER TABLE external_effects ADD COLUMN last_error TEXT",
        "updated_at": "ALTER TABLE external_effects ADD COLUMN updated_at TEXT",
    }
    for name, sql in additions.items():
        if name not in columns:
            db.execute(sql)


def _event_from_row(row: sqlite3.Row) -> StateEvent:
    from_value = str(row["from_phase"]) if row["from_phase"] is not None else None
    return StateEvent(
        id=int(row["id"]),
        task_id=str(row["task_id"]),
        candidate_id=str(row["candidate_id"]) if row["candidate_id"] is not None else None,
        event_type=str(row["event_type"]),
        from_phase=WorkflowPhase(from_value) if from_value else None,
        to_phase=WorkflowPhase(str(row["to_phase"])),
        payload_json=str(row["payload_json"]),
        payload_sha256=str(row["payload_sha256"]),
        previous_event_sha256=(
            str(row["previous_event_sha256"]) if row["previous_event_sha256"] is not None else None
        ),
        event_sha256=str(row["event_sha256"]),
        actor=str(row["actor"]),
        created_at=str(row["created_at"]),
    )


_DDL = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    candidate_id TEXT,
    event_type TEXT NOT NULL,
    from_phase TEXT,
    to_phase TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    previous_event_sha256 TEXT,
    event_sha256 TEXT NOT NULL UNIQUE,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    current_phase TEXT NOT NULL,
    current_candidate_id TEXT,
    current_event_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    base_sha TEXT NOT NULL,
    patch_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    sha256 TEXT PRIMARY KEY,
    task_id TEXT,
    artifact_type TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    storage_uri TEXT NOT NULL,
    compatibility_path TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    task_id TEXT,
    role TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS external_effects (
    effect_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    candidate_id TEXT,
    effect_type TEXT NOT NULL,
    status TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    external_ref TEXT,
    observed_hash TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    requested_event_sha256 TEXT,
    result_event_sha256 TEXT,
    attempt_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
"""

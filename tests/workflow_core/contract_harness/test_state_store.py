from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from workflow_core.contract_harness.adapters.filesystem_evidence_store import (
    FilesystemEvidenceStore,
)
from workflow_core.contract_harness.adapters.sqlite_state_store import SQLiteStateStore
from workflow_core.contract_harness.domain.errors import IntegrityError
from workflow_core.contract_harness.domain.models import WorkflowPhase


def test_state_store_appends_hash_chained_events_and_verifies_integrity(tmp_path: Path) -> None:
    evidence = FilesystemEvidenceStore(tmp_path / "objects")
    store = SQLiteStateStore(tmp_path / "state.db", evidence_store=evidence)
    ref = evidence.put_json({"status": "pass"})
    store.record_artifact(
        task_id="T-0001",
        artifact_type="verify_result",
        ref=ref,
        compatibility_path="verify-result.json",
    )

    first = store.append_event(
        task_id="T-0001",
        candidate_id=None,
        event_type="PREPARE",
        from_phase=None,
        to_phase=WorkflowPhase.PREPARED,
        payload={"contract_sha256": "sha256:first"},
        actor="harness",
    )
    second = store.append_event(
        task_id="T-0001",
        candidate_id="cand_123",
        event_type="VERIFY",
        from_phase=WorkflowPhase.PREPARED,
        to_phase=WorkflowPhase.VERIFIED,
        payload={"artifact_sha256": ref.sha256},
        actor="harness",
    )

    assert second.previous_event_sha256 == first.event_sha256
    assert store.current_phase("T-0001") == WorkflowPhase.VERIFIED
    assert store.verify_integrity()["status"] == "pass"


def test_state_store_detects_missing_evidence_object(tmp_path: Path) -> None:
    evidence = FilesystemEvidenceStore(tmp_path / "objects")
    store = SQLiteStateStore(tmp_path / "state.db", evidence_store=evidence)
    ref = evidence.put_json({"status": "pass"})
    store.record_artifact(task_id="T-0001", artifact_type="verify_result", ref=ref)
    evidence.path_for(ref.sha256).unlink()

    with pytest.raises(IntegrityError, match="missing evidence object"):
        store.verify_integrity()


def test_state_store_detects_missing_event_artifact_row(tmp_path: Path) -> None:
    evidence = FilesystemEvidenceStore(tmp_path / "objects")
    db_path = tmp_path / "state.db"
    store = SQLiteStateStore(db_path, evidence_store=evidence)
    ref = evidence.put_json({"status": "pass"})
    store.record_artifact(task_id="T-0001", artifact_type="verify_result", ref=ref)
    store.append_event(
        task_id="T-0001",
        candidate_id=None,
        event_type="VERIFY",
        from_phase=None,
        to_phase=WorkflowPhase.VERIFIED,
        payload={"artifact_sha256": ref.sha256},
        actor="harness",
    )
    with sqlite3.connect(db_path) as db:
        db.execute("DELETE FROM artifacts WHERE sha256 = ?", (ref.sha256,))

    with pytest.raises(IntegrityError, match="missing artifact row"):
        store.verify_integrity()


def test_state_store_detects_tampered_evidence_bytes(tmp_path: Path) -> None:
    evidence = FilesystemEvidenceStore(tmp_path / "objects")
    store = SQLiteStateStore(tmp_path / "state.db", evidence_store=evidence)
    ref = evidence.put_json({"status": "pass"})
    store.record_artifact(task_id="T-0001", artifact_type="verify_result", ref=ref)
    store.append_event(
        task_id="T-0001",
        candidate_id=None,
        event_type="VERIFY",
        from_phase=None,
        to_phase=WorkflowPhase.VERIFIED,
        payload={"artifact_sha256": ref.sha256},
        actor="harness",
    )
    evidence.path_for(ref.sha256).write_text('{"status":"tampered"}', encoding="utf-8")

    with pytest.raises(IntegrityError, match="evidence hash mismatch"):
        store.verify_integrity()

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.adapters.filesystem_evidence_store import (
    FilesystemEvidenceStore,
)
from workflow_core.contract_harness.adapters.sqlite_state_store import (
    SQLiteStateReader,
    SQLiteStateStore,
)
from workflow_core.contract_harness.domain.authority import artifact_type_for
from workflow_core.contract_harness.domain.errors import IntegrityError
from workflow_core.contract_harness.domain.models import StateEvent, WorkflowPhase
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json_atomic
from workflow_core.contract_harness.runtime_paths import runtime_root, task_dir


def evidence_root(root: Path) -> Path:
    return runtime_root(root) / "objects" / "sha256"


def state_db_path(root: Path) -> Path:
    return runtime_root(root) / "state" / "workflow-state.db"


def evidence_store(root: Path) -> FilesystemEvidenceStore:
    return FilesystemEvidenceStore(evidence_root(root))


def state_store(root: Path) -> SQLiteStateStore:
    evidence = evidence_store(root)
    return SQLiteStateStore(state_db_path(root), evidence_store=evidence)


def state_reader(root: Path) -> SQLiteStateReader:
    evidence = evidence_store(root)
    return SQLiteStateReader(state_db_path(root), evidence_store=evidence)


def candidate_id_from_patch_sha256(patch_sha256: str) -> str:
    return f"cand_{patch_sha256.removeprefix('sha256:')[:12]}"


def record_authority_artifact(
    root: Path,
    task_id: str,
    name: str,
    *,
    event_type: str,
    to_phase: WorkflowPhase,
    payload: dict[str, Any] | None = None,
    candidate_id: str | None = None,
    actor: str | None = None,
    media_type: str | None = None,
) -> StateEvent:
    path = task_dir(root, task_id) / name
    data = path.read_bytes()
    evidence = evidence_store(root)
    ref = evidence.put_bytes(data, media_type or _media_type(name))
    store = state_store(root)
    store.record_artifact(
        task_id=task_id,
        artifact_type=artifact_type_for(name),
        ref=ref,
        compatibility_path=name,
    )
    current = store.current_phase(task_id)
    event_payload = {
        "artifact": name,
        "artifact_sha256": ref.sha256,
        "compatibility_path": name,
        **(payload or {}),
    }
    event = store.append_event(
        task_id=task_id,
        candidate_id=candidate_id,
        event_type=event_type,
        from_phase=current,
        to_phase=to_phase,
        payload=event_payload,
        actor=_actor(actor),
    )
    _update_authority_manifest(
        root,
        task_id,
        name=name,
        artifact_type=artifact_type_for(name),
        sha256=ref.sha256,
        storage_uri=ref.storage_uri,
        event_sha256=event.event_sha256,
    )
    return event


def state_summary(root: Path, task_id: str) -> dict[str, Any]:
    db_path = state_db_path(root)
    if not db_path.is_file():
        return {"integrity": "absent", "current_phase": None, "current_event_sha256": None}
    store = state_reader(root)
    try:
        integrity = store.verify_integrity()
        integrity_status = str(integrity["status"])
    except IntegrityError as exc:
        return {
            "integrity": "fail",
            "reason": str(exc),
            "current_phase": _phase_value(store.current_phase(task_id)),
            "current_event_sha256": store.current_event_sha256(task_id),
        }
    return {
        "integrity": integrity_status,
        "current_phase": _phase_value(store.current_phase(task_id)),
        "current_event_sha256": store.current_event_sha256(task_id),
    }


def latest_event_payload(
    root: Path,
    task_id: str,
    event_type: str,
    *,
    candidate_id: str | None = None,
) -> dict[str, Any] | None:
    db_path = state_db_path(root)
    if not db_path.is_file():
        return None
    event = state_reader(root).latest_event(
        task_id,
        event_type=event_type,
        candidate_id=candidate_id,
    )
    if event is None:
        return None
    data = json.loads(event.payload_json)
    if not isinstance(data, dict):
        raise ValueError("state event payload must be a JSON object")
    return data


def _update_authority_manifest(
    root: Path,
    task_id: str,
    *,
    name: str,
    artifact_type: str,
    sha256: str,
    storage_uri: str,
    event_sha256: str,
) -> None:
    path = task_dir(root, task_id) / "authority-manifest.json"
    try:
        manifest = read_json(path)
    except (OSError, ValueError):
        manifest = {
            "schema_version": 1,
            "task_id": task_id,
            "authority_artifacts": {},
            "written_by": "harness",
        }
    artifacts = manifest.setdefault("authority_artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
        manifest["authority_artifacts"] = artifacts
    artifacts[name] = {
        "artifact_type": artifact_type,
        "sha256": sha256,
        "storage_uri": storage_uri,
        "compatibility_path": name,
        "compatibility_sha256": file_hash(task_dir(root, task_id) / name),
        "state_event_sha256": event_sha256,
    }
    write_json_atomic(path, manifest)


def _media_type(name: str) -> str:
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".diff") or name.endswith(".patch"):
        return "text/x-diff"
    return "application/octet-stream"


def _phase_value(phase: WorkflowPhase | None) -> str | None:
    return None if phase is None else phase.value


def _actor(actor: str | None) -> str:
    return actor or os.environ.get("HARNESS_ACTOR") or "harness"

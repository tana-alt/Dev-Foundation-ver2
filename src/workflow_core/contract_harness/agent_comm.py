from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from workflow_core.contract_harness.hashing import file_hash, hash_json
from workflow_core.contract_harness.jsonio import write_json
from workflow_core.contract_harness.runtime_paths import runtime_root, task_dir
from workflow_core.contract_harness.status import task_status

ALLOWED_INTENTS = {
    "action_request",
    "status_query",
    "status_response",
    "proposal",
    "clarification",
    "rework_hint",
    "artifact_summary",
    "test_request",
    "review_question",
    "handoff_note",
}

FORBIDDEN_AUTHORITY_CLAIMS = {
    "completion_claim",
    "done_claim",
    "review_verdict",
    "gate_result",
    "land_result",
    "push_result",
    "mergeable_claim",
}

_STATUS_ARTIFACTS = {
    "candidate.diff": "candidate_diff",
    "verify-result.json": "verify_result",
    "submission.json": "submission",
    "gate-result.json": "gate_result",
    "land-result.json": "land_result",
    "oracle-result.json": "oracle_result",
    "push-result.json": "push_result",
    "rework-request.json": "rework_request",
}


def send_message(
    root: Path,
    task_id: str,
    *,
    from_agent_id: str,
    from_role: str,
    to_agent_id: str,
    to_role: str,
    kind: str,
    subject: str,
    body_markdown: str,
    basis_refs: list[dict[str, Any]] | None = None,
    artifact_refs: list[dict[str, Any]] | None = None,
    auto_basis_refs: bool = True,
) -> dict[str, Any]:
    _validate_kind(kind)
    _validate_artifact_refs(artifact_refs or [])
    warnings: list[str] = []
    refs = list(basis_refs or [])
    if auto_basis_refs:
        try:
            refs.extend(_auto_basis_refs(root, task_id, kind))
        except (OSError, ValueError, RuntimeError) as exc:
            warnings.append(f"basis_refs_auto_attach_failed: {exc}")
    envelope = {
        "schema_version": 1,
        "message_sha256": "",
        "correlation_handle": _correlation_handle(),
        "task_id": task_id,
        "from": {
            "agent_id": from_agent_id,
            "role": from_role,
        },
        "to": {
            "agent_id": to_agent_id,
            "role": to_role,
        },
        "kind": kind,
        "subject": subject,
        "body_markdown": body_markdown,
        "basis_refs": refs,
        "artifact_refs": artifact_refs or [],
        "warnings": warnings,
        "expires_at": (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "written_by": "agent-comm-switchboard",
    }
    envelope["message_sha256"] = hash_json({**envelope, "message_sha256": ""})
    _write_message(root, task_id, envelope)
    return envelope


def build_status_response(
    root: Path,
    task_id: str,
    *,
    from_agent_id: str,
    from_role: str,
    to_agent_id: str,
    to_role: str,
) -> dict[str, Any]:
    try:
        status = task_status(root, task_id)
        body = _status_body(status)
    except (OSError, ValueError, RuntimeError) as exc:
        status = {
            "schema_version": 1,
            "task_id": task_id,
            "phase": "unknown",
            "authority": {"complete": False, "source": f"unknown: {exc}"},
            "artifacts": {"present": [], "missing": []},
            "written_by": "harness",
        }
        body = f"status is unknown or partial: {exc}"
    return send_message(
        root,
        task_id,
        from_agent_id=from_agent_id,
        from_role=from_role,
        to_agent_id=to_agent_id,
        to_role=to_role,
        kind="status_response",
        subject=f"Status for {task_id}",
        body_markdown=body,
        basis_refs=[{"type": "harness_status", "value": status}],
        auto_basis_refs=True,
    )


def _validate_kind(kind: str) -> None:
    if kind in FORBIDDEN_AUTHORITY_CLAIMS:
        raise ValueError(f"message kind is forbidden authority claim: {kind}")
    if kind not in ALLOWED_INTENTS:
        raise ValueError(f"message kind is not allowed: {kind}")


def _validate_artifact_refs(refs: list[dict[str, Any]]) -> None:
    for ref in refs:
        if "path" in ref and not str(ref.get("sha256") or "").startswith("sha256:"):
            raise ValueError("artifact_ref requires sha256")


def _auto_basis_refs(root: Path, task_id: str, kind: str) -> list[dict[str, Any]]:
    if kind not in {"status_query", "status_response", "artifact_summary", "rework_hint"}:
        return []
    runtime = task_dir(root, task_id)
    refs = []
    for name, ref_type in _STATUS_ARTIFACTS.items():
        path = runtime / name
        if path.is_file():
            refs.append({"type": ref_type, "path": str(path), "sha256": file_hash(path)})
    return refs


def _write_message(root: Path, task_id: str, envelope: dict[str, Any]) -> None:
    runtime = task_dir(root, task_id)
    message_sha = str(envelope["message_sha256"])
    to_agent = str(envelope["to"]["agent_id"])
    handle = _safe_component(str(envelope["correlation_handle"]))
    write_json(runtime / "comm" / "inbox" / to_agent / f"{message_sha}.json", envelope)
    thread = {
        "schema_version": 1,
        "task_id": task_id,
        "correlation_handle": envelope["correlation_handle"],
        "message_sha256": message_sha,
        "message_path": str(runtime / "comm" / "inbox" / to_agent / f"{message_sha}.json"),
        "runtime_root": str(runtime_root(root)),
        "written_by": "agent-comm-switchboard",
    }
    write_json(runtime / "comm" / "threads" / f"{handle}.json", thread)


def _status_body(status: dict[str, Any]) -> str:
    artifacts_obj = status.get("artifacts")
    artifacts = cast(dict[str, Any], artifacts_obj) if isinstance(artifacts_obj, dict) else {}
    present = ", ".join(str(item) for item in artifacts.get("present", [])) or "none"
    missing = ", ".join(str(item) for item in artifacts.get("missing", [])) or "none"
    authority_obj = status.get("authority")
    authority = cast(dict[str, Any], authority_obj) if isinstance(authority_obj, dict) else {}
    return (
        f"phase: {status.get('phase', 'unknown')}\n"
        f"present artifacts: {present}\n"
        f"missing artifacts: {missing}\n"
        f"completion authority: {authority.get('source', 'unknown')}"
    )


def _correlation_handle() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"rt:{stamp}"


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    return cleaned.strip(".-") or "thread"

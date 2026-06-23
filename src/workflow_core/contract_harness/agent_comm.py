from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from workflow_core.contract_harness.hashing import file_hash, hash_json
from workflow_core.contract_harness.jsonio import read_json, write_json
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
    in_reply_to: str | None = None,
    delegation_brief: str | None = None,
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
        "in_reply_to": in_reply_to,
        "basis_refs": refs,
        "artifact_refs": artifact_refs or [],
        "warnings": warnings,
        "expires_at": (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "written_by": "agent-comm-switchboard",
    }
    if delegation_brief:
        envelope["delegation"] = {
            "role": to_role,
            "brief": delegation_brief,
        }
    envelope["message_sha256"] = hash_json({**envelope, "message_sha256": ""})
    _write_message(root, task_id, envelope)
    return envelope


def send_peer_message(
    root: Path,
    task_id: str,
    *,
    to_agent_id: str,
    subject: str,
    body_markdown: str,
    from_agent_id: str,
    from_role: str,
    kind: str | None = None,
    in_reply_to: str | None = None,
    delegation_brief: str | None = None,
) -> dict[str, Any]:
    peer = find_peer(root, task_id, to_agent_id)
    reply_target = _reply_target(root, task_id, in_reply_to) if in_reply_to else None
    if in_reply_to and reply_target is None:
        raise ValueError(f"in_reply_to message not found: {in_reply_to}")
    if reply_target is not None and str(reply_target.get("agent_id") or "") != to_agent_id:
        raise ValueError("in_reply_to target does not match original sender")
    if peer is None and reply_target is None:
        raise ValueError(f"unknown peer: {to_agent_id}")
    to_role = str((peer or {}).get("role") or (reply_target or {}).get("role") or "writer")
    resolved_kind = kind or (
        "handoff_note" if in_reply_to else "action_request" if delegation_brief else "clarification"
    )
    return send_message(
        root,
        task_id,
        from_agent_id=from_agent_id,
        from_role=from_role,
        to_agent_id=to_agent_id,
        to_role=to_role,
        kind=resolved_kind,
        subject=subject,
        body_markdown=body_markdown,
        in_reply_to=in_reply_to,
        delegation_brief=delegation_brief,
    )


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


def list_inbox(root: Path, task_id: str, *, agent_id: str) -> dict[str, Any]:
    inbox = task_dir(root, task_id) / "comm" / "inbox" / agent_id
    messages: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in sorted(inbox.glob("*.json")) if inbox.is_dir() else []:
        try:
            messages.append(read_json(path))
        except (OSError, ValueError) as exc:
            warnings.append(f"message_read_failed:{path.name}: {exc}")
    return {
        "schema_version": 1,
        "task_id": task_id,
        "agent_id": agent_id,
        "inbox_path": str(inbox),
        "message_count": len(messages),
        "messages": messages,
        "warnings": warnings,
        "written_by": "agent-comm-switchboard",
    }


def list_peers(root: Path, task_id: str) -> dict[str, Any]:
    sessions = task_dir(root, task_id) / "comm" / "sessions"
    peers: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in sorted(sessions.glob("*.json")) if sessions.is_dir() else []:
        try:
            data = read_json(path)
        except (OSError, ValueError) as exc:
            warnings.append(f"peer_read_failed:{path.name}: {exc}")
            continue
        peers.append(
            {
                "agent_id": str(data.get("agent_id") or ""),
                "role": str(data.get("role") or ""),
                "brief": str(data.get("brief") or ""),
                "delegation_hash_id": str(data.get("delegation_hash_id") or ""),
                "status": str(data.get("status") or ""),
                "cwd": str(data.get("cwd") or ""),
            }
        )
    return {
        "schema_version": 1,
        "task_id": task_id,
        "peers": peers,
        "warnings": warnings,
        "written_by": "agent-comm-switchboard",
    }


def find_peer(root: Path, task_id: str, agent_id: str) -> dict[str, Any] | None:
    path = task_dir(root, task_id) / "comm" / "sessions" / f"{_safe_component(agent_id)}.json"
    if path.is_file():
        return read_json(path)
    return None


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


def _reply_target(root: Path, task_id: str, message_sha256: str | None) -> dict[str, str] | None:
    if not message_sha256:
        return None
    runtime = task_dir(root, task_id)
    for path in sorted((runtime / "comm" / "inbox").glob(f"*/{message_sha256}.json")):
        try:
            message = read_json(path)
        except (OSError, ValueError):
            continue
        sender = message.get("from")
        if isinstance(sender, dict):
            agent_id = sender.get("agent_id")
            role = sender.get("role")
            if isinstance(agent_id, str) and agent_id and isinstance(role, str) and role:
                return {"agent_id": agent_id, "role": role}
    return None


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

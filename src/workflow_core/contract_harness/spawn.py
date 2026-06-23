from __future__ import annotations

import shlex
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.agent_tools import (
    role_agent_tools,
    role_optional_tools,
)
from workflow_core.contract_harness.context_audit import audit_context
from workflow_core.contract_harness.contract import ensure_prepared, load_contract
from workflow_core.contract_harness.gitutil import common_dir
from workflow_core.contract_harness.jsonio import write_json
from workflow_core.contract_harness.launch import writer_session
from workflow_core.contract_harness.roles import current_role
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.worktree import create_worktree

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]


def spawn_session(
    root: Path,
    task_id: str,
    *,
    target_role: str,
    agent: str,
    agent_command: str,
    reviewer_id: str | None = None,
    profile: str = "default",
    comm: bool = False,
    brief: str = "",
) -> dict[str, Any]:
    _validate_target_role(current_role(), target_role)
    if target_role == "reviewer" and not reviewer_id:
        raise ValueError("reviewer-id is required when spawning reviewer")
    ensure_prepared(root, task_id)
    canonical = _canonical_root(root)
    if target_role == "writer":
        session = writer_session(canonical, task_id, agent_command=agent_command)
    else:
        worktree = create_worktree(
            canonical,
            task_id,
            kind=target_role,
            reviewer_id=reviewer_id if target_role == "reviewer" else None,
        )
        session = _role_session(
            canonical,
            task_id,
            role=target_role,
            agent_command=agent_command,
            worktree=worktree,
            reviewer_id=reviewer_id,
            profile=profile,
        )
    session = _with_agent_metadata(
        canonical,
        task_id,
        session,
        role=target_role,
        agent=agent,
        reviewer_id=reviewer_id,
        profile=profile,
        brief=brief,
    )
    _write_session(canonical, task_id, session, role=target_role, reviewer_id=reviewer_id)
    _write_rebind(canonical, task_id, session)
    if comm:
        _write_comm_session(canonical, task_id, session)
    return session


def _validate_target_role(caller_role: str, target_role: str) -> None:
    allowed = {
        "writer": {"writer"},
        "reviewer": {"reviewer"},
        "integrator": {"writer", "reviewer", "integrator"},
        "admin": {"writer", "reviewer", "integrator"},
    }
    if target_role not in {"writer", "reviewer", "integrator"}:
        raise ValueError("spawn role must be writer, reviewer, or integrator")
    if target_role not in allowed.get(caller_role, set()):
        raise ValueError(f"role {caller_role} cannot spawn {target_role}")


def _role_session(
    root: Path,
    task_id: str,
    *,
    role: str,
    agent_command: str,
    worktree: dict[str, Any],
    reviewer_id: str | None,
    profile: str,
) -> dict[str, Any]:
    path = Path(str(worktree["path"]))
    env = _role_env(root, task_id, role=role, agent_id="", reviewer_id=reviewer_id)
    command = _shell_command(path, env, agent_command)
    return {
        "task_id": task_id,
        "status": "ready",
        "role": role,
        "reviewer_id": reviewer_id,
        "cwd": str(path),
        "command": command,
        "argv": shlex.split(agent_command),
        "env": env,
        "worktree": worktree,
        "initial_context": _initial_context(root, task_id, role=role, profile=profile),
        "context_audit": audit_context(path, task_id),
        "handoff": _handoff_commands(root, task_id, role=role, reviewer_id=reviewer_id),
    }


def _with_agent_metadata(
    root: Path,
    task_id: str,
    session: dict[str, Any],
    *,
    role: str,
    agent: str,
    reviewer_id: str | None,
    profile: str,
    brief: str,
) -> dict[str, Any]:
    agent_id = _agent_id(
        task_id,
        role=role,
        agent=agent,
        reviewer_id=reviewer_id,
        brief=brief,
    )
    env = _role_env(root, task_id, role=role, agent_id=agent_id, reviewer_id=reviewer_id)
    cwd = Path(str(session["cwd"]))
    enriched = {
        **session,
        "agent": agent,
        "agent_id": agent_id,
        "profile": profile,
        "brief": brief,
        "delegation_hash_id": _delegation_hash_id(brief) if brief else "",
        "env": env,
        "command": _shell_command(
            cwd,
            env,
            " ".join(shlex.quote(part) for part in session["argv"]),
        ),
        "initial_context": _initial_context(root, task_id, role=role, profile=profile),
    }
    return enriched


def _role_env(
    root: Path,
    task_id: str,
    *,
    role: str,
    agent_id: str,
    reviewer_id: str | None,
) -> dict[str, str]:
    env = {
        "FOUNDATION_REPO_ROOT": str(_canonical_root(root)),
        "FOUNDATION_PROJECT_ID": task_id,
        "FOUNDATION_TASK_ID": task_id,
        "FOUNDATION_AGENT_ID": agent_id,
        "HARNESS_ROLE": role,
    }
    if reviewer_id:
        env["FOUNDATION_REVIEWER_ID"] = reviewer_id
    return env


def _initial_context(
    root: Path,
    task_id: str,
    *,
    role: str,
    profile: str,
) -> dict[str, Any]:
    tools = (
        role_agent_tools(root, task_id, role)
        if profile == "default"
        else role_optional_tools(root, task_id, role, profile)
    )
    contract = load_contract(root, task_id)
    return {
        "task_id": task_id,
        "role": role,
        "task_goal": contract.get("goal"),
        "scope_contract": contract["scope_contract"],
        "verifier_ids": [str(item.get("id", "")) for item in contract["verifier_plan"]],
        "acceptance": _acceptance_summary(contract.get("acceptance")),
        "policy": _policy_summary(contract.get("policy")),
        "artifact_refs": _artifact_refs(),
        "next_action": _next_action(role),
        "agent_tools": tools,
    }


def _acceptance_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    summary: dict[str, Any] = {}
    for key in ("mode", "source"):
        if key in value:
            summary[key] = value[key]
    audit = value.get("audit")
    if isinstance(audit, dict) and "status" in audit:
        summary["audit_status"] = audit["status"]
    return summary


def _policy_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    summary: dict[str, Any] = {}
    if "id" in value:
        summary["policy_id"] = value["id"]
    for key in ("policy_id", "human_gates", "external_writes"):
        if key in value:
            summary[key] = value[key]
    return summary


def _artifact_refs() -> dict[str, str]:
    return {
        "contract": "contract.lock.json",
        "capsule": "capsule.json",
        "verifier_plan": "verifier-plan.json",
    }


def _next_action(role: str) -> str:
    if role == "writer":
        return "implement verified candidate, then run harness verify and submit"
    if role == "reviewer":
        return "review submitted evidence and write a reviewer verdict"
    return "collect reviews, run gate, then land or return rework"


def _write_session(
    root: Path,
    task_id: str,
    session: dict[str, Any],
    *,
    role: str,
    reviewer_id: str | None,
) -> None:
    if role == "reviewer":
        assert reviewer_id is not None
        filename = f"reviewer-session-{_safe_component(reviewer_id)}.json"
    else:
        filename = f"{role}-session.json"
    write_json(task_dir(root, task_id) / filename, session)


def _write_rebind(root: Path, task_id: str, session: dict[str, Any]) -> None:
    agent_id = str(session["agent_id"])
    packet = {
        "schema_version": 1,
        "task_id": task_id,
        "agent_id": agent_id,
        "role": session["role"],
        "brief": session.get("brief", ""),
        "delegation_hash_id": session.get("delegation_hash_id", ""),
        "cwd": session["cwd"],
        "env": session["env"],
        "handoff": session["handoff"],
        "transcript_included": False,
        "written_by": "harness",
    }
    write_json(task_dir(root, task_id) / "comm" / "rebind" / f"{agent_id}.json", packet)


def _write_comm_session(root: Path, task_id: str, session: dict[str, Any]) -> None:
    agent_id = str(session["agent_id"])
    packet = {
        "schema_version": 1,
        "task_id": task_id,
        "agent_id": agent_id,
        "role": session["role"],
        "agent": session["agent"],
        "brief": session.get("brief", ""),
        "delegation_hash_id": session.get("delegation_hash_id", ""),
        "cwd": session["cwd"],
        "status": "ready",
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "written_by": "harness",
    }
    write_json(task_dir(root, task_id) / "comm" / "sessions" / f"{agent_id}.json", packet)


def _handoff_commands(
    root: Path,
    task_id: str,
    *,
    role: str,
    reviewer_id: str | None,
) -> dict[str, str]:
    harness = shlex.quote(str(_harness_path(root)))
    if role == "writer":
        return {
            "verify": f"HARNESS_ROLE=writer {harness} verify {task_id}",
            "submit": f"HARNESS_ROLE=writer {harness} submit {task_id}",
            "submit_and_wait": f"HARNESS_ROLE=writer {harness} submit {task_id} --wait",
            "status": f"{harness} status {task_id}",
        }
    if role == "reviewer":
        reviewer = shlex.quote(str(reviewer_id or "<reviewer-id>"))
        return {
            "review_approve": (
                f"HARNESS_ROLE=reviewer {harness} review {task_id} "
                f"--write-verdict {reviewer} approve"
            ),
            "review_block": (
                f"HARNESS_ROLE=reviewer {harness} review {task_id} --write-verdict {reviewer} block"
            ),
            "status": f"{harness} status {task_id}",
        }
    return {
        "dispatch": f"HARNESS_ROLE=integrator {harness} dispatch {task_id}",
        "gate": f"HARNESS_ROLE=integrator {harness} gate {task_id}",
        "land": f"HARNESS_ROLE=integrator {harness} land {task_id}",
        "push": f"HARNESS_ROLE=integrator {harness} push {task_id}",
        "status": f"{harness} status {task_id}",
    }


def _shell_command(path: Path, env: dict[str, str], agent_command: str) -> str:
    env_prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in env.items())
    return f"cd {shlex.quote(str(path))} && {env_prefix} {agent_command}"


def _agent_id(
    task_id: str,
    *,
    role: str,
    agent: str,
    reviewer_id: str | None,
    brief: str = "",
) -> str:
    suffix = reviewer_id if reviewer_id else task_id
    parts = [_safe_component(role), _safe_component(agent), _safe_component(suffix)]
    if role == "writer" and brief:
        parts.append(_safe_component(_delegation_hash_id(brief).split(":", 1)[1][:10]))
    return ".".join(parts)


def _delegation_hash_id(brief: str) -> str:
    return f"sha256:{sha256(brief.encode('utf-8')).hexdigest()}"


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    return cleaned.strip(".-") or "agent"


def _canonical_root(root: Path) -> Path:
    return common_dir(root).resolve().parent


def _harness_path(root: Path) -> Path:
    candidate = root / "harness"
    if candidate.is_file():
        return candidate
    return _PACKAGE_ROOT / "harness"

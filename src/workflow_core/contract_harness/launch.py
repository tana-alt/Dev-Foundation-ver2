from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.agent_tools import role_agent_skills, role_agent_tools
from workflow_core.contract_harness.context_audit import audit_context
from workflow_core.contract_harness.contract import ensure_prepared, load_contract
from workflow_core.contract_harness.gitutil import common_dir, git
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.runtime_paths import runtime_root, task_dir
from workflow_core.contract_harness.worktree import create_worktree

_MARKER = ".harness-worktree.json"
_PACKAGE_ROOT = Path(__file__).resolve().parents[3]


def writer_session(
    root: Path,
    task_id: str,
    *,
    agent_command: str = "codex --yolo",
) -> dict[str, Any]:
    ensure_prepared(root, task_id)
    canonical = _canonical_root(root)
    worktree = _writer_worktree(root, task_id)
    writer_path = Path(str(worktree["path"]))
    env = _writer_env(root, task_id)
    command = _shell_command(writer_path, env, agent_command)
    session = {
        "task_id": task_id,
        "status": "ready",
        "role": "writer",
        "cwd": str(writer_path),
        "command": command,
        "argv": shlex.split(agent_command),
        "env": env,
        "worktree": worktree,
        "initial_context": _initial_context(writer_path, task_id),
        "context_audit": audit_context(writer_path, task_id),
        "handoff": _handoff_commands(canonical, task_id),
    }
    write_json(task_dir(root, task_id) / "writer-session.json", session)
    return session


def _writer_worktree(root: Path, task_id: str) -> dict[str, Any]:
    canonical = _canonical_root(root)
    marker = root / _MARKER
    if marker.is_file():
        data = read_json(marker)
        if data.get("kind") == "writer" and data.get("task_id") == task_id:
            return _existing_writer_record(canonical, root, data, task_id)
    existing = runtime_root(canonical) / "worktrees" / task_id / "writer"
    marker = existing / _MARKER
    if marker.is_file():
        data = read_json(marker)
        if data.get("kind") == "writer" and data.get("task_id") == task_id:
            return _existing_writer_record(canonical, existing, data, task_id)
    return create_worktree(canonical, task_id, kind="writer")


def _existing_writer_record(
    canonical: Path,
    path: Path,
    marker: dict[str, Any],
    task_id: str,
) -> dict[str, Any]:
    if marker.get("source_repo_common_dir") != str(common_dir(canonical).resolve()):
        raise ValueError(f"refusing to reuse worktree with foreign marker: {path}")
    status = git(path, ["status", "--porcelain=v1"]).stdout.strip()
    record = {
        "task_id": task_id,
        "kind": "writer",
        "reviewer_id": None,
        "path": str(path),
        "base_ref": marker.get("base_ref"),
        "state": marker.get("state", "active"),
        "head_sha": git(path, ["rev-parse", "HEAD"]).stdout.strip(),
        "dirty": bool(status),
        "resume": True,
    }
    write_json(task_dir(canonical, task_id) / "writer-worktree.json", record)
    return record


def _writer_env(root: Path, task_id: str) -> dict[str, str]:
    return {
        "FOUNDATION_REPO_ROOT": str(_canonical_root(root)),
        "FOUNDATION_PROJECT_ID": task_id,
        "FOUNDATION_TASK_ID": task_id,
        "HARNESS_ROLE": "writer",
    }


def _canonical_root(root: Path) -> Path:
    return common_dir(root).resolve().parent


def _shell_command(path: Path, env: dict[str, str], agent_command: str) -> str:
    env_prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in env.items())
    return f"cd {shlex.quote(str(path))} && {env_prefix} {agent_command}"


def _handoff_commands(root: Path, task_id: str) -> dict[str, str]:
    harness = shlex.quote(str(_harness_path(root)))
    return {
        "verify": f"HARNESS_ROLE=writer {harness} verify {task_id}",
        "submit": f"HARNESS_ROLE=writer {harness} submit {task_id}",
        "submit_and_wait": f"HARNESS_ROLE=writer {harness} submit {task_id} --wait",
    }


def _harness_path(root: Path) -> Path:
    candidate = root / "harness"
    if candidate.is_file():
        return candidate
    return _PACKAGE_ROOT / "harness"


def _initial_context(root: Path, task_id: str) -> dict[str, Any]:
    contract = load_contract(root, task_id)
    return {
        "task_id": task_id,
        "scope_contract": contract["scope_contract"],
        "verifier_ids": [str(item.get("id", "")) for item in contract["verifier_plan"]],
        "agent_tools": role_agent_tools(root, task_id, "writer"),
        "agent_skills": role_agent_skills(root, "writer"),
    }

from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.config import harness_dir
from workflow_core.contract_harness.health import config_health
from workflow_core.contract_harness.jsonio import read_json
from workflow_core.contract_harness.runtime_paths import task_dir

_ARTIFACTS = (
    "contract.lock.json",
    "capsule.json",
    "verifier-plan.json",
    "writer-worktree.json",
    "verify-result.json",
    "submission.json",
    "gate-result.json",
    "integration-result.json",
    "land-result.json",
    "oracle-result.json",
    "push-result.json",
    "rework-request.json",
)


def task_status(root: Path, task_id: str) -> dict[str, Any]:
    runtime = task_dir(root, task_id)
    present = [name for name in _ARTIFACTS if (runtime / name).is_file()]
    missing = [name for name in _ARTIFACTS if name not in present]
    phase = _phase(root, task_id, runtime, present)
    authority = _authority(runtime)
    return {
        "schema_version": 1,
        "task_id": task_id,
        "phase": phase,
        "authority": authority,
        "artifacts": {
            "present": present,
            "missing": missing,
        },
        "health": config_health(root, task_id),
        "summary": _summary(phase, authority, present, missing),
        "written_by": "harness",
    }


def _phase(root: Path, task_id: str, runtime: Path, present: list[str]) -> str:
    terminal = _terminal_phase(runtime, present)
    if terminal is not None:
        return terminal
    pre_gate = _pre_gate_phase(present)
    if pre_gate is not None:
        return pre_gate
    if "contract.lock.json" in present:
        return "prepared"
    if (harness_dir(root) / "tasks" / task_id / "task.yaml").is_file():
        return "defined"
    return "unknown"


def _terminal_phase(runtime: Path, present: list[str]) -> str | None:
    if "push-result.json" in present:
        if _json_status(runtime, "push-result.json") == "pushed":
            return "pushed"
        return "push_attempted"
    if "rework-request.json" in present:
        return "rework_required"
    if "oracle-result.json" in present:
        return "oracle_retry"
    if "land-result.json" in present:
        if _json_status(runtime, "land-result.json") == "landed":
            return "landed"
        return "rework_required"
    if "integration-result.json" in present:
        if _json_status(runtime, "integration-result.json") == "integrated":
            return "integrated"
        return "rework_required"
    if "gate-result.json" in present:
        gate = read_json(runtime / "gate-result.json")
        return "integrated" if gate.get("mergeable") is True else "rework_required"
    return None


def _pre_gate_phase(present: list[str]) -> str | None:
    if "submission.json" in present:
        return "submitted"
    if "verify-result.json" in present:
        return "verified"
    if "writer-worktree.json" in present:
        return "writer_active"
    return None


def _authority(runtime: Path) -> dict[str, Any]:
    push_result = runtime / "push-result.json"
    if push_result.is_file():
        data = read_json(push_result)
        status = str(data.get("status") or "unknown")
        if status == "pushed":
            return {"complete": True, "source": "push-result.json status=pushed"}
        reason = str(data.get("reason") or "unknown")
        return {"complete": False, "source": f"push-result.json status={status} reason={reason}"}
    for name in ("gate-result.json", "land-result.json", "push-result.json"):
        if not (runtime / name).is_file():
            return {"complete": False, "source": f"missing {name}"}
    return {"complete": False, "source": "push-result.json is not pushed"}


def _summary(
    phase: str,
    authority: dict[str, Any],
    present: list[str],
    missing: list[str],
) -> str:
    present_text = ", ".join(present) if present else "no runtime artifacts"
    missing_text = ", ".join(missing) if missing else "no required artifacts missing"
    complete = "complete" if authority.get("complete") is True else "not complete"
    return f"phase={phase}; {complete}; present: {present_text}; missing: {missing_text}"


def _json_status(runtime: Path, name: str) -> str:
    return str(read_json(runtime / name).get("status") or "")

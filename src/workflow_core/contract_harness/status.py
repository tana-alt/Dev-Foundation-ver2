from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.application.services import latest_event_payload, state_summary
from workflow_core.contract_harness.config import harness_dir
from workflow_core.contract_harness.gitutil import git
from workflow_core.contract_harness.health import config_health
from workflow_core.contract_harness.jsonio import read_json
from workflow_core.contract_harness.roles import role_context
from workflow_core.contract_harness.runtime_paths import task_dir

_ARTIFACTS = (
    "contract.lock.json",
    "acceptance-proposal.json",
    "capsule.json",
    "resume-capsule.json",
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
    "bottleneck-events.json",
)

_NEXT_ACTIONS: dict[str, tuple[str, str | None, str]] = {
    "unknown": (
        "continue",
        "./harness prepare {task_id}",
        "task definition is ready for contract preparation",
    ),
    "defined": (
        "continue",
        "./harness prepare {task_id}",
        "task definition is ready for contract preparation",
    ),
    "prepared": (
        "continue",
        "HARNESS_ROLE=writer ./harness verify {task_id}",
        "candidate evidence has not been verified yet",
    ),
    "writer_active": (
        "continue",
        "HARNESS_ROLE=writer ./harness verify {task_id}",
        "candidate evidence has not been verified yet",
    ),
    "verified": (
        "continue",
        "HARNESS_ROLE=writer ./harness submit {task_id}",
        "verified candidate is ready for writer submission",
    ),
    "submitted": (
        "continue",
        "HARNESS_ROLE=integrator ./harness dispatch {task_id}",
        "submitted evidence is waiting for integrator dispatch",
    ),
    "integrated": (
        "continue",
        "HARNESS_ROLE=integrator ./harness land {task_id}",
        "candidate is gated but not landed",
    ),
    "landed": (
        "continue",
        "HARNESS_ROLE=integrator ./harness push {task_id}",
        "local land evidence exists and remote push is next if policy allows",
    ),
    "rework_required": (
        "rework",
        "HARNESS_ROLE=writer ./harness status {task_id}",
        "review, gate, or integration evidence requires writer rework",
    ),
    "oracle_retry": (
        "continue",
        "HARNESS_ROLE=integrator ./harness oracle {task_id} --target-head <sha>",
        "oracle retry evidence is required before integration can continue",
    ),
    "push_attempted": (
        "blocked",
        "HARNESS_ROLE=integrator ./harness push {task_id}",
        "previous push did not complete; inspect push-result.json first",
    ),
    "pushed": (
        "blocked",
        None,
        "push-result exists but authority is not complete",
    ),
}


def task_status(root: Path, task_id: str) -> dict[str, Any]:
    runtime = task_dir(root, task_id)
    present = [name for name in _ARTIFACTS if (runtime / name).is_file()]
    missing = [name for name in _ARTIFACTS if name not in present]
    phase = _phase(root, task_id, runtime, present)
    state_store = state_summary(root, task_id)
    authority = _authority(root, task_id, runtime, state_store)
    return {
        "schema_version": 1,
        "task_id": task_id,
        "phase": phase,
        "mode": "local-orchestration",
        "role": role_context(),
        "land_status": _land_status(phase, present),
        "next_action": next_action(task_id, phase, authority),
        "state_store": state_store,
        "authority": authority,
        "artifacts": {
            "present": present,
            "missing": missing,
        },
        "health": config_health(root, task_id),
        "summary": _summary(phase, authority, present, missing),
        "written_by": "harness",
    }


def next_action(task_id: str, phase: str, authority: dict[str, Any]) -> dict[str, str | None]:
    if authority.get("complete") is True:
        return {"status": "complete", "command": None, "reason": "task is complete"}
    template = _NEXT_ACTIONS.get(phase)
    if template is not None:
        status, command, reason = template
        return {
            "status": status,
            "command": None if command is None else command.format(task_id=task_id),
            "reason": reason,
        }
    return {
        "status": "blocked",
        "command": None,
        "reason": f"no next action is defined for phase={phase}",
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


def _land_status(phase: str, present: list[str]) -> str:
    if phase in {"pushed", "landed"}:
        return phase
    if phase == "integrated":
        return "not_landed"
    if "land-result.json" in present:
        return "land_attempted"
    return "not_ready"


def _authority(
    root: Path,
    task_id: str,
    runtime: Path,
    state_store: dict[str, Any],
) -> dict[str, Any]:
    if state_store.get("integrity") == "pass" and state_store.get("current_phase") == "complete":
        complete_payload = latest_event_payload(root, task_id, "COMPLETE")
        if complete_payload is not None and _complete_git_state_present(root, complete_payload):
            return {
                "complete": True,
                "source": "StateStore COMPLETE event + local merge commit",
            }
    push_result = runtime / "push-result.json"
    if push_result.is_file():
        data = read_json(push_result)
        status = str(data.get("status") or "unknown")
        if status == "pushed":
            complete_payload = latest_event_payload(root, task_id, "COMPLETE")
            if (
                state_store.get("integrity") == "pass"
                and state_store.get("current_phase") == "complete"
                and complete_payload is not None
                and _complete_git_state_present(root, complete_payload)
            ):
                return {
                    "complete": True,
                    "source": "StateStore COMPLETE event + push-result.json status=pushed",
                }
            return {
                "complete": False,
                "source": "push-result.json status=pushed without StateStore COMPLETE event",
            }
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


def _complete_git_state_present(root: Path, payload: dict[str, Any]) -> bool:
    landed = payload.get("landed_commit")
    remote_after = payload.get("remote_sha_after")
    shas = [str(item) for item in (landed, remote_after) if isinstance(item, str) and item]
    return bool(shas) and all(_commit_exists(root, sha) for sha in shas)


def _commit_exists(root: Path, sha: str) -> bool:
    if set(sha) == {"0"}:
        return False
    return git(root, ["cat-file", "-e", f"{sha}^{{commit}}"], check=False).returncode == 0

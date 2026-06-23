from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.agent_tools import role_agent_tools
from workflow_core.contract_harness.application.services import (
    candidate_id_from_patch_sha256,
    record_authority_artifact,
)
from workflow_core.contract_harness.command_runner import (
    command_result_artifact,
    env_timeout_s,
    run_command,
)
from workflow_core.contract_harness.contract import load_contract
from workflow_core.contract_harness.domain.models import WorkflowPhase
from workflow_core.contract_harness.evidence import artifact_hashes
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json, write_json_atomic
from workflow_core.contract_harness.mutation import run_handoff_mutation
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.verify import recompute_machine_evidence
from workflow_core.contract_harness.worktree import (
    create_worktree,
    resolve_candidate_workspace,
    seal_candidate_workspace,
)


def submit_task(
    root: Path,
    task_id: str,
    *,
    wait: bool = False,
    harness_bin: Path | None = None,
) -> tuple[dict[str, Any], int]:
    submission = build_submission(root, task_id)
    write_json_atomic(task_dir(root, task_id) / "submission.json", submission)
    record_authority_artifact(
        root,
        task_id,
        "submission.json",
        event_type="SUBMIT",
        to_phase=WorkflowPhase.SUBMITTED,
        payload={
            "candidate_diff_sha256": submission["candidate_diff_sha256"],
            "machine_evidence_sha256": submission["machine_evidence_sha256"],
            "base_sha": submission.get("base_sha"),
        },
        candidate_id=str(submission["candidate_id"]),
    )
    if wait:
        return wait_for_dispatch(root, task_id, harness_bin=harness_bin)
    return submission, 0


def submission_exists(root: Path, task_id: str) -> bool:
    return (task_dir(root, task_id) / "submission.json").is_file()


def validate_submission(root: Path, task_id: str) -> dict[str, Any]:
    submission = read_json(task_dir(root, task_id) / "submission.json")
    verify_result = _passed_verify_result(root, task_id)
    if not _matches_current_candidate(root, task_id, submission, verify_result):
        raise ValueError("stale_submission")
    return submission


def build_submission(root: Path, task_id: str) -> dict[str, Any]:
    verify_result = _passed_verify_result(root, task_id)
    candidate = task_dir(root, task_id) / "candidate.diff"
    if file_hash(candidate) != verify_result.get("candidate_diff_sha256"):
        raise ValueError("candidate hash mismatch")
    hashes = artifact_hashes(root, task_id)
    if hashes["quality_result_sha256"] != verify_result.get("quality_result_sha256"):
        raise ValueError("quality evidence mismatch")
    if hashes["tool_candidates_sha256"] != verify_result.get("tool_candidates_sha256"):
        raise ValueError("tool evidence mismatch")
    if hashes["scope_map_reverse_sha256"] != verify_result.get("scope_map_reverse_sha256"):
        raise ValueError("scope map evidence mismatch")
    mutation_result = run_handoff_mutation(root, task_id, verify_result)
    submission = {
        "schema_version": 1,
        "task_id": task_id,
        "candidate_id": candidate_id_from_patch_sha256(str(verify_result["candidate_diff_sha256"])),
        "status": "submitted",
        "base_sha": verify_result.get("base_sha"),
        "candidate_diff_sha256": verify_result["candidate_diff_sha256"],
        "machine_evidence_sha256": verify_result["machine_evidence_sha256"],
        "contract_semantic_sha256": verify_result["contract_semantic_sha256"],
        **hashes,
        "mutation_result_sha256": None,
        "mutation_status": "not_configured",
        "mutation_survivor_count": 0,
        "writer_handoff": _writer_handoff(root, task_id, verify_result),
        "written_by": "harness",
        "submitted_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if mutation_result is not None:
        submission["mutation_result_sha256"] = file_hash(
            task_dir(root, task_id) / "mutation-result.json"
        )
        submission["mutation_status"] = mutation_result["status"]
        submission["mutation_survivor_count"] = mutation_result["survivor_count"]
    submission["candidate_workspace"] = seal_candidate_workspace(
        root,
        task_id,
        str(verify_result["candidate_diff_sha256"]),
    )
    return submission


def wait_for_dispatch(
    root: Path,
    task_id: str,
    *,
    harness_bin: Path | None = None,
) -> tuple[dict[str, Any], int]:
    executable = harness_bin or Path("harness")
    dispatch_root, workspace = _dispatch_workspace(root, task_id)
    write_json(
        task_dir(root, task_id) / "integrator-handoff.json",
        {
            "task_id": task_id,
            "from_workspace": str(root),
            "integration_workspace": workspace,
            "written_by": "harness",
        },
    )
    completed = run_command(
        [str(executable), "dispatch", task_id],
        cwd=dispatch_root,
        timeout_s=env_timeout_s("FOUNDATION_GATE_TIMEOUT_S", 900),
        env={**os.environ, "HARNESS_ROLE": "integrator"},
    )
    _write_dispatch_result(root, task_id, completed)
    return _dispatch_result(completed)


def _writer_handoff(root: Path, task_id: str, verify_result: dict[str, Any]) -> dict[str, Any]:
    verifiers = [item for item in verify_result.get("verifiers", []) if isinstance(item, dict)]
    contract = load_contract(root, task_id)
    return {
        "task_id": task_id,
        "task_goal": contract.get("goal"),
        "scope_contract": contract["scope_contract"],
        "acceptance": _handoff_acceptance(contract.get("acceptance"), verify_result, verifiers),
        "verification": {
            "status": verify_result.get("status"),
            "candidate_diff_sha256": verify_result.get("candidate_diff_sha256"),
            "machine_evidence_sha256": verify_result.get("machine_evidence_sha256"),
            "passed_verifiers": [
                str(item.get("id")) for item in verifiers if item.get("status") == "pass"
            ],
            "failed_verifiers": [
                str(item.get("id")) for item in verifiers if item.get("status") != "pass"
            ],
        },
        "agent_tools": role_agent_tools(root, task_id, "writer"),
    }


def _handoff_acceptance(
    locked_acceptance: Any,
    verify_result: dict[str, Any],
    verifiers: list[dict[str, Any]],
) -> dict[str, Any]:
    locked = locked_acceptance if isinstance(locked_acceptance, dict) else {}
    payload: dict[str, Any] = {
        "mode": locked.get("mode", "generated"),
        "required_verifiers_passed": verify_result.get("status") == "pass",
        "verifier_ids": [str(item.get("id")) for item in verifiers],
    }
    audit = locked.get("audit")
    if isinstance(audit, dict) and "status" in audit:
        payload["audit_status"] = audit["status"]
    criteria = locked.get("criteria")
    if isinstance(criteria, list):
        payload["criteria_count"] = len(criteria)
    return payload


def _dispatch_workspace(root: Path, task_id: str) -> tuple[Path, dict[str, Any]]:
    marker = root / ".harness-worktree.json"
    if marker.is_file():
        data = read_json(marker)
        if data.get("kind") == "integrator" and data.get("task_id") == task_id:
            return root, {
                "task_id": task_id,
                "kind": "integrator",
                "path": str(root),
                "state": data.get("state", "active"),
            }
    workspace = create_worktree(root, task_id, kind="integrator")
    return Path(str(workspace["path"])), workspace


def _passed_verify_result(root: Path, task_id: str) -> dict[str, Any]:
    path = task_dir(root, task_id) / "verify-result.json"
    if not path.is_file():
        raise ValueError("verify-result.json is required before submit")
    verify_result = read_json(path)
    if verify_result.get("status") != "pass":
        raise ValueError("verify-result status must be pass")
    if verify_result.get("machine_evidence_sha256") != recompute_machine_evidence(verify_result):
        raise ValueError("machine evidence mismatch")
    return verify_result


def _matches_current_candidate(
    root: Path,
    task_id: str,
    submission: dict[str, Any],
    verify_result: dict[str, Any],
) -> bool:
    candidate = task_dir(root, task_id) / "candidate.diff"
    try:
        resolve_candidate_workspace(
            root,
            task_id,
            expected_hash=str(submission.get("candidate_diff_sha256")),
        )
    except (OSError, ValueError):
        return False
    return (
        submission.get("status") == "submitted"
        and submission.get("candidate_diff_sha256") == verify_result.get("candidate_diff_sha256")
        and submission.get("machine_evidence_sha256")
        == verify_result.get("machine_evidence_sha256")
        and file_hash(candidate) == submission.get("candidate_diff_sha256")
        and _matches_artifact_hashes(root, task_id, submission)
        and _matches_mutation_result(root, task_id, submission)
    )


def _matches_artifact_hashes(root: Path, task_id: str, submission: dict[str, Any]) -> bool:
    return all(
        submission.get(key) == value for key, value in artifact_hashes(root, task_id).items()
    )


def _matches_mutation_result(root: Path, task_id: str, submission: dict[str, Any]) -> bool:
    expected = submission.get("mutation_result_sha256")
    if expected is None:
        return True
    path = task_dir(root, task_id) / "mutation-result.json"
    return path.is_file() and file_hash(path) == expected


def _write_dispatch_result(root: Path, task_id: str, result: dict[str, Any]) -> None:
    write_json(
        task_dir(root, task_id) / "dispatch-result.json",
        {
            "task_id": task_id,
            "phase": "submit_wait_dispatch",
            **command_result_artifact(result),
            "written_by": "harness",
        },
    )


def _dispatch_result(completed: dict[str, Any]) -> tuple[dict[str, Any], int]:
    try:
        data = read_json_from_text(str(completed.get("stdout") or ""))
    except ValueError:
        data = {
            "ok": False,
            "reason": str(completed.get("stderr") or "").strip() or "dispatch_failed",
        }
    return data, int(completed["exit_code"])


def read_json_from_text(text: str) -> dict[str, Any]:
    import json

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("dispatch output must be a JSON object")
    return data

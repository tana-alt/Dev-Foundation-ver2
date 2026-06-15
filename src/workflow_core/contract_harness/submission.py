from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.agent_tools import role_agent_skills, role_agent_tools
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
        "task_id": task_id,
        "status": "submitted",
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
    completed = subprocess.run(
        [str(executable), "dispatch", task_id],
        cwd=dispatch_root,
        capture_output=True,
        text=True,
        timeout=int(os.environ.get("FOUNDATION_GATE_TIMEOUT_S", "900")),
        env={**os.environ, "HARNESS_ROLE": "integrator"},
    )
    return _dispatch_result(completed)


def _writer_handoff(root: Path, task_id: str, verify_result: dict[str, Any]) -> dict[str, Any]:
    verifiers = [item for item in verify_result.get("verifiers", []) if isinstance(item, dict)]
    return {
        "task_id": task_id,
        "acceptance": {
            "mode": "generated",
            "required_verifiers_passed": verify_result.get("status") == "pass",
            "verifier_ids": [str(item.get("id")) for item in verifiers],
        },
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
        "agent_skills": role_agent_skills(root, "writer"),
    }


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


def _dispatch_result(completed: subprocess.CompletedProcess[str]) -> tuple[dict[str, Any], int]:
    try:
        data = read_json_from_text(completed.stdout)
    except ValueError:
        data = {"ok": False, "reason": completed.stderr.strip() or "dispatch_failed"}
    return data, completed.returncode


def read_json_from_text(text: str) -> dict[str, Any]:
    import json

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("dispatch output must be a JSON object")
    return data

from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.command_runner import run_command
from workflow_core.contract_harness.hashing import hash_json


def run_verifiers(root: Path, plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for verifier in plan:
        results.append(_run_one(root, verifier))
    return results


def all_passed(results: list[dict[str, Any]]) -> bool:
    return all(result.get("status") == "pass" for result in results)


def machine_evidence_hash(
    *,
    task_id: str,
    candidate_diff_sha256: str,
    contract_semantic_sha256: str,
    scope_violation_count: int,
    verifiers: list[dict[str, Any]],
) -> str:
    evidence = {
        "task_id": task_id,
        "candidate_diff_sha256": candidate_diff_sha256,
        "contract_semantic_sha256": contract_semantic_sha256,
        "scope_violation_count": scope_violation_count,
        "verifiers": [
            {"id": str(item["id"]), "status": str(item["status"])}
            for item in sorted(verifiers, key=lambda row: str(row["id"]))
        ],
    }
    return hash_json(evidence)


def _run_one(root: Path, verifier: dict[str, Any]) -> dict[str, Any]:
    completed = run_command(
        str(verifier["command"]),
        cwd=root,
        shell=True,
        timeout_s=int(verifier.get("timeout_s", 900)),
    )
    return {
        "id": str(verifier["id"]),
        "status": "pass" if int(completed["exit_code"]) == 0 else "fail",
        "exit_code": completed["exit_code"],
        "duration_ms": completed["duration_ms"],
        "timed_out": completed["timed_out"],
    }

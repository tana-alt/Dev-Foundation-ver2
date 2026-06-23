from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.architecture_gate import canonical_architecture_gate
from workflow_core.contract_harness.command_runner import run_command
from workflow_core.contract_harness.hashing import hash_json, sha256_text


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
    architecture_gate: dict[str, Any] | None = None,
) -> str:
    evidence = {
        "task_id": task_id,
        "candidate_diff_sha256": candidate_diff_sha256,
        "contract_semantic_sha256": contract_semantic_sha256,
        "scope_violation_count": scope_violation_count,
        "architecture_gate": canonical_architecture_gate(architecture_gate),
        "verifiers": [
            {
                "id": str(item["id"]),
                "status": str(item["status"]),
                "command": item.get("command"),
                "command_display": item.get("command_display"),
                "shell": item.get("shell"),
                "timeout_s": item.get("timeout_s"),
                "exit_code": item.get("exit_code"),
                "timed_out": item.get("timed_out"),
                "stdout_sha256": item.get("stdout_sha256"),
                "stderr_sha256": item.get("stderr_sha256"),
            }
            for item in sorted(verifiers, key=lambda row: str(row["id"]))
        ],
    }
    return hash_json(evidence)


def _run_one(root: Path, verifier: dict[str, Any]) -> dict[str, Any]:
    command = verifier["command"]
    shell = bool(verifier.get("shell", isinstance(command, str)))
    timeout_s = int(verifier.get("timeout_s", 900))
    runnable_command = _runnable_command(command, shell=shell)
    completed = run_command(
        runnable_command,
        cwd=root,
        shell=shell,
        timeout_s=timeout_s,
    )
    return {
        "id": str(verifier["id"]),
        "status": "pass" if int(completed["exit_code"]) == 0 else "fail",
        "command": completed["command"],
        "command_display": completed["command_display"],
        "shell": shell,
        "timeout_s": timeout_s,
        "exit_code": completed["exit_code"],
        "duration_ms": completed["duration_ms"],
        "timed_out": completed["timed_out"],
        "stdout_sha256": sha256_text(str(completed.get("stdout", ""))),
        "stderr_sha256": sha256_text(str(completed.get("stderr", ""))),
        "stdout_tail": completed["stdout_tail"],
        "stderr_tail": completed["stderr_tail"],
    }


def _runnable_command(command: object, *, shell: bool) -> str | list[str]:
    if isinstance(command, str):
        return command
    parts = [str(part) for part in command] if isinstance(command, list) else [str(command)]
    if shell:
        return " ".join(shlex.quote(part) for part in parts)
    return parts

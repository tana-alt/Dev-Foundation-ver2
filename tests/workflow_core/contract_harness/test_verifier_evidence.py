from __future__ import annotations

from pathlib import Path

from workflow_core.contract_harness.config import verifier_plan
from workflow_core.contract_harness.verifier import machine_evidence_hash, run_verifiers


def test_verifier_plan_preserves_argv_command_and_shell_opt_in() -> None:
    plan = verifier_plan(
        {
            "default": [
                {
                    "id": "unit",
                    "command": ["python", "-c", "raise SystemExit(0)"],
                    "shell": False,
                    "timeout_s": 30,
                }
            ]
        },
        "demo",
    )

    assert plan == [
        {
            "id": "unit",
            "command": ["python", "-c", "raise SystemExit(0)"],
            "applies_to": ["**/*"],
            "always": True,
            "shell": False,
            "timeout_s": 30,
        }
    ]


def test_machine_evidence_hash_changes_for_command_exit_and_output(tmp_path: Path) -> None:
    results = run_verifiers(
        tmp_path,
        [
            {
                "id": "unit",
                "command": ["python", "-c", "print('one')"],
                "shell": False,
            }
        ],
    )

    verifier = results[0]
    assert verifier["status"] == "pass"
    assert verifier["command"] == ["python", "-c", "print('one')"]
    assert verifier["shell"] is False
    assert verifier["exit_code"] == 0
    assert verifier["stdout_sha256"].startswith("sha256:")
    assert verifier["stderr_sha256"].startswith("sha256:")

    base = _evidence_hash(results)
    changed_output = [{**verifier, "stdout_sha256": "sha256:" + "0" * 64}]
    changed_exit = [{**verifier, "exit_code": 1}]
    changed_command = [{**verifier, "command": ["python", "-c", "print('two')"]}]
    changed_shell = [{**verifier, "shell": True}]
    changed_timeout = [{**verifier, "timeout_s": 1}]

    assert _evidence_hash(changed_output) != base
    assert _evidence_hash(changed_exit) != base
    assert _evidence_hash(changed_command) != base
    assert _evidence_hash(changed_shell) != base
    assert _evidence_hash(changed_timeout) != base


def _evidence_hash(verifiers: list[dict[str, object]]) -> str:
    return machine_evidence_hash(
        task_id="T-0001",
        candidate_diff_sha256="sha256:" + "a" * 64,
        contract_semantic_sha256="sha256:" + "b" * 64,
        scope_violation_count=0,
        verifiers=verifiers,
        architecture_gate={"status": "pass", "findings": []},
    )

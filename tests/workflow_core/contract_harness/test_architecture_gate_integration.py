from __future__ import annotations

import json
from pathlib import Path

from workflow_core.contract_harness.verify import recompute_machine_evidence

from .conftest import TASK_ID, git, load_runtime_json, run_harness, runtime_task_dir


def test_verify_result_includes_architecture_gate(harness_repo: Path) -> None:
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    result = run_harness(harness_repo, "verify", TASK_ID)

    assert result.returncode == 0, result.stdout + result.stderr
    verify_result = load_runtime_json(harness_repo, "verify-result.json")
    gate = verify_result["architecture_gate"]
    assert gate["status"] == "pass"
    assert gate["predicate_version"] == "architecture-gate/v1"
    assert verify_result["machine_evidence_sha256"] == recompute_machine_evidence(verify_result)


def test_verify_fails_when_architecture_gate_blocks(harness_repo: Path) -> None:
    doc = harness_repo / "docs" / "04-system-design-contract.md"
    doc.parent.mkdir()
    doc.write_text("new active doc\n", encoding="utf-8")

    result = run_harness(harness_repo, "verify", TASK_ID)

    assert result.returncode != 0
    verify_result = load_runtime_json(harness_repo, "verify-result.json")
    assert verify_result["status"] == "fail"
    assert verify_result["architecture_gate"]["status"] == "block"
    assert verify_result["architecture_gate"]["reason_codes"] == ["ACTIVE_DOC_EXPANSION"]


def test_gate_recomputes_architecture_gate(harness_repo: Path) -> None:
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0

    path = runtime_task_dir(harness_repo) / "verify-result.json"
    verify_result = json.loads(path.read_text(encoding="utf-8"))
    verify_result["architecture_gate"]["status"] = "advisory"
    verify_result["architecture_gate"]["advisory_codes"] = ["ROUTING_OR_CONTEXT_BOUNDARY_CHANGED"]
    path.write_text(json.dumps(verify_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    gate = run_harness(harness_repo, "gate", TASK_ID, role="integrator")

    assert gate.returncode != 0
    assert json.loads(gate.stdout)["reason"] == "architecture_gate_mismatch"


def test_architecture_advisory_requires_executed_verifier(harness_repo: Path) -> None:
    # The advisory path should be able to pass when the existing verifier plan
    # has run and produced machine evidence. This keeps scope-map-reverse out
    # of the authority path.
    target = harness_repo / "src" / "workflow_core" / "contract_harness"
    target.mkdir(parents=True)
    (target / "agent_tools.py").write_text("ROUTING_CHANGE = True\n", encoding="utf-8")

    result = run_harness(harness_repo, "verify", TASK_ID)

    assert result.returncode == 0, result.stdout + result.stderr
    verify_result = load_runtime_json(harness_repo, "verify-result.json")
    assert verify_result["architecture_gate"]["status"] == "advisory"
    assert verify_result["architecture_gate"]["oracle_requirements"] == [
        "T_UNION_COVERS_BEHAVIORAL_BOUNDARY"
    ]


def test_task_yaml_architecture_significance_is_ignored(harness_repo: Path) -> None:
    task = harness_repo / ".harness" / "tasks" / TASK_ID / "task.yaml"
    task.write_text(
        task.read_text(encoding="utf-8")
        + "design_gate:\n"
        + "  architecture_significance: significant\n",
        encoding="utf-8",
    )
    git(harness_repo, "add", ".harness/tasks/T-0001/task.yaml")
    git(harness_repo, "commit", "-m", "self report significance")
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    result = run_harness(harness_repo, "verify", TASK_ID)

    assert result.returncode == 0, result.stdout + result.stderr
    verify_result = load_runtime_json(harness_repo, "verify-result.json")
    assert verify_result["architecture_gate"]["derived_significance"] == "none"

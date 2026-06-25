from __future__ import annotations

import json
from pathlib import Path

from .conftest import TASK_ID, git, load_runtime_json, run_harness


def write_policy(repo: Path) -> None:
    policy_dir = repo / ".harness" / "policies"
    policy_dir.mkdir()
    (policy_dir / "bottleneck-reduction.yaml").write_text(
        "id: bottleneck-reduction\n"
        "goal: reduce harness bottlenecks\n"
        "invariants:\n"
        "  - id: no_silent_block\n"
        "    statement: stops are recorded\n"
        "  - id: proof_required\n"
        "    statement: completion requires proof\n"
        "acceptance_requirements:\n"
        "  - every_criterion_has_proof\n"
        "  - policy_invariants_are_mapped\n"
        "verifiers:\n"
        "  required:\n"
        "    - unit\n"
        "metrics:\n"
        "  - acceptance_audit_failure_count\n",
        encoding="utf-8",
    )


def test_agent_generated_acceptance_is_audited_and_locked(harness_repo: Path) -> None:
    write_policy(harness_repo)
    (harness_repo / ".harness" / "tasks" / TASK_ID / "task.yaml").write_text(
        f"id: {TASK_ID}\n"
        "policy: bottleneck-reduction\n"
        "scope: demo\n"
        "base: main\n"
        "goal: Generate a resume capsule from runtime state\n"
        "acceptance:\n"
        "  mode: agent_generated\n"
        "  criteria:\n"
        "    - id: AC-1\n"
        "      statement: stops are recorded\n"
        "      policy_refs:\n"
        "        - no_silent_block\n"
        "      proof:\n"
        "        kind: test\n"
        "        command: python -c 'raise SystemExit(0)'\n"
        "    - id: AC-2\n"
        "      statement: completion has proof\n"
        "      policy_refs:\n"
        "        - proof_required\n"
        "      proof:\n"
        "        kind: test\n"
        "        command: python -c 'raise SystemExit(0)'\n",
        encoding="utf-8",
    )
    git(
        harness_repo,
        "add",
        ".harness/policies/bottleneck-reduction.yaml",
        f".harness/tasks/{TASK_ID}/task.yaml",
    )
    git(harness_repo, "commit", "-m", "configure policy acceptance")

    prepared = run_harness(harness_repo, "prepare", TASK_ID)

    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    contract = load_runtime_json(harness_repo, "contract.lock.json")
    assert contract["policy"]["id"] == "bottleneck-reduction"
    assert contract["acceptance"]["audit"]["status"] == "pass"
    assert contract["acceptance"]["mode"] == "agent_generated"
    proposal = load_runtime_json(harness_repo, "acceptance-proposal.json")
    assert proposal["criteria"][0]["id"] == "AC-1"
    capsule = load_runtime_json(harness_repo, "resume-capsule.json")
    assert capsule["task_id"] == TASK_ID
    assert capsule["locked_acceptance"]["audit"]["status"] == "pass"
    spawned = run_harness(harness_repo, "spawn", TASK_ID, "--role", "writer", "--agent", "codex")
    assert spawned.returncode == 0, spawned.stdout + spawned.stderr
    initial_context = json.loads(spawned.stdout)["initial_context"]
    assert initial_context["policy"]["policy_id"] == "bottleneck-reduction"
    assert initial_context["acceptance"]["audit_status"] == "pass"
    assert initial_context["acceptance"]["mode"] == "agent_generated"
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    verified = run_harness(harness_repo, "verify", TASK_ID)
    assert verified.returncode == 0, verified.stdout + verified.stderr
    submitted = run_harness(harness_repo, "submit", TASK_ID)
    assert submitted.returncode == 0, submitted.stdout + submitted.stderr
    submission = load_runtime_json(harness_repo, "submission.json")
    assert submission["writer_handoff"]["acceptance"]["mode"] == "agent_generated"
    assert submission["writer_handoff"]["acceptance"]["audit_status"] == "pass"


def test_project_layout_task_uses_project_policy(harness_repo: Path) -> None:
    task_id = "PROJECT-TASK"
    project = harness_repo / ".harness" / "demo-project"
    (project / "tasks" / task_id).mkdir(parents=True)
    (project / "policy.yaml").write_text(
        "id: demo-project\n"
        "goal: keep demo project artifacts together\n"
        "invariants:\n"
        "  - id: evidence_locality\n"
        "    statement: task evidence belongs under the project task directory\n",
        encoding="utf-8",
    )
    (project / "tasks" / task_id / "task.yaml").write_text(
        f"id: {task_id}\n"
        "scope: demo\n"
        "base: main\n"
        "goal: prove project layout task lookup\n"
        "acceptance:\n"
        "  mode: generated\n",
        encoding="utf-8",
    )
    git(harness_repo, "add", ".harness/demo-project")
    git(harness_repo, "commit", "-m", "add project layout task")

    prepared = run_harness(harness_repo, "prepare", task_id)

    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    contract = load_runtime_json(harness_repo, "contract.lock.json", task_id)
    assert contract["policy"]["id"] == "demo-project"
    assert contract["policy"]["path"] == ".harness/demo-project/policy.yaml"
    assert "demo-project/policy.yaml" in contract["input_hashes"]
    assert f"demo-project/tasks/{task_id}/task.yaml" in contract["input_hashes"]

    worktree = run_harness(harness_repo, "worktree", task_id, "--writer", role="integrator")
    assert worktree.returncode == 0, worktree.stdout + worktree.stderr
    writer_path = Path(json.loads(worktree.stdout)["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    verified = run_harness(writer_path, "verify", task_id)
    assert verified.returncode == 0, verified.stdout + verified.stderr


def test_weak_agent_generated_acceptance_records_rework_bottleneck(harness_repo: Path) -> None:
    write_policy(harness_repo)
    (harness_repo / ".harness" / "tasks" / TASK_ID / "task.yaml").write_text(
        f"id: {TASK_ID}\n"
        "policy: bottleneck-reduction\n"
        "scope: demo\n"
        "base: main\n"
        "goal: Generate a resume capsule from runtime state\n"
        "acceptance:\n"
        "  mode: agent_generated\n"
        "  criteria:\n"
        "    - id: AC-1\n"
        "      statement: stops are recorded\n"
        "      policy_refs:\n"
        "        - no_silent_block\n",
        encoding="utf-8",
    )

    prepared = run_harness(harness_repo, "prepare", TASK_ID)

    assert prepared.returncode == 1
    result = json.loads(prepared.stdout)
    assert result["status"] == "rework_required"
    assert result["reason"] == "acceptance_audit_failed"
    rework = load_runtime_json(harness_repo, "rework-request.json")
    assert rework["reason"] == "acceptance_audit_failed"
    bottlenecks = load_runtime_json(harness_repo, "bottleneck-events.json")
    assert bottlenecks["events"][0]["phase"] == "acceptance.audit"
    assert bottlenecks["events"][0]["status"] == "rework_required"
    capsule = load_runtime_json(harness_repo, "resume-capsule.json")
    assert capsule["current_phase"] == "rework_required"
    assert capsule["unresolved"]["reason"] == "acceptance_audit_failed"
    assert capsule["latest_evidence"][0]["type"] == "bottleneck_event"


def test_agent_generated_acceptance_rejects_invalid_proof_command(
    harness_repo: Path,
) -> None:
    write_policy(harness_repo)
    (harness_repo / ".harness" / "tasks" / TASK_ID / "task.yaml").write_text(
        f"id: {TASK_ID}\n"
        "policy: bottleneck-reduction\n"
        "scope: demo\n"
        "base: main\n"
        "goal: Generate a resume capsule from runtime state\n"
        "acceptance:\n"
        "  mode: agent_generated\n"
        "  criteria:\n"
        "    - id: AC-1\n"
        "      statement: stops are recorded\n"
        "      policy_refs:\n"
        "        - no_silent_block\n"
        "      proof:\n"
        "        kind: test\n"
        "        command: does-not-exist --run\n"
        "    - id: AC-2\n"
        "      statement: completion has proof\n"
        "      policy_refs:\n"
        "        - proof_required\n"
        "      proof:\n"
        "        kind: test\n"
        "        command: python -c 'raise SystemExit(0)'\n",
        encoding="utf-8",
    )

    prepared = run_harness(harness_repo, "prepare", TASK_ID)

    assert prepared.returncode == 1
    result = json.loads(prepared.stdout)
    codes = {finding["code"] for finding in result["audit"]["findings"]}
    assert "invalid_proof_command" in codes


def test_agent_generated_acceptance_requires_explicit_human_gates(
    harness_repo: Path,
) -> None:
    policy_dir = harness_repo / ".harness" / "policies"
    policy_dir.mkdir()
    (policy_dir / "gated.yaml").write_text(
        "id: gated\n"
        "goal: make protected actions explicit\n"
        "invariants:\n"
        "  - id: proof_required\n"
        "    statement: completion requires proof\n"
        "acceptance_requirements:\n"
        "  - every_criterion_has_proof\n"
        "  - policy_invariants_are_mapped\n"
        "  - human_gates_are_explicit\n"
        "human_gates:\n"
        "  - external_write\n",
        encoding="utf-8",
    )
    (harness_repo / ".harness" / "tasks" / TASK_ID / "task.yaml").write_text(
        f"id: {TASK_ID}\n"
        "policy: gated\n"
        "scope: demo\n"
        "base: main\n"
        "goal: Generate a resume capsule from runtime state\n"
        "acceptance:\n"
        "  mode: agent_generated\n"
        "  criteria:\n"
        "    - id: AC-1\n"
        "      statement: completion has proof\n"
        "      policy_refs:\n"
        "        - proof_required\n"
        "      proof:\n"
        "        kind: test\n"
        "        command: python -c 'raise SystemExit(0)'\n",
        encoding="utf-8",
    )

    prepared = run_harness(harness_repo, "prepare", TASK_ID)

    assert prepared.returncode == 1
    result = json.loads(prepared.stdout)
    codes = {finding["code"] for finding in result["audit"]["findings"]}
    assert "missing_human_gates" in codes

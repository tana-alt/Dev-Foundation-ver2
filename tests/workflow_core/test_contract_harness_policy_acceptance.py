from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from workflow_core.contract_harness.config import ConfigError

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "harness"
TASK_ID = "T-0001"


def git(
    repo: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=check,
    )


def init_policy_repo(tmp_path: Path, *, policy_text: str | None = None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    harness = repo / ".harness"
    (harness / "tasks" / TASK_ID).mkdir(parents=True)
    (harness / "rfc-decisions").mkdir()
    (harness / "bottleneck.yaml").write_text("version: 1\n", encoding="utf-8")
    (harness / "policy.yaml").write_text(policy_text or policy_yaml(), encoding="utf-8")
    (harness / "owners.yaml").write_text(
        "scopes:\n  demo:\n    allowed_paths:\n      - src/**\n",
        encoding="utf-8",
    )
    (harness / "verifiers.yaml").write_text(
        "default:\n"
        "  - id: unit\n"
        "    command: python -c 'raise SystemExit(0)'\n"
        "    applies_to: ['**/*']\n"
        "    always: true\n",
        encoding="utf-8",
    )
    (harness / "review.yaml").write_text(
        "default:\n  quorum: 2\n  reviewers:\n    - reader-correctness\n    - reader-scope\n",
        encoding="utf-8",
    )
    (harness / "tasks" / TASK_ID / "task.yaml").write_text(
        f"id: {TASK_ID}\n"
        "scope: demo\n"
        "base: main\n"
        "intent:\n"
        "  kind: implementation\n"
        "  summary: policy acceptance\n"
        "acceptance:\n"
        "  mode: generated\n"
        "allowed_outputs:\n"
        "  - source_diff\n",
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    (repo / "src" / "app.txt").write_text("base\n", encoding="utf-8")
    (repo / "Makefile").write_text("check-required:\n\t@true\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    return repo


def policy_yaml(*, push_mode: str = "dry_run", extra: str = "") -> str:
    return (
        "version: 1\n"
        "goal:\n"
        "  summary: safe serialized integration for contract harness tasks\n"
        "constraints:\n"
        "  runtime_state:\n"
        "    must_use_git_common_dir: true\n"
        "    forbidden_tracked_paths:\n"
        "      - .harness/state/**\n"
        "  integration_target:\n"
        "    remote: origin\n"
        "    branch: main\n"
        "  external_writes:\n"
        "    default_mode: dry_run\n"
        "    allowed_roles:\n"
        "      - integrator\n"
        "    remotes:\n"
        "      origin:\n"
        "        branches:\n"
        "          main:\n"
        f"            mode: {push_mode}\n"
        "            require_rescue_ref: true\n"
        "            require_push_lock: true\n"
        "            require_local_sync_after_remote_update: true\n"
        "authority:\n"
        "  source: .harness/policy.yaml\n"
        "  missing_required_yaml_information: rework\n"
        "  format_variance: tolerated\n"
        "context_model:\n"
        "  contract_sources:\n"
        "    global_policy: .harness/policy.yaml\n"
        "    task_contract: .harness/tasks/<task_id>/task.yaml\n"
        "    operational_protocols: AGENTS.md\n"
        "    optional_references: docs/reference/**\n"
        "architecture:\n"
        "  repo_wide_invariants:\n"
        "    - id: ARCH-CONTROL-PLANE-TRACKED\n"
        "      statement: .harness policy/task files are tracked control-plane configuration.\n"
        "scope_policy:\n"
        "  allowed_paths:\n"
        "    semantics: expected_impact_area\n"
        "    hard_gate: false\n"
        "  forbidden_paths:\n"
        "    semantics: blocked_area\n"
        "    hard_gate: true\n"
        "task_contract:\n"
        "  missing_required_information_result: rework\n"
        "  format_policy:\n"
        "    strict_schema_required: false\n"
        "review:\n"
        "  default_posture: adversarial_counterexample_search\n"
        "  stages:\n"
        "    architecture_review:\n"
        "      timing: before_or_early_implementation\n"
        "    code_review:\n"
        "      timing: after_implementation\n"
        "bottlenecks:\n"
        "  integration:\n"
        "    max_active_integrators_per_branch: 1\n"
        "    lock_timeout_s: 900\n"
        "metrics:\n"
        "  observe:\n"
        "    - rework_rate\n"
        "    - stale_submission_rate\n"
        "    - lock_contention_rate\n"
        "    - local_sync_required_rate\n"
        f"{extra}"
    )


def add_bare_remote(tmp_path: Path, repo: Path) -> Path:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    return remote


def test_policy_yaml_is_repo_wide_goal_constraints_and_scope_semantics(tmp_path: Path) -> None:
    repo = init_policy_repo(tmp_path)

    from workflow_core.contract_harness.policy import load_policy

    policy = load_policy(repo)
    assert policy["goal"]["summary"] == "safe serialized integration for contract harness tasks"
    assert "constraints" in policy
    assert "bottlenecks" in policy
    assert policy["authority"]["missing_required_yaml_information"] == "rework"
    assert policy["task_contract"]["missing_required_information_result"] == "rework"
    assert policy["task_contract"]["format_policy"]["strict_schema_required"] is False
    assert policy["scope_policy"]["allowed_paths"]["hard_gate"] is False
    assert policy["scope_policy"]["allowed_paths"]["semantics"] == "expected_impact_area"
    assert policy["scope_policy"]["forbidden_paths"]["hard_gate"] is True
    assert policy["scope_policy"]["forbidden_paths"]["semantics"] == "blocked_area"
    assert set(policy["review"]["stages"]) == {"architecture_review", "code_review"}
    assert "scope" not in policy


def test_policy_yaml_rejects_task_specific_scope_key(tmp_path: Path) -> None:
    repo = init_policy_repo(tmp_path, policy_text=policy_yaml(extra="scope: demo\n"))

    from workflow_core.contract_harness.policy import load_policy

    with pytest.raises(ConfigError, match="policy.yaml must not define task-specific scope"):
        load_policy(repo)


def test_active_harness_control_plane_files_are_git_tracked() -> None:
    result = subprocess.run(
        ["git", "ls-files", ".harness"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    tracked = set(result.stdout.splitlines())

    assert {
        ".harness/bottleneck.yaml",
        ".harness/owners.yaml",
        ".harness/policy.yaml",
        ".harness/review.yaml",
        ".harness/semantic_ai_reviewer.py",
        ".harness/tasks/p0-policy-task-contract-refinement/task.yaml",
        ".harness/verifiers.yaml",
    } <= tracked
    assert not any(path.startswith(".harness/state/") for path in tracked)
    assert not any(path.startswith(".harness/proposals/") for path in tracked)


def test_plan_n0003_saved_under_plan_harness_review_plans() -> None:
    plan = ROOT / "Plan" / "harness-review" / "plans" / "Plan_N0003.md"

    assert plan.is_file()
    assert "Harness Authority" in plan.read_text(encoding="utf-8")


def test_policy_oracle_retry_defaults_to_zero_until_enabled(tmp_path: Path) -> None:
    repo = init_policy_repo(tmp_path)

    from workflow_core.contract_harness.policy import (
        load_policy,
        max_remote_changed_retries,
        oracle_timeout_s,
    )

    policy = load_policy(repo)
    assert max_remote_changed_retries(policy) == 0
    assert oracle_timeout_s(policy) == 900

    enabled_root = tmp_path / "enabled"
    enabled_root.mkdir()
    enabled_policy = policy_yaml().replace(
        "    lock_timeout_s: 900\n",
        ("    lock_timeout_s: 900\n    max_remote_changed_retries: 2\n    oracle_timeout_s: 123\n"),
    )
    enabled = load_policy(
        init_policy_repo(
            enabled_root,
            policy_text=enabled_policy,
        )
    )
    assert max_remote_changed_retries(enabled) == 2
    assert oracle_timeout_s(enabled) == 123


def test_runtime_root_rejects_tracked_harness_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_policy_repo(tmp_path)
    monkeypatch.setenv("HARNESS_RUNTIME_ROOT", str(repo / ".harness" / "state"))

    from workflow_core.contract_harness.runtime_paths import runtime_root

    with pytest.raises(ConfigError, match=r"\.harness/state"):
        runtime_root(repo)


def test_runtime_artifacts_never_written_under_tracked_harness_state(tmp_path: Path) -> None:
    repo = init_policy_repo(tmp_path)
    prepared = subprocess.run(
        [str(HARNESS), "prepare", TASK_ID],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HARNESS_ROLE": "writer"},
    )

    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    common = git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    runtime = repo / common if not Path(common).is_absolute() else Path(common)
    assert (runtime / "harness-runtime" / "state" / "tasks" / TASK_ID).is_dir()
    assert not (repo / ".harness" / "state").exists()


def test_prepare_locks_global_policy_yaml_as_contract_source(tmp_path: Path) -> None:
    repo = init_policy_repo(tmp_path)

    prepared = subprocess.run(
        [str(HARNESS), "prepare", TASK_ID],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "HARNESS_ROLE": "writer"},
    )

    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    common = git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    runtime = repo / common if not Path(common).is_absolute() else Path(common)
    contract_path = runtime / "harness-runtime" / "state" / "tasks" / TASK_ID / "contract.lock.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert "policy.yaml" in contract["input_hashes"]
    assert ".harness/policy.yaml" not in contract["scope_contract"]["forbidden_paths"]


def test_external_write_decision_blocks_non_integrator_and_dry_run(
    tmp_path: Path,
) -> None:
    repo = init_policy_repo(tmp_path)

    from workflow_core.contract_harness.policy import decide_external_write, load_policy

    policy = load_policy(repo)
    writer = decide_external_write(
        policy,
        role="writer",
        remote="origin",
        branch="main",
        action="push_landed_commit",
    )
    assert writer["ok"] is False
    assert writer["reason"] == "protected_external_write"
    assert writer["completed"] is False

    integrator = decide_external_write(
        policy,
        role="integrator",
        remote="origin",
        branch="main",
        action="push_landed_commit",
    )
    assert integrator["ok"] is False
    assert integrator["reason"] == "protected_external_write"
    assert integrator["mode"] == "dry_run"
    assert integrator["completed"] is False


def test_integration_target_uses_explicit_policy_not_sorted_first(tmp_path: Path) -> None:
    policy_text = policy_yaml().replace(
        "      origin:\n",
        "      aaa:\n"
        "        branches:\n"
        "          release:\n"
        "            mode: enabled\n"
        "      origin:\n",
    )
    repo = init_policy_repo(tmp_path, policy_text=policy_text)

    from workflow_core.contract_harness.policy import integration_target, load_policy

    remote, branch, branch_policy = integration_target(load_policy(repo))

    assert remote == "origin"
    assert branch == "main"
    assert branch_policy["require_local_sync_after_remote_update"] is True


def test_integration_target_requires_explicit_policy_schema(tmp_path: Path) -> None:
    policy_text = policy_yaml().replace(
        "  integration_target:\n    remote: origin\n    branch: main\n",
        "",
    )
    repo = init_policy_repo(tmp_path, policy_text=policy_text)

    from workflow_core.contract_harness.policy import integration_target, load_policy

    with pytest.raises(ConfigError, match=r"constraints\.integration_target"):
        integration_target(load_policy(repo))


def test_remote_update_sync_fast_forwards_local_branch(tmp_path: Path) -> None:
    repo = init_policy_repo(tmp_path)
    remote = add_bare_remote(tmp_path, repo)
    other = tmp_path / "other"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "app.txt").write_text("remote update\n", encoding="utf-8")
    git(other, "commit", "-am", "remote update")
    git(other, "push", "origin", "main")
    expected_sha = git(other, "rev-parse", "HEAD").stdout.strip()
    assert git(repo, "rev-parse", "main").stdout.strip() != expected_sha

    from workflow_core.contract_harness.sync import sync_local_target_branch

    result: dict[str, Any] = sync_local_target_branch(
        repo,
        task_id=TASK_ID,
        remote="origin",
        branch="main",
        expected_sha=expected_sha,
        env={**os.environ, "HARNESS_ROLE": "integrator"},
    )

    assert result["status"] == "local_synced"
    assert result["remote_sha"] == expected_sha
    assert result["final_local_sha"] == expected_sha
    assert git(repo, "rev-parse", "main").stdout.strip() == expected_sha

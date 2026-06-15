from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from workflow_core.contract_harness.config import ConfigError

ROOT = Path(__file__).resolve().parents[2]
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
    return remote


def test_policy_yaml_is_shared_goal_constraints_and_not_scope(tmp_path: Path) -> None:
    repo = init_policy_repo(tmp_path)

    from workflow_core.contract_harness.policy import load_policy

    policy = load_policy(repo)
    assert policy["goal"]["summary"] == "safe serialized integration for contract harness tasks"
    assert "constraints" in policy
    assert "bottlenecks" in policy
    assert "scope" not in policy
    assert "allowed_paths" not in policy
    assert "forbidden_paths" not in policy


def test_policy_yaml_rejects_scope_keys(tmp_path: Path) -> None:
    repo = init_policy_repo(tmp_path, policy_text=policy_yaml(extra="scope: demo\n"))

    from workflow_core.contract_harness.policy import load_policy

    with pytest.raises(ConfigError, match="policy.yaml must not define scope"):
        load_policy(repo)


def test_runtime_root_rejects_tracked_harness_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_policy_repo(tmp_path)
    monkeypatch.setenv("HARNESS_RUNTIME_ROOT", str(repo / ".harness" / "state"))

    from workflow_core.contract_harness.runtime_paths import runtime_root

    with pytest.raises(ConfigError, match=r"\.harness/state"):
        runtime_root(repo)


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

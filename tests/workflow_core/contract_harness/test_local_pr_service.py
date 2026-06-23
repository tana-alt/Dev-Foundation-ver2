from __future__ import annotations

import json
from pathlib import Path

from .conftest import TASK_ID, git, load_runtime_json, run_harness


def add_remote(repo: Path, tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    return remote


def test_local_pr_ref_binds_to_candidate_hash(harness_repo: Path) -> None:
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0

    created = run_harness(harness_repo, "pr", "create", TASK_ID, role="integrator")

    assert created.returncode == 0, created.stdout + created.stderr
    result = json.loads(created.stdout)
    assert result["status"] == "created"
    assert result["ref"].startswith(f"refs/harness/pr/{TASK_ID}/cand_")
    assert not result["ref"].startswith("refs/foundation/pr/")
    assert git(harness_repo, "rev-parse", "--verify", result["ref"]).returncode == 0

    pr_result = load_runtime_json(harness_repo, "pr-result.json")
    assert (
        pr_result["candidate_diff_sha256"]
        == load_runtime_json(harness_repo, "verify-result.json")["candidate_diff_sha256"]
    )


def test_pr_checks_rerun_verifiers_on_local_pr_ref(harness_repo: Path) -> None:
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "pr", "create", TASK_ID, role="integrator").returncode == 0

    checked = run_harness(harness_repo, "pr", "checks", TASK_ID, role="integrator")

    assert checked.returncode == 0, checked.stdout + checked.stderr
    result = json.loads(checked.stdout)
    assert result["status"] == "pass"
    assert result["ref"].startswith(f"refs/harness/pr/{TASK_ID}/cand_")


def test_pr_checks_reject_moved_local_pr_ref(harness_repo: Path) -> None:
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0
    created = run_harness(harness_repo, "pr", "create", TASK_ID, role="integrator")
    assert created.returncode == 0, created.stdout + created.stderr
    ref = json.loads(created.stdout)["ref"]
    git(harness_repo, "update-ref", ref, "HEAD")

    checked = run_harness(harness_repo, "pr", "checks", TASK_ID, role="integrator")

    assert checked.returncode == 1
    result = json.loads(checked.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "pr_ref_hash_mismatch"


def test_land_requires_fresh_pr_checks_after_local_pr_created(
    harness_repo: Path,
    tmp_path: Path,
) -> None:
    add_remote(harness_repo, tmp_path)
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0
    assert (
        run_harness(
            harness_repo, "review", TASK_ID, "--run", "reader-correctness", role="reviewer"
        ).returncode
        == 0
    )
    assert (
        run_harness(
            harness_repo, "review", TASK_ID, "--run", "reader-scope", role="reviewer"
        ).returncode
        == 0
    )
    gate = run_harness(harness_repo, "gate", TASK_ID, role="integrator")
    assert gate.returncode == 0, gate.stdout + gate.stderr
    created = run_harness(harness_repo, "pr", "create", TASK_ID, role="integrator")
    assert created.returncode == 0, created.stdout + created.stderr

    landed = run_harness(harness_repo, "land", TASK_ID, role="integrator")

    assert landed.returncode == 1
    result = json.loads(landed.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "pr_checks_missing"

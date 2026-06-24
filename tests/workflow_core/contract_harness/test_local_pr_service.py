from __future__ import annotations

import json
from pathlib import Path

from .conftest import (
    TASK_ID,
    git,
    install_fake_gh,
    load_runtime_json,
    run_harness,
    runtime_task_dir,
)


def add_remote(repo: Path, tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    install_fake_gh(repo, tmp_path)
    return remote


def approve_and_post_review_gate(repo: Path) -> None:
    assert (
        run_harness(
            repo, "review", TASK_ID, "--run", "reader-correctness", role="reviewer"
        ).returncode
        == 0
    )
    assert (
        run_harness(repo, "review", TASK_ID, "--run", "reader-scope", role="reviewer").returncode
        == 0
    )
    gated = run_harness(repo, "post-review-gate", TASK_ID, role="integrator")
    assert gated.returncode == 0, gated.stdout + gated.stderr


def test_local_pr_ref_binds_to_candidate_hash(harness_repo: Path, tmp_path: Path) -> None:
    add_remote(harness_repo, tmp_path)
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0
    approve_and_post_review_gate(harness_repo)

    created = run_harness(harness_repo, "pr", "create", TASK_ID, role="integrator")

    assert created.returncode == 0, created.stdout + created.stderr
    result = json.loads(created.stdout)
    assert result["status"] == "created"
    assert result["external_pr"]["url"] == "https://github.com/example/repo/pull/123"
    assert result["external_pr"]["repository"] == "example/repo"
    assert result["ref"].startswith(f"refs/harness/pr/{TASK_ID}/cand_")
    assert not result["ref"].startswith("refs/foundation/pr/")
    assert git(harness_repo, "rev-parse", "--verify", result["ref"]).returncode == 0

    pr_result = load_runtime_json(harness_repo, "pr-result.json")
    assert (
        pr_result["candidate_diff_sha256"]
        == load_runtime_json(harness_repo, "verify-result.json")["candidate_diff_sha256"]
    )


def test_pr_create_requires_post_review_gate_pass(harness_repo: Path) -> None:
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0

    created = run_harness(harness_repo, "pr", "create", TASK_ID, role="integrator")

    assert created.returncode == 1
    result = json.loads(created.stdout)
    assert result["status"] == "blocked"
    assert result["classification"] == "integrator_required"
    assert result["reason"] == "review_quorum_unmet"
    assert not (runtime_task_dir(harness_repo) / "pr-result.json").exists()


def test_status_after_post_review_gate_recommends_pr_create(harness_repo: Path) -> None:
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0
    approve_and_post_review_gate(harness_repo)

    status = run_harness(harness_repo, "status", TASK_ID, role="integrator")

    assert status.returncode == 0, status.stdout + status.stderr
    result = json.loads(status.stdout)
    assert result["phase"] == "post_review_gated"
    assert result["next_action"] == {
        "status": "continue",
        "command": f"HARNESS_ROLE=integrator ./harness pr create {TASK_ID}",
        "reason": "post-review mechanical gate passed and PR creation is next",
    }


def test_land_requires_pr_created_after_post_review_gate(
    harness_repo: Path,
    tmp_path: Path,
) -> None:
    add_remote(harness_repo, tmp_path)
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0
    approve_and_post_review_gate(harness_repo)

    landed = run_harness(harness_repo, "land", TASK_ID, role="integrator")

    assert landed.returncode == 1
    result = json.loads(landed.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "pr_not_created"


def test_pr_create_revalidates_stale_post_review_gate_pass(harness_repo: Path) -> None:
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0
    approve_and_post_review_gate(harness_repo)
    blocked_review = run_harness(
        harness_repo,
        "review",
        TASK_ID,
        "--write-verdict",
        "reader-scope",
        "block",
        "--label",
        "scope_risk",
        role="reviewer",
    )
    assert blocked_review.returncode == 0, blocked_review.stdout + blocked_review.stderr

    created = run_harness(harness_repo, "pr", "create", TASK_ID, role="integrator")

    assert created.returncode == 1
    result = json.loads(created.stdout)
    assert result["status"] == "blocked"
    assert result["classification"] == "writer_rework_required"
    assert result["reason"] == "review_blocked"
    assert not (runtime_task_dir(harness_repo) / "pr-result.json").exists()


def test_pr_checks_rerun_verifiers_on_local_pr_ref(harness_repo: Path, tmp_path: Path) -> None:
    add_remote(harness_repo, tmp_path)
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0
    approve_and_post_review_gate(harness_repo)
    assert run_harness(harness_repo, "pr", "create", TASK_ID, role="integrator").returncode == 0

    checked = run_harness(harness_repo, "pr", "checks", TASK_ID, role="integrator")

    assert checked.returncode == 0, checked.stdout + checked.stderr
    result = json.loads(checked.stdout)
    assert result["status"] == "pass"
    assert result["ref"].startswith(f"refs/harness/pr/{TASK_ID}/cand_")


def test_pr_checks_reject_moved_local_pr_ref(harness_repo: Path, tmp_path: Path) -> None:
    add_remote(harness_repo, tmp_path)
    (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    assert run_harness(harness_repo, "submit", TASK_ID).returncode == 0
    approve_and_post_review_gate(harness_repo)
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

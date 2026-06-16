from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from workflow_core.contract_harness import push as push_module

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "harness"
TASK_ID = "T-0001"


def run_harness(
    repo: Path, *args: str, role: str = "integrator"
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HARNESS), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=90,
        env={**os.environ, "HARNESS_ROLE": role},
    )


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
        check=check,
    )


def init_repo(tmp_path: Path, *, push_mode: str = "dry_run") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    write_harness_config(repo, push_mode=push_mode)
    (repo / "src").mkdir()
    (repo / "src" / "app.txt").write_text("base\n", encoding="utf-8")
    (repo / "src" / "other.txt").write_text("base other\n", encoding="utf-8")
    (repo / "Makefile").write_text("check-required:\n\t@true\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    return repo


def write_harness_config(repo: Path, *, push_mode: str) -> None:
    base = repo / ".harness"
    (base / "tasks" / TASK_ID).mkdir(parents=True)
    (base / "rfc-decisions").mkdir()
    (base / "bottleneck.yaml").write_text("version: 1\n", encoding="utf-8")
    (base / "owners.yaml").write_text(
        "scopes:\n  demo:\n    allowed_paths:\n      - src/**\n",
        encoding="utf-8",
    )
    (base / "verifiers.yaml").write_text(
        "default:\n"
        "  - id: unit\n"
        "    command: python -c 'raise SystemExit(0)'\n"
        "    applies_to: ['**/*']\n"
        "    always: true\n",
        encoding="utf-8",
    )
    (base / "review.yaml").write_text(
        "default:\n"
        "  quorum: 2\n"
        "  reviewers:\n"
        "    - reader-correctness\n"
        "    - reader-scope\n"
        "  background_auto_run: true\n",
        encoding="utf-8",
    )
    (base / "policy.yaml").write_text(policy_yaml(push_mode), encoding="utf-8")
    (base / "tasks" / TASK_ID / "task.yaml").write_text(
        f"id: {TASK_ID}\n"
        "scope: demo\n"
        "base: main\n"
        "intent:\n"
        "  kind: implementation\n"
        "  summary: land push acceptance\n"
        "acceptance:\n"
        "  mode: generated\n"
        "allowed_outputs:\n"
        "  - source_diff\n",
        encoding="utf-8",
    )


def policy_yaml(push_mode: str) -> str:
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
    )


def add_remote(tmp_path: Path, repo: Path) -> Path:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    return remote


def runtime_task_dir(repo: Path) -> Path:
    common = Path(git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = repo / common
    return common / "harness-runtime" / "state" / "tasks" / TASK_ID


def runtime_root(repo: Path) -> Path:
    return runtime_task_dir(repo).parents[2]


def load_runtime(repo: Path, name: str) -> dict[str, Any]:
    data = json.loads((runtime_task_dir(repo) / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def prepare_candidate(repo: Path, text: str = "candidate\n") -> None:
    (repo / "src" / "app.txt").write_text(text, encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID, role="writer").returncode == 0
    assert run_harness(repo, "submit", TASK_ID, role="writer").returncode == 0
    gate = run_harness(repo, "gate", TASK_ID)
    assert gate.returncode == 0, gate.stdout + gate.stderr


def test_worktree_command_creates_writer_reviewer_and_integrator_worktrees(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)

    writer = json.loads(run_harness(repo, "worktree", TASK_ID, "--writer").stdout)
    reviewer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--reviewer", "reader-scope").stdout
    )
    integrator = json.loads(run_harness(repo, "worktree", TASK_ID, "--integrator").stdout)

    writer_path = Path(writer["path"])
    reviewer_path = Path(reviewer["path"])
    integrator_path = Path(integrator["path"])
    assert writer_path.is_dir()
    assert reviewer_path.is_dir()
    assert integrator_path.is_dir()
    assert str(writer_path).startswith(str(runtime_root(repo) / "worktrees"))
    assert (reviewer_path / "src" / "app.txt").read_text(encoding="utf-8") == "candidate\n"
    assert (
        git(integrator_path, "rev-parse", "HEAD").stdout.strip()
        == git(repo, "rev-parse", "origin/main").stdout.strip()
    )
    worktrees = (
        (writer_path, "writer"),
        (reviewer_path, "reviewer"),
        (integrator_path, "integrator"),
    )
    for path, kind in worktrees:
        marker = json.loads((path / ".harness-worktree.json").read_text(encoding="utf-8"))
        assert marker["task_id"] == TASK_ID
        assert marker["kind"] == kind
        assert marker["source_repo_common_dir"]


def test_worktree_reuses_clean_unmarked_legacy_worktree_by_migrating_marker(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)
    first = json.loads(run_harness(repo, "worktree", TASK_ID, "--writer").stdout)
    path = Path(first["path"])
    marker = path / ".harness-worktree.json"
    marker.unlink()

    second = run_harness(repo, "worktree", TASK_ID, "--writer")

    assert second.returncode == 0, second.stdout + second.stderr
    migrated = json.loads(marker.read_text(encoding="utf-8"))
    assert migrated["migration"] == "legacy-clean-worktree"


def test_worktree_refuses_dirty_unmarked_legacy_worktree_before_reset(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)
    first = json.loads(run_harness(repo, "worktree", TASK_ID, "--writer").stdout)
    path = Path(first["path"])
    (path / ".harness-worktree.json").unlink()
    (path / "src" / "app.txt").write_text("dirty legacy worktree\n", encoding="utf-8")

    second = run_harness(repo, "worktree", TASK_ID, "--writer")

    assert second.returncode != 0
    assert "unmarked harness worktree is dirty" in second.stdout


def test_affected_command_classifies_fast_partial_and_rebase(tmp_path: Path) -> None:
    fast_repo = init_repo(tmp_path / "fast")
    add_remote(tmp_path / "fast", fast_repo)
    prepare_candidate(fast_repo)
    fast = json.loads(run_harness(fast_repo, "affected", TASK_ID).stdout)
    assert fast["classification"] == "FAST"

    partial_repo = init_repo(tmp_path / "partial")
    add_remote(tmp_path / "partial", partial_repo)
    prepare_candidate(partial_repo)
    other = tmp_path / "other-partial"
    git(tmp_path, "clone", str(tmp_path / "partial" / "remote.git"), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "other.txt").write_text("target drift\n", encoding="utf-8")
    git(other, "commit", "-am", "target drift")
    git(other, "push", "origin", "main")
    partial = json.loads(run_harness(partial_repo, "affected", TASK_ID).stdout)
    assert partial["classification"] == "PARTIAL"

    rebase_repo = init_repo(tmp_path / "rebase")
    add_remote(tmp_path / "rebase", rebase_repo)
    prepare_candidate(rebase_repo)
    other_rebase = tmp_path / "other-rebase"
    git(tmp_path, "clone", str(tmp_path / "rebase" / "remote.git"), str(other_rebase))
    git(other_rebase, "config", "user.email", "test@example.com")
    git(other_rebase, "config", "user.name", "Test User")
    (other_rebase / "src" / "app.txt").write_text("target same path\n", encoding="utf-8")
    git(other_rebase, "commit", "-am", "target same path")
    git(other_rebase, "push", "origin", "main")
    rebase = json.loads(run_harness(rebase_repo, "affected", TASK_ID).stdout)
    assert rebase["classification"] == "REBASE"


def test_land_creates_integrator_commit_without_mutating_parent_head(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    before_head = git(repo, "rev-parse", "HEAD").stdout.strip()
    prepare_candidate(repo)

    landed = run_harness(repo, "land", TASK_ID)
    assert landed.returncode == 0, landed.stdout + landed.stderr
    result = json.loads(landed.stdout)
    assert result["status"] == "landed"
    assert result["classification"] == "FAST"
    assert result["landed_commit"]
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == before_head
    assert (
        git(Path(result["worktree_path"]), "rev-parse", "HEAD").stdout.strip()
        == result["landed_commit"]
    )
    assert load_runtime(repo, "land-result.json")["landed_commit"] == result["landed_commit"]


def test_push_dry_run_preserves_landed_context_without_external_write(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, push_mode="dry_run")
    remote = add_remote(tmp_path, repo)
    old_remote = git(repo, "rev-parse", "origin/main").stdout.strip()
    prepare_candidate(repo)
    land = json.loads(run_harness(repo, "land", TASK_ID).stdout)

    pushed = run_harness(repo, "push", TASK_ID)

    assert pushed.returncode != 0
    result = json.loads(pushed.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "protected_external_write"
    assert result["landed_commit"] == land["landed_commit"]
    assert result["target_base_sha"] == old_remote
    assert result["candidate_diff_sha256"] == land["candidate_diff_sha256"]
    assert result["machine_evidence_sha256"] == land["machine_evidence_sha256"]
    assert result["pushed_sha"] is None
    assert result["lock_acquire"] == {
        "reason": "protected_external_write",
        "status": "not_attempted",
    }
    assert result["sync"] == {
        "reason": "push_not_attempted",
        "status": "not_attempted",
    }
    assert git(remote, "rev-parse", "refs/heads/main").stdout.strip() == old_remote
    assert load_runtime(repo, "push-result.json")["landed_commit"] == land["landed_commit"]


def test_land_rebase_conflict_writes_rework_without_commit(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)
    other = tmp_path / "other"
    git(tmp_path, "clone", str(tmp_path / "remote.git"), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "app.txt").write_text("target conflict\n", encoding="utf-8")
    git(other, "commit", "-am", "target conflict")
    git(other, "push", "origin", "main")

    landed = run_harness(repo, "land", TASK_ID)
    assert landed.returncode != 0
    result = json.loads(landed.stdout)
    assert result["status"] == "rework_required"
    assert result["classification"] == "REBASE"
    assert result["landed_commit"] is None


def test_push_creates_rescue_ref_updates_remote_releases_lock_and_syncs_local(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path, push_mode="enabled")
    remote = add_remote(tmp_path, repo)
    old_remote = git(repo, "rev-parse", "origin/main").stdout.strip()
    prepare_candidate(repo)
    land = json.loads(run_harness(repo, "land", TASK_ID).stdout)
    git(repo, "checkout", "--", "src/app.txt")

    pushed = run_harness(repo, "push", TASK_ID)
    assert pushed.returncode == 0, pushed.stdout + pushed.stderr
    result = json.loads(pushed.stdout)
    assert result["status"] == "pushed"
    assert result["pushed_sha"] == land["landed_commit"]
    assert result["lock_ref"] == "refs/harness/locks/origin/main"
    assert result["remote_sha_before"] == old_remote
    assert result["remote_sha_after"] == land["landed_commit"]
    assert result["lock_acquire"]["status"] == "acquired"
    assert result["lock_acquire"]["target_sha"] == old_remote
    assert result["lock_release"] == {
        "ref": "refs/harness/locks/origin/main",
        "status": "released",
    }
    assert git(repo, "rev-parse", "origin/main").stdout.strip() == land["landed_commit"]
    assert git(repo, "rev-parse", "main").stdout.strip() == land["landed_commit"]

    refs = git(remote, "for-each-ref", "--format=%(refname) %(objectname)", "refs/harness").stdout
    assert f" {old_remote}" in refs
    assert f"refs/harness/rescue/main/{TASK_ID}/" in refs
    assert "refs/harness/locks/origin/main" not in refs
    assert load_runtime(repo, "push-result.json")["lock_release"]["status"] == "released"
    assert load_runtime(repo, "sync-result.json")["status"] == "local_synced"


def test_push_reports_local_sync_required_after_remote_update(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, push_mode="enabled")
    remote = add_remote(tmp_path, repo)
    old_remote = git(repo, "rev-parse", "origin/main").stdout.strip()
    prepare_candidate(repo)
    land = json.loads(run_harness(repo, "land", TASK_ID).stdout)

    pushed = run_harness(repo, "push", TASK_ID)

    assert pushed.returncode != 0
    result = json.loads(pushed.stdout)
    assert result["status"] == "pushed"
    assert result["reason"] == "local_sync_required"
    assert result["pushed_sha"] == land["landed_commit"]
    assert result["remote_sha_before"] == old_remote
    assert result["remote_sha_after"] == land["landed_commit"]
    assert result["sync"]["status"] == "local_sync_required"
    assert result["sync"]["reason"] == "dirty_worktree"
    assert result["lock_release"] == {
        "ref": "refs/harness/locks/origin/main",
        "status": "released",
    }
    assert git(remote, "rev-parse", "refs/heads/main").stdout.strip() == land["landed_commit"]
    assert git(repo, "rev-parse", "main").stdout.strip() == old_remote
    assert load_runtime(repo, "push-result.json")["reason"] == "local_sync_required"
    assert load_runtime(repo, "sync-result.json")["reason"] == "dirty_worktree"


def test_push_failure_after_rescue_writes_artifact_and_releases_lock(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path, push_mode="enabled")
    remote = add_remote(tmp_path, repo)
    hook = remote / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\n"
        "while read old new ref; do\n"
        '  if [ "$ref" = "refs/heads/main" ]; then\n'
        "    exit 1\n"
        "  fi\n"
        "done\n"
        "exit 0\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    old_remote = git(repo, "rev-parse", "origin/main").stdout.strip()
    prepare_candidate(repo)
    run_harness(repo, "land", TASK_ID)
    git(repo, "checkout", "--", "src/app.txt")

    pushed = run_harness(repo, "push", TASK_ID)
    assert pushed.returncode != 0
    result = json.loads(pushed.stdout)
    assert result["status"] == "failed"
    assert result["reason"] == "push_failed"
    assert result["pushed_sha"] is None
    assert result["rescue_ref"].startswith(f"refs/harness/rescue/main/{TASK_ID}/")
    assert result["lock_release"] == {
        "ref": "refs/harness/locks/origin/main",
        "status": "released",
    }
    assert load_runtime(repo, "push-result.json")["reason"] == "push_failed"

    refs = git(remote, "for-each-ref", "--format=%(refname) %(objectname)", "refs/harness").stdout
    assert f"{result['rescue_ref']} {old_remote}" in refs
    assert "refs/harness/locks/origin/main" not in refs
    assert git(remote, "rev-parse", "refs/heads/main").stdout.strip() == old_remote


def test_push_reports_nonzero_when_remote_lock_release_fails(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, push_mode="enabled")
    remote = add_remote(tmp_path, repo)
    hook = remote / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\n"
        "zero=0000000000000000000000000000000000000000\n"
        "while read old new ref; do\n"
        '  if [ "$ref" = "refs/harness/locks/origin/main" ] && [ "$new" = "$zero" ]; then\n'
        "    exit 1\n"
        "  fi\n"
        "done\n"
        "exit 0\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    old_remote = git(repo, "rev-parse", "origin/main").stdout.strip()
    prepare_candidate(repo)
    land = json.loads(run_harness(repo, "land", TASK_ID).stdout)
    git(repo, "checkout", "--", "src/app.txt")

    pushed = run_harness(repo, "push", TASK_ID)

    assert pushed.returncode != 0
    result = json.loads(pushed.stdout)
    assert result["status"] == "pushed"
    assert result["reason"] == "lock_release_failed"
    assert result["pushed_sha"] == land["landed_commit"]
    assert result["remote_sha_before"] == old_remote
    assert result["remote_sha_after"] == land["landed_commit"]
    assert result["lock_release"]["status"] == "release_failed"
    assert result["lock_release"]["ref"] == "refs/harness/locks/origin/main"
    assert git(remote, "rev-parse", "refs/heads/main").stdout.strip() == land["landed_commit"]
    lock_sha = git(remote, "rev-parse", "refs/harness/locks/origin/main").stdout.strip()
    assert lock_sha != old_remote
    assert git(remote, "rev-parse", "refs/harness/locks/origin/main^").stdout.strip() == old_remote
    assert load_runtime(repo, "push-result.json")["reason"] == "lock_release_failed"


def test_remote_push_lock_acquire_is_create_only_even_for_same_sha(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, push_mode="enabled")
    remote = add_remote(tmp_path, repo)
    remote_sha = git(repo, "rev-parse", "origin/main").stdout.strip()
    lock_ref = "refs/harness/locks/origin/main"

    first = push_module._acquire_remote_lock(repo, "origin", lock_ref, remote_sha)
    second = push_module._acquire_remote_lock(repo, "origin", lock_ref, remote_sha)

    assert first["ref"] == lock_ref
    assert first["status"] == "acquired"
    assert first["target_sha"] == remote_sha
    assert first["sha"] != remote_sha
    assert second["ref"] == lock_ref
    assert second["status"] == "blocked"
    assert second["reason"] == "remote_lock_exists"
    assert git(remote, "rev-parse", lock_ref).stdout.strip() == first["sha"]
    assert git(remote, "rev-parse", f"{lock_ref}^").stdout.strip() == remote_sha
    assert push_module._release_remote_lock(repo, "origin", lock_ref)["status"] == "released"


def test_push_is_blocked_by_remote_lock_ref(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, push_mode="enabled")
    remote = add_remote(tmp_path, repo)
    prepare_candidate(repo)
    run_harness(repo, "land", TASK_ID)
    target_sha = git(repo, "rev-parse", "origin/main").stdout.strip()
    lock = push_module._acquire_remote_lock(
        repo,
        "origin",
        "refs/harness/locks/origin/main",
        target_sha,
    )
    assert lock["status"] == "acquired"

    pushed = run_harness(repo, "push", TASK_ID)
    assert pushed.returncode != 0
    result = json.loads(pushed.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "blocked_by_lock"
    assert result["lock_ref"] == "refs/harness/locks/origin/main"
    assert result["lock_acquire"] == {
        "reason": "remote_lock_exists",
        "ref": "refs/harness/locks/origin/main",
        "sha": lock["sha"],
        "status": "blocked",
        "target_sha": target_sha,
    }
    assert git(remote, "rev-parse", "refs/heads/main").stdout.strip() == target_sha
    assert git(remote, "rev-parse", "refs/harness/locks/origin/main").stdout.strip() == lock["sha"]

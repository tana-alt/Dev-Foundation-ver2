from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from workflow_core.contract_harness import push as push_module
from workflow_core.contract_harness.hashing import file_hash

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


def init_repo(
    tmp_path: Path,
    *,
    push_mode: str = "dry_run",
    max_remote_changed_retries: int = 0,
) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    write_harness_config(
        repo,
        push_mode=push_mode,
        max_remote_changed_retries=max_remote_changed_retries,
    )
    (repo / "src").mkdir()
    (repo / "src" / "app.txt").write_text("base\n", encoding="utf-8")
    (repo / "src" / "other.txt").write_text("base other\n", encoding="utf-8")
    (repo / "Makefile").write_text("check-required:\n\t@true\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    return repo


def write_harness_config(
    repo: Path,
    *,
    push_mode: str,
    max_remote_changed_retries: int,
) -> None:
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
    (base / "policy.yaml").write_text(
        policy_yaml(push_mode, max_remote_changed_retries=max_remote_changed_retries),
        encoding="utf-8",
    )
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


def policy_yaml(push_mode: str, *, max_remote_changed_retries: int = 0) -> str:
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
        f"    max_remote_changed_retries: {max_remote_changed_retries}\n"
        "    oracle_timeout_s: 900\n"
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


def runtime_task_dir(repo: Path, task_id: str = TASK_ID) -> Path:
    common = Path(git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = repo / common
    return common / "harness-runtime" / "state" / "tasks" / task_id


def runtime_root(repo: Path) -> Path:
    return runtime_task_dir(repo).parents[2]


def load_runtime(repo: Path, name: str, task_id: str = TASK_ID) -> dict[str, Any]:
    data = json.loads((runtime_task_dir(repo, task_id) / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def prepare_candidate(repo: Path, text: str = "candidate\n", task_id: str = TASK_ID) -> None:
    prepare_candidate_path(repo, task_id, "src/app.txt", text)
    gate = run_harness(repo, "gate", task_id)
    assert gate.returncode == 0, gate.stdout + gate.stderr


def prepare_candidate_path(repo: Path, task_id: str, rel_path: str, text: str) -> None:
    (repo / rel_path).write_text(text, encoding="utf-8")
    assert run_harness(repo, "verify", task_id, role="writer").returncode == 0
    assert run_harness(repo, "submit", task_id, role="writer").returncode == 0


def add_task(repo: Path, task_id: str) -> None:
    task_path = repo / ".harness" / "tasks" / task_id / "task.yaml"
    task_path.parent.mkdir(parents=True)
    task_path.write_text(
        f"id: {task_id}\n"
        "scope: demo\n"
        "base: main\n"
        "intent:\n"
        "  kind: implementation\n"
        "  summary: compose acceptance\n"
        "acceptance:\n"
        "  mode: generated\n"
        "allowed_outputs:\n"
        "  - source_diff\n",
        encoding="utf-8",
    )
    git(repo, "add", str(task_path.relative_to(repo)))
    git(repo, "commit", "-m", f"add task {task_id}")


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
    git_dir = Path(git(writer_path, "rev-parse", "--git-dir").stdout.strip())
    if not git_dir.is_absolute():
        git_dir = writer_path / git_dir
    exclude_lines = (git_dir / "info" / "exclude").read_text(encoding="utf-8").splitlines()
    assert "artifact/" not in exclude_lines
    assert "artifact/*" in exclude_lines
    assert "!artifact/.gitkeep" in exclude_lines
    assert "!artifact/README.md" in exclude_lines


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


def test_spawn_uses_existing_worktree_marker_validation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)
    first = json.loads(run_harness(repo, "worktree", TASK_ID, "--writer").stdout)

    second = run_harness(repo, "worktree", TASK_ID, "--writer")

    assert second.returncode == 0, second.stdout + second.stderr
    reused = json.loads(second.stdout)
    marker = json.loads(
        (Path(reused["path"]) / ".harness-worktree.json").read_text(encoding="utf-8")
    )
    assert reused["path"] == first["path"]
    assert marker["task_id"] == TASK_ID
    assert marker["kind"] == "writer"
    assert marker["source_repo_common_dir"]


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


def test_land_before_gate_writes_blocked_phase_result(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate_path(repo, TASK_ID, "src/app.txt", "candidate\n")

    landed = run_harness(repo, "land", TASK_ID)

    assert landed.returncode != 0
    result = json.loads(landed.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "gate_result_missing"
    assert result["land_gate"] == {"status": "not_run"}
    assert load_runtime(repo, "land-result.json")["reason"] == "gate_result_missing"


def test_land_with_nonmergeable_gate_writes_blocked_phase_result(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate_path(repo, TASK_ID, "src/app.txt", "candidate\n")
    runtime = runtime_task_dir(repo)
    (runtime / "gate-result.json").write_text(
        json.dumps(
            {
                "task_id": TASK_ID,
                "status": "blocked",
                "reason": "review_quorum_unmet",
                "mergeable": False,
            }
        ),
        encoding="utf-8",
    )

    landed = run_harness(repo, "land", TASK_ID)

    assert landed.returncode != 0
    result = json.loads(landed.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "gate_not_mergeable"
    assert result["gate_result"]["reason"] == "review_quorum_unmet"
    assert load_runtime(repo, "land-result.json")["reason"] == "gate_not_mergeable"


def test_push_before_land_writes_blocked_phase_result(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)

    pushed = run_harness(repo, "push", TASK_ID)

    assert pushed.returncode != 0
    result = json.loads(pushed.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "land_result_missing"
    assert result["lock_acquire"]["status"] == "not_attempted"
    assert load_runtime(repo, "push-result.json")["reason"] == "land_result_missing"


def test_push_with_unlanded_result_writes_blocked_phase_result(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)
    runtime = runtime_task_dir(repo)
    (runtime / "land-result.json").write_text(
        json.dumps(
            {
                "task_id": TASK_ID,
                "status": "rework_required",
                "reason": "machine_gate_failed",
                "remote": "origin",
                "branch": "main",
                "target_base_sha": git(repo, "rev-parse", "origin/main").stdout.strip(),
                "landed_commit": None,
                "candidate_diff_sha256": "candidate",
                "machine_evidence_sha256": "machine",
            }
        ),
        encoding="utf-8",
    )

    pushed = run_harness(repo, "push", TASK_ID)

    assert pushed.returncode != 0
    result = json.loads(pushed.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "land_not_landed"
    assert result["remote"] == "origin"
    assert load_runtime(repo, "push-result.json")["reason"] == "land_not_landed"


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


def test_oracle_reapplies_single_candidate_green(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    target_head = git(repo, "rev-parse", "origin/main").stdout.strip()
    prepare_candidate(repo)
    parent_head = git(repo, "rev-parse", "HEAD").stdout.strip()
    runtime = runtime_task_dir(repo)
    before = {
        name: file_hash(runtime / name)
        for name in ("candidate.diff", "verify-result.json", "submission.json")
    }

    oracle = run_harness(repo, "oracle", TASK_ID, "--target-head", target_head)

    assert oracle.returncode == 0, oracle.stdout + oracle.stderr
    result = json.loads(oracle.stdout)
    assert result["status"] == "green"
    assert result["reason"] == "ok"
    assert result["target_head_sha"] == target_head
    assert result["merged_commit"]
    assert result["blamed_task_ids"] == []
    assert result["land_gate"]["status"] == "pass"
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == parent_head
    assert load_runtime(repo, "oracle-result.json")["merged_commit"] == result["merged_commit"]
    oracle_run = (
        runtime_root(repo)
        / "state"
        / "integration"
        / "origin"
        / "main"
        / "oracle-runs"
        / f"{result['run_id']}.json"
    )
    assert oracle_run.is_file()
    assert {
        name: file_hash(runtime / name)
        for name in ("candidate.diff", "verify-result.json", "submission.json")
    } == before


def test_oracle_writes_runtime_artifact_under_common_dir(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    target_head = git(repo, "rev-parse", "origin/main").stdout.strip()
    prepare_candidate(repo)

    oracle = run_harness(repo, "oracle", TASK_ID, "--target-head", target_head)

    assert oracle.returncode == 0, oracle.stdout + oracle.stderr
    result = json.loads(oracle.stdout)
    runtime = runtime_root(repo)
    assert (runtime / "state" / "tasks" / TASK_ID / "oracle-result.json").is_file()
    assert (
        runtime
        / "state"
        / "integration"
        / "origin"
        / "main"
        / "oracle-runs"
        / f"{result['run_id']}.json"
    ).is_file()
    assert not (repo / ".harness" / "state" / "tasks" / TASK_ID).exists()


def test_oracle_does_not_mutate_submission_artifacts(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    target_head = git(repo, "rev-parse", "origin/main").stdout.strip()
    prepare_candidate(repo)
    runtime = runtime_task_dir(repo)
    before = {
        name: file_hash(runtime / name)
        for name in ("candidate.diff", "verify-result.json", "submission.json")
    }

    oracle = run_harness(repo, "oracle", TASK_ID, "--target-head", target_head)

    assert oracle.returncode == 0, oracle.stdout + oracle.stderr
    after = {
        name: file_hash(runtime / name)
        for name in ("candidate.diff", "verify-result.json", "submission.json")
    }
    assert after == before


def test_oracle_rejects_candidate_hash_mismatch(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    target_head = git(repo, "rev-parse", "origin/main").stdout.strip()
    prepare_candidate(repo)
    (runtime_task_dir(repo) / "candidate.diff").write_text("not the submitted diff\n")

    oracle = run_harness(repo, "oracle", TASK_ID, "--target-head", target_head)

    assert oracle.returncode != 0
    result = json.loads(oracle.stdout)
    assert result["status"] == "red"
    assert result["reason"] == "candidate_hash_mismatch"
    assert result["blamed_task_ids"] == [TASK_ID]
    assert load_runtime(repo, "oracle-result.json")["reason"] == "candidate_hash_mismatch"


def test_oracle_blames_apply_failure(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    remote = add_remote(tmp_path, repo)
    prepare_candidate(repo)
    other = tmp_path / "other"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "app.txt").write_text("target conflict\n", encoding="utf-8")
    git(other, "commit", "-am", "target conflict")
    git(other, "push", "origin", "main")
    git(repo, "fetch", "origin", "main")
    target_head = git(repo, "rev-parse", "origin/main").stdout.strip()

    oracle = run_harness(repo, "oracle", TASK_ID, "--target-head", target_head)

    assert oracle.returncode != 0
    result = json.loads(oracle.stdout)
    assert result["status"] == "red"
    assert result["reason"] == "apply_failed"
    assert result["blamed_task_ids"] == [TASK_ID]
    assert result["land_gate"]["status"] == "not_run"


def test_oracle_blames_verifier_failure(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".harness" / "verifiers.yaml").write_text(
        "default:\n"
        "  - id: unit\n"
        "    command: "
        + json.dumps(
            'python -c "from pathlib import Path; '
            "raise SystemExit(0 if Path('src/other.txt').read_text() == 'base other\\n' else 1)\""
        )
        + "\n"
        "    applies_to: ['**/*']\n"
        "    always: true\n",
        encoding="utf-8",
    )
    git(repo, "add", ".harness/verifiers.yaml")
    git(repo, "commit", "-m", "tighten verifier")
    remote = add_remote(tmp_path, repo)
    prepare_candidate(repo)
    other = tmp_path / "other-verifier"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "other.txt").write_text("target drift\n", encoding="utf-8")
    git(other, "commit", "-am", "target drift")
    git(other, "push", "origin", "main")
    git(repo, "fetch", "origin", "main")
    target_head = git(repo, "rev-parse", "origin/main").stdout.strip()

    oracle = run_harness(repo, "oracle", TASK_ID, "--target-head", target_head)

    assert oracle.returncode != 0
    result = json.loads(oracle.stdout)
    assert result["status"] == "red"
    assert result["reason"] == "verifier_failed"
    assert result["blamed_task_ids"] == [TASK_ID]
    assert result["land_gate"]["status"] == "fail"


def test_compose_pending_candidates_green(tmp_path: Path) -> None:
    task_2 = "T-0002"
    repo = init_repo(tmp_path)
    add_task(repo, task_2)
    add_remote(tmp_path, repo)
    prepare_candidate_path(repo, TASK_ID, "src/app.txt", "candidate app\n")
    git(repo, "checkout", "--", "src/app.txt")
    prepare_candidate_path(repo, task_2, "src/other.txt", "candidate other\n")
    git(repo, "checkout", "--", "src/other.txt")

    composed = run_harness(repo, "compose", task_2, TASK_ID)

    assert composed.returncode == 0, composed.stdout + composed.stderr
    result = json.loads(composed.stdout)
    assert result["status"] == "green"
    assert result["reason"] == "ok"
    assert result["task_ids"] == [TASK_ID, task_2]
    assert result["green_task_ids"] == [TASK_ID, task_2]
    assert result["blamed_task_ids"] == []
    assert result["merged_commit"]
    worktree = Path(result["worktree_path"])
    assert git(worktree, "show", f"{result['merged_commit']}:src/app.txt").stdout == (
        "candidate app\n"
    )
    assert git(worktree, "show", f"{result['merged_commit']}:src/other.txt").stdout == (
        "candidate other\n"
    )
    pending = runtime_root(repo) / "state" / "integration" / "origin" / "main" / "pending.json"
    assert pending.is_file()
    pending_data = json.loads(pending.read_text(encoding="utf-8"))
    assert [row["task_id"] for row in pending_data["pending"]] == [TASK_ID, task_2]
    assert (pending.parent / "compose-result.json").is_file()
    assert not (runtime_task_dir(repo, TASK_ID) / "land-result.json").exists()
    assert not (runtime_task_dir(repo, task_2) / "land-result.json").exists()


def test_compose_blames_apply_failure_for_overlapping_candidate(
    tmp_path: Path,
) -> None:
    task_2 = "T-0002"
    repo = init_repo(tmp_path)
    add_task(repo, task_2)
    add_remote(tmp_path, repo)
    prepare_candidate_path(repo, TASK_ID, "src/app.txt", "candidate app 1\n")
    git(repo, "checkout", "--", "src/app.txt")
    prepare_candidate_path(repo, task_2, "src/app.txt", "candidate app 2\n")
    git(repo, "checkout", "--", "src/app.txt")

    composed = run_harness(repo, "compose", task_2, TASK_ID)

    assert composed.returncode != 0
    result = json.loads(composed.stdout)
    assert result["status"] == "red"
    assert result["reason"] == "apply_failed"
    assert result["green_task_ids"] == [TASK_ID]
    assert result["blamed_task_ids"] == [task_2]
    rework = load_runtime(repo, "rework-request.json", task_id=task_2)
    assert rework["reason"] == "apply_failed"
    assert rework["source_artifact"]["type"] == "compose_result"
    assert str(rework["source_artifact"]["sha256"]).startswith("sha256:")


def test_compose_refuses_dirty_existing_worktree_before_reset(tmp_path: Path) -> None:
    task_2 = "T-0002"
    repo = init_repo(tmp_path)
    add_task(repo, task_2)
    add_remote(tmp_path, repo)
    prepare_candidate_path(repo, TASK_ID, "src/app.txt", "candidate app\n")
    git(repo, "checkout", "--", "src/app.txt")
    prepare_candidate_path(repo, task_2, "src/other.txt", "candidate other\n")
    git(repo, "checkout", "--", "src/other.txt")
    first = run_harness(repo, "compose", task_2, TASK_ID)
    assert first.returncode == 0, first.stdout + first.stderr
    worktree = Path(json.loads(first.stdout)["worktree_path"])
    (worktree / "src" / "app.txt").write_text("dirty compose investigation\n", encoding="utf-8")

    second = run_harness(repo, "compose", task_2, TASK_ID)

    assert second.returncode != 0
    result = json.loads(second.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "compose_worktree_unusable"
    assert "compose worktree is dirty" in result["error"]
    compose_result = (
        runtime_root(repo) / "state" / "integration" / "origin" / "main" / "compose-result.json"
    )
    assert json.loads(compose_result.read_text(encoding="utf-8"))["status"] == "blocked"


def test_compose_refuses_unmarked_existing_worktree_before_reset(tmp_path: Path) -> None:
    task_2 = "T-0002"
    repo = init_repo(tmp_path)
    add_task(repo, task_2)
    add_remote(tmp_path, repo)
    prepare_candidate_path(repo, TASK_ID, "src/app.txt", "candidate app\n")
    git(repo, "checkout", "--", "src/app.txt")
    prepare_candidate_path(repo, task_2, "src/other.txt", "candidate other\n")
    git(repo, "checkout", "--", "src/other.txt")
    first = run_harness(repo, "compose", task_2, TASK_ID)
    assert first.returncode == 0, first.stdout + first.stderr
    worktree = Path(json.loads(first.stdout)["worktree_path"])
    (worktree / ".harness-compose-worktree.json").unlink()

    second = run_harness(repo, "compose", task_2, TASK_ID)

    assert second.returncode != 0
    result = json.loads(second.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "compose_worktree_unusable"
    assert "unmarked compose worktree" in result["error"]


def test_compose_push_green_set_updates_remote_and_per_task_artifacts(
    tmp_path: Path,
) -> None:
    task_2 = "T-0002"
    repo = init_repo(tmp_path, push_mode="enabled")
    add_task(repo, task_2)
    remote = add_remote(tmp_path, repo)
    prepare_candidate_path(repo, TASK_ID, "src/app.txt", "candidate app\n")
    git(repo, "checkout", "--", "src/app.txt")
    prepare_candidate_path(repo, task_2, "src/other.txt", "candidate other\n")
    git(repo, "checkout", "--", "src/other.txt")

    pushed = run_harness(repo, "compose-push", task_2, TASK_ID)

    assert pushed.returncode == 0, pushed.stdout + pushed.stderr
    result = json.loads(pushed.stdout)
    assert result["status"] == "pushed"
    assert result["green_task_ids"] == [TASK_ID, task_2]
    assert result["lock_acquire"]["status"] == "acquired"
    assert result["lock_release"]["status"] == "released"
    assert git(remote, "show", "main:src/app.txt").stdout == "candidate app\n"
    assert git(remote, "show", "main:src/other.txt").stdout == "candidate other\n"
    for task_id in (TASK_ID, task_2):
        land = load_runtime(repo, "land-result.json", task_id=task_id)
        push = load_runtime(repo, "push-result.json", task_id=task_id)
        assert land["status"] == "landed"
        assert land["classification"] == "COMPOSED"
        assert push["status"] == "pushed"
        assert push["composed_task_ids"] == [TASK_ID, task_2]
    compose_push = (
        runtime_root(repo)
        / "state"
        / "integration"
        / "origin"
        / "main"
        / "compose-push-result.json"
    )
    assert json.loads(compose_push.read_text(encoding="utf-8"))["status"] == "pushed"


def test_compose_push_dry_run_blocks_without_external_write(tmp_path: Path) -> None:
    task_2 = "T-0002"
    repo = init_repo(tmp_path, push_mode="dry_run")
    add_task(repo, task_2)
    remote = add_remote(tmp_path, repo)
    old_remote = git(repo, "rev-parse", "origin/main").stdout.strip()
    prepare_candidate_path(repo, TASK_ID, "src/app.txt", "candidate app\n")
    git(repo, "checkout", "--", "src/app.txt")
    prepare_candidate_path(repo, task_2, "src/other.txt", "candidate other\n")
    git(repo, "checkout", "--", "src/other.txt")

    pushed = run_harness(repo, "compose-push", task_2, TASK_ID)

    assert pushed.returncode != 0
    result = json.loads(pushed.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "protected_external_write"
    assert result["lock_acquire"]["status"] == "not_attempted"
    assert result["lock_release"]["status"] == "not_attempted"
    assert git(remote, "rev-parse", "refs/heads/main").stdout.strip() == old_remote
    for task_id in (TASK_ID, task_2):
        push = load_runtime(repo, "push-result.json", task_id=task_id)
        assert push["status"] == "blocked"


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


def test_manual_resolution_requires_resolved_diff_before_authority(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)

    checked = run_harness(repo, "manual-resolution-check", TASK_ID)

    assert checked.returncode != 0
    result = json.loads(checked.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "resolved_diff_required"
    assert result["authority"] is False


def test_resolved_diff_requires_machine_validation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)
    runtime = runtime_task_dir(repo)
    resolved = runtime / "resolved.diff"
    resolved.write_text((runtime / "candidate.diff").read_text(encoding="utf-8"), encoding="utf-8")
    (runtime / "resolved-diff.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": TASK_ID,
                "source": "manual_integrator_resolution",
                "base_target_sha": git(repo, "rev-parse", "origin/main").stdout.strip(),
                "candidate_diff_sha256": file_hash(runtime / "candidate.diff"),
                "resolved_diff_sha256": file_hash(resolved),
                "resolver_role": "integrator",
                "validation": {"status": "fail", "verifiers": []},
                "review_impact": {"requires_reapproval": False},
                "written_by": "harness",
            }
        ),
        encoding="utf-8",
    )

    checked = run_harness(repo, "manual-resolution-check", TASK_ID)

    assert checked.returncode != 0
    result = json.loads(checked.stdout)
    assert result["reason"] == "machine_validation_required"
    assert result["authority"] is False


def test_resolved_diff_requires_reapproval_when_certificate_subject_changes(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)
    runtime = runtime_task_dir(repo)
    resolved = runtime / "resolved.diff"
    resolved.write_text((runtime / "candidate.diff").read_text(encoding="utf-8"), encoding="utf-8")
    payload = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "source": "manual_integrator_resolution",
        "base_target_sha": git(repo, "rev-parse", "origin/main").stdout.strip(),
        "candidate_diff_sha256": file_hash(runtime / "candidate.diff"),
        "resolved_diff_sha256": file_hash(resolved),
        "resolver_role": "integrator",
        "validation": {"status": "pass", "verifiers": []},
        "review_impact": {
            "requires_reapproval": True,
            "reason": "resolved diff changes certified subject",
        },
        "written_by": "harness",
    }
    (runtime / "resolved-diff.json").write_text(json.dumps(payload), encoding="utf-8")

    checked = run_harness(repo, "manual-resolution-check", TASK_ID)

    assert checked.returncode != 0
    result = json.loads(checked.stdout)
    assert result["reason"] == "review_reapproval_required"
    assert result["authority"] is False

    payload["review_reapproval"] = {"status": "approved", "reviewer_ids": ["reader-correctness"]}
    (runtime / "resolved-diff.json").write_text(json.dumps(payload), encoding="utf-8")
    rechecked = run_harness(repo, "manual-resolution-check", TASK_ID)
    assert rechecked.returncode == 0, rechecked.stdout + rechecked.stderr
    assert json.loads(rechecked.stdout)["authority"] is True


def test_unvalidated_manual_resolution_cannot_be_landed_or_pushed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)
    runtime = runtime_task_dir(repo)
    (runtime / "resolved.diff").write_text("invalid manual diff\n", encoding="utf-8")
    (runtime / "resolved-diff.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": TASK_ID,
                "source": "manual_integrator_resolution",
                "candidate_diff_sha256": file_hash(runtime / "candidate.diff"),
                "resolved_diff_sha256": file_hash(runtime / "resolved.diff"),
                "validation": {"status": "fail", "verifiers": []},
                "review_impact": {"requires_reapproval": False},
                "written_by": "harness",
            }
        ),
        encoding="utf-8",
    )

    checked = run_harness(repo, "manual-resolution-check", TASK_ID)

    assert checked.returncode != 0
    assert json.loads(checked.stdout)["authority"] is False
    assert not (runtime / "land-result.json").exists()
    assert not (runtime / "push-result.json").exists()


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


def test_sequential_overlap_still_rebase_required_at_land(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    add_remote(tmp_path, repo)
    prepare_candidate(repo)
    other = tmp_path / "other-sequential-overlap"
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


def test_disjoint_concurrent_recovered_by_merge_oracle(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, push_mode="enabled", max_remote_changed_retries=2)
    remote = add_remote(tmp_path, repo)
    prepare_candidate(repo)
    land = json.loads(run_harness(repo, "land", TASK_ID).stdout)
    other = tmp_path / "other-disjoint"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "other.txt").write_text("target disjoint\n", encoding="utf-8")
    git(other, "commit", "-am", "target disjoint")
    git(other, "push", "origin", "main")
    git(repo, "checkout", "--", "src/app.txt")

    pushed = run_harness(repo, "push", TASK_ID)

    assert pushed.returncode == 0, pushed.stdout + pushed.stderr
    result = json.loads(pushed.stdout)
    assert result["status"] == "pushed"
    assert result["reason"] == "ok"
    assert result["landed_commit"] != land["landed_commit"]
    assert result["oracle_retry"]["status"] == "green"
    assert result["oracle_retry"]["attempt"] == 1
    assert result["remote_sha_before"] != land["target_base_sha"]
    assert result["lock_acquire"]["target_sha"] == result["remote_sha_before"]
    assert git(remote, "show", "main:src/app.txt").stdout == "candidate\n"
    assert git(remote, "show", "main:src/other.txt").stdout == "target disjoint\n"


def test_remote_lock_released_after_oracle_green(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, push_mode="enabled", max_remote_changed_retries=2)
    remote = add_remote(tmp_path, repo)
    prepare_candidate(repo)
    run_harness(repo, "land", TASK_ID)
    other = tmp_path / "other-oracle-green"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "other.txt").write_text("target disjoint\n", encoding="utf-8")
    git(other, "commit", "-am", "target disjoint")
    git(other, "push", "origin", "main")
    git(repo, "checkout", "--", "src/app.txt")

    pushed = run_harness(repo, "push", TASK_ID)

    assert pushed.returncode == 0, pushed.stdout + pushed.stderr
    result = json.loads(pushed.stdout)
    assert result["oracle_retry"]["status"] == "green"
    assert result["lock_release"]["status"] == "released"
    assert (
        "refs/harness/locks/origin/main"
        not in git(
            remote,
            "for-each-ref",
            "--format=%(refname)",
            "refs/harness/locks",
        ).stdout
    )


def test_remote_lock_released_after_oracle_red(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, push_mode="enabled", max_remote_changed_retries=2)
    remote = add_remote(tmp_path, repo)
    prepare_candidate(repo)
    run_harness(repo, "land", TASK_ID)
    other = tmp_path / "other-oracle-red"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "app.txt").write_text("target overlap\n", encoding="utf-8")
    git(other, "commit", "-am", "target overlap")
    git(other, "push", "origin", "main")

    pushed = run_harness(repo, "push", TASK_ID)

    assert pushed.returncode != 0
    result = json.loads(pushed.stdout)
    assert result["status"] == "rework_required"
    assert result["lock_acquire"]["status"] == "not_attempted"
    assert result["lock_release"]["status"] == "not_attempted"
    assert (
        "refs/harness/locks/origin/main"
        not in git(
            remote,
            "for-each-ref",
            "--format=%(refname)",
            "refs/harness/locks",
        ).stdout
    )


def test_remote_lock_not_held_while_oracle_runs(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = init_repo(tmp_path, push_mode="enabled", max_remote_changed_retries=1)
    remote = add_remote(tmp_path, repo)
    prepare_candidate(repo)
    run_harness(repo, "land", TASK_ID)
    other = tmp_path / "other-no-lock"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "other.txt").write_text("remote moved\n", encoding="utf-8")
    git(other, "commit", "-am", "remote moved")
    git(other, "push", "origin", "main")
    git(repo, "checkout", "--", "src/app.txt")
    monkeypatch.setenv("HARNESS_ROLE", "integrator")

    def green_noop_oracle(
        _root: Path,
        _task_id: str,
        *,
        target_head_sha: str,
        attempt: int = 1,
    ) -> tuple[dict[str, Any], int]:
        lock_ref = "refs/harness/locks/origin/main"
        assert not git(remote, "show-ref", "--verify", lock_ref, check=False).stdout
        return (
            {
                "status": "green",
                "reason": "ok",
                "attempt": attempt,
                "run_id": f"run-{attempt}",
                "target_head_sha": target_head_sha,
                "merged_commit": target_head_sha,
            },
            0,
        )

    monkeypatch.setattr(push_module, "run_single_candidate_oracle", green_noop_oracle)

    result, code = push_module.push_task(repo, TASK_ID)

    assert code == 0
    assert result["oracle_retry"]["status"] == "green"
    assert result["lock_acquire"]["status"] == "acquired"
    assert result["lock_release"]["status"] == "released"


def test_concurrent_overlap_still_no_clobber(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, push_mode="enabled", max_remote_changed_retries=2)
    remote = add_remote(tmp_path, repo)
    prepare_candidate(repo)
    run_harness(repo, "land", TASK_ID)
    other = tmp_path / "other-overlap"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "app.txt").write_text("target overlap\n", encoding="utf-8")
    git(other, "commit", "-am", "target overlap")
    git(other, "push", "origin", "main")

    pushed = run_harness(repo, "push", TASK_ID)

    assert pushed.returncode != 0
    result = json.loads(pushed.stdout)
    assert result["status"] == "rework_required"
    assert result["reason"] == "oracle_red"
    assert result["blamed_task_ids"] == [TASK_ID]
    assert result["lock_acquire"]["status"] == "not_attempted"
    assert result["lock_release"]["status"] == "not_attempted"
    assert load_runtime(repo, "rework-request.json")["reason"] == "apply_failed"
    assert git(remote, "show", "main:src/app.txt").stdout == "target overlap\n"


def test_oracle_retry_keeps_exact_cas_against_tested_head(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = init_repo(tmp_path, push_mode="enabled", max_remote_changed_retries=1)
    remote = add_remote(tmp_path, repo)
    prepare_candidate(repo)
    land = json.loads(run_harness(repo, "land", TASK_ID).stdout)
    other = tmp_path / "other-cas"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "other.txt").write_text("first remote move\n", encoding="utf-8")
    git(other, "commit", "-am", "first remote move")
    git(other, "push", "origin", "main")
    monkeypatch.setenv("HARNESS_ROLE", "integrator")

    def green_but_stale(
        _root: Path,
        _task_id: str,
        *,
        target_head_sha: str,
        attempt: int = 1,
    ) -> tuple[dict[str, Any], int]:
        (other / "src" / "other.txt").write_text("second remote move\n", encoding="utf-8")
        git(other, "commit", "-am", "second remote move")
        git(other, "push", "origin", "main")
        return (
            {
                "status": "green",
                "reason": "ok",
                "attempt": attempt,
                "run_id": f"run-{attempt}",
                "target_head_sha": target_head_sha,
                "merged_commit": land["landed_commit"],
            },
            0,
        )

    monkeypatch.setattr(push_module, "run_single_candidate_oracle", green_but_stale)

    result, code = push_module.push_task(repo, TASK_ID)

    assert code == 1
    assert result["status"] == "escalated"
    assert result["reason"] == "oracle_retry_exhausted"
    assert result["lock_acquire"]["status"] == "not_attempted"
    assert git(remote, "show", "main:src/app.txt").stdout == "base\n"
    assert git(remote, "show", "main:src/other.txt").stdout == "second remote move\n"


def test_retry_exhaustion_escalates_without_loop(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = init_repo(tmp_path, push_mode="enabled", max_remote_changed_retries=2)
    remote = add_remote(tmp_path, repo)
    prepare_candidate(repo)
    land = json.loads(run_harness(repo, "land", TASK_ID).stdout)
    other = tmp_path / "other-exhaustion"
    git(tmp_path, "clone", str(remote), str(other))
    git(other, "config", "user.email", "test@example.com")
    git(other, "config", "user.name", "Test User")
    (other / "src" / "other.txt").write_text("target drift 0\n", encoding="utf-8")
    git(other, "commit", "-am", "target drift 0")
    git(other, "push", "origin", "main")
    git(repo, "checkout", "--", "src/app.txt")
    monkeypatch.setenv("HARNESS_ROLE", "integrator")
    calls = 0

    def green_but_remote_moves(
        _root: Path,
        _task_id: str,
        *,
        target_head_sha: str,
        attempt: int = 1,
    ) -> tuple[dict[str, Any], int]:
        nonlocal calls
        calls += 1
        lock_ref = "refs/harness/locks/origin/main"
        assert not git(remote, "show-ref", "--verify", lock_ref, check=False).stdout
        (other / "src" / "other.txt").write_text(
            f"target drift {calls}\n",
            encoding="utf-8",
        )
        git(other, "commit", "-am", f"target drift {calls}")
        git(other, "push", "origin", "main")
        return (
            {
                "status": "green",
                "reason": "ok",
                "attempt": attempt,
                "run_id": f"run-{attempt}",
                "target_head_sha": target_head_sha,
                "merged_commit": target_head_sha,
            },
            0,
        )

    monkeypatch.setattr(push_module, "run_single_candidate_oracle", green_but_remote_moves)

    result, code = push_module.push_task(repo, TASK_ID)

    assert code == 1
    assert calls == 2
    assert result["status"] == "escalated"
    assert result["reason"] == "oracle_retry_exhausted"
    assert result["target_base_sha"] == land["target_base_sha"]
    assert result["lock_acquire"]["status"] == "not_attempted"
    assert result["lock_release"]["status"] == "not_attempted"
    assert load_runtime(repo, "push-result.json")["reason"] == "oracle_retry_exhausted"


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

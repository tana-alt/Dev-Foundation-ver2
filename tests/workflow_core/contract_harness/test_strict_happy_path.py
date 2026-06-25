from __future__ import annotations

import json
from pathlib import Path

from .conftest import (
    TASK_ID,
    create_session,
    git,
    install_fake_gh,
    start_daemon,
    strict_cli,
    strict_env,
    strict_json,
)


def test_strict_happy_path_to_complete(harness_repo: Path, tmp_path: Path) -> None:
    _add_remote(harness_repo, tmp_path)
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")
        reviewer = create_session(harness_repo, "reviewer", agent_id="reviewer.scope.T-0001")
        integrator = create_session(
            harness_repo,
            "integrator",
            agent_id="integrator.codex.T-0001",
        )
        admin = create_session(harness_repo, "admin", agent_id="admin.local.T-0001")

        assert strict_cli(harness_repo, "prepare", TASK_ID, session=writer).returncode == 0
        (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
        assert strict_cli(harness_repo, "verify", TASK_ID, session=writer).returncode == 0
        assert strict_cli(harness_repo, "submit", TASK_ID, session=writer).returncode == 0
        assert (
            strict_cli(
                harness_repo,
                "review",
                TASK_ID,
                "--run",
                "reader-scope",
                session=reviewer,
            ).returncode
            == 0
        )
        assert (
            strict_cli(
                harness_repo,
                "review",
                TASK_ID,
                "--run",
                "reader-correctness",
                session=reviewer,
            ).returncode
            == 0
        )
        assert (
            strict_cli(
                harness_repo,
                "review",
                TASK_ID,
                "--collect",
                session=integrator,
            ).returncode
            == 0
        )
        assert strict_cli(harness_repo, "gate", TASK_ID, session=integrator).returncode == 0
        assert strict_cli(harness_repo, "pr", "create", TASK_ID, session=integrator).returncode == 0
        assert strict_cli(harness_repo, "pr", "checks", TASK_ID, session=integrator).returncode == 0
        assert (
            strict_cli(
                harness_repo,
                "merge",
                "local",
                TASK_ID,
                session=integrator,
            ).returncode
            == 0
        )
        assert strict_cli(harness_repo, "complete", TASK_ID, session=integrator).returncode == 0

        status = strict_json(harness_repo, "status", TASK_ID, session=integrator)

        assert status["result"]["state_store"]["current_phase"] == "complete"
        assert status["result"]["authority"]["complete"] is True
        assert status["result"]["completion"]["complete"] is True
        integrity = strict_json(harness_repo, "integrity", "verify", session=admin)
        assert integrity["result"]["status"] == "pass"
    finally:
        daemon.stop()


def test_strict_complete_rejects_tampered_land_result(
    harness_repo: Path,
    tmp_path: Path,
) -> None:
    _add_remote(harness_repo, tmp_path)
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")
        reviewer = create_session(harness_repo, "reviewer", agent_id="reviewer.scope.T-0001")
        integrator = create_session(
            harness_repo,
            "integrator",
            agent_id="integrator.codex.T-0001",
        )
        assert strict_cli(harness_repo, "prepare", TASK_ID, session=writer).returncode == 0
        (harness_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
        assert strict_cli(harness_repo, "verify", TASK_ID, session=writer).returncode == 0
        assert strict_cli(harness_repo, "submit", TASK_ID, session=writer).returncode == 0
        assert (
            strict_cli(
                harness_repo,
                "review",
                TASK_ID,
                "--run",
                "reader-scope",
                session=reviewer,
            ).returncode
            == 0
        )
        assert (
            strict_cli(
                harness_repo,
                "review",
                TASK_ID,
                "--run",
                "reader-correctness",
                session=reviewer,
            ).returncode
            == 0
        )
        assert (
            strict_cli(harness_repo, "review", TASK_ID, "--collect", session=integrator).returncode
            == 0
        )
        assert strict_cli(harness_repo, "gate", TASK_ID, session=integrator).returncode == 0
        assert strict_cli(harness_repo, "pr", "create", TASK_ID, session=integrator).returncode == 0
        assert strict_cli(harness_repo, "pr", "checks", TASK_ID, session=integrator).returncode == 0
        assert (
            strict_cli(harness_repo, "merge", "local", TASK_ID, session=integrator).returncode == 0
        )

        land_path = _runtime_task_dir(harness_repo) / "land-result.json"
        land_result = json.loads(land_path.read_text(encoding="utf-8"))
        land_result["tampered"] = True
        land_path.write_text(json.dumps(land_result, sort_keys=True), encoding="utf-8")
        completed = strict_cli(harness_repo, "complete", TASK_ID, session=integrator)

        assert completed.returncode == 1
        assert "land_artifact_hash_mismatch" in completed.stdout
    finally:
        daemon.stop()


def _add_remote(repo: Path, tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    install_fake_gh(repo, tmp_path)
    return remote


def _runtime_task_dir(repo: Path) -> Path:
    env = strict_env(repo)
    if "HARNESS_RUNTIME_ROOT" in env:
        return Path(env["HARNESS_RUNTIME_ROOT"]) / "state" / "tasks" / TASK_ID
    common = Path(git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = repo / common
    return common / "harness-runtime" / "state" / "tasks" / TASK_ID

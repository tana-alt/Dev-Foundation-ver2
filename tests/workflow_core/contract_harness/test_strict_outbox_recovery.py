from __future__ import annotations

import json
from pathlib import Path

from .conftest import (
    TASK_ID,
    create_session,
    git,
    install_fake_gh,
    runtime_task_dir,
    start_daemon,
    strict_cli,
    strict_json,
)


def test_strict_pr_create_effect_is_idempotent(harness_repo: Path, tmp_path: Path) -> None:
    _drive_to_gate(harness_repo, tmp_path)
    daemon = start_daemon(harness_repo)
    try:
        integrator = create_session(
            harness_repo,
            "integrator",
            agent_id="integrator.codex.T-0001",
        )
        first = strict_json(harness_repo, "pr", "create", TASK_ID, session=integrator)
        second = strict_json(harness_repo, "pr", "create", TASK_ID, session=integrator)

        assert first["result"]["status"] == "succeeded"
        assert second["result"]["status"] == "reused"
        assert first["result"]["result"]["ref"] == second["result"]["effect"]["external_ref"]
        assert first["result"]["effect"]["effect_id"] == second["result"]["effect"]["effect_id"]
    finally:
        daemon.stop()


def test_strict_resume_requested_effect(harness_repo: Path, tmp_path: Path) -> None:
    _drive_to_gate(harness_repo, tmp_path)
    daemon = start_daemon(harness_repo)
    try:
        integrator = create_session(
            harness_repo,
            "integrator",
            agent_id="integrator.codex.T-0001",
        )
        requested = strict_json(harness_repo, "pr", "create", TASK_ID, session=integrator)
        effect_id = requested["result"]["effect"]["effect_id"]
        _mark_effect_requested(harness_repo, effect_id)

        resumed = strict_json(harness_repo, "outbox", "resume", session=integrator)

        assert resumed["result"]["resumed"] == 1
        assert resumed["result"]["results"][0]["status"] == "succeeded"
        assert resumed["result"]["results"][0]["recovered"] is True
    finally:
        daemon.stop()


def test_strict_resume_rejects_tampered_pr_observation(
    harness_repo: Path,
    tmp_path: Path,
) -> None:
    _drive_to_gate(harness_repo, tmp_path)
    daemon = start_daemon(harness_repo)
    try:
        integrator = create_session(
            harness_repo,
            "integrator",
            agent_id="integrator.codex.T-0001",
        )
        requested = strict_json(harness_repo, "pr", "create", TASK_ID, session=integrator)
        effect_id = requested["result"]["effect"]["effect_id"]
        strict_runtime = Path(
            daemon.env.get(
                "HARNESS_RUNTIME_ROOT",
                str(runtime_task_dir(harness_repo).parents[2]),
            )
        )
        pr_result_path = strict_runtime / "state" / "tasks" / TASK_ID / "pr-result.json"
        pr_result = json.loads(pr_result_path.read_text(encoding="utf-8"))
        pr_result["head_sha"] = "0" * 40
        pr_result_path.write_text(
            json.dumps(pr_result, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _mark_effect_requested(harness_repo, effect_id)

        resumed = strict_json(harness_repo, "outbox", "resume", session=integrator)
        result = resumed["result"]["results"][0]

        assert not (result["status"] == "succeeded" and result.get("recovered") is True)
    finally:
        daemon.stop()


def _drive_to_gate(repo: Path, tmp_path: Path) -> None:
    _add_remote(repo, tmp_path)
    daemon = start_daemon(repo)
    try:
        writer = create_session(repo, "writer", agent_id="writer.codex.T-0001")
        reviewer = create_session(repo, "reviewer", agent_id="reviewer.scope.T-0001")
        integrator = create_session(repo, "integrator", agent_id="integrator.codex.T-0001")
        assert strict_cli(repo, "prepare", TASK_ID, session=writer).returncode == 0
        (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
        assert strict_cli(repo, "verify", TASK_ID, session=writer).returncode == 0
        assert strict_cli(repo, "submit", TASK_ID, session=writer).returncode == 0
        assert (
            strict_cli(
                repo,
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
                repo,
                "review",
                TASK_ID,
                "--run",
                "reader-correctness",
                session=reviewer,
            ).returncode
            == 0
        )
        assert strict_cli(repo, "review", TASK_ID, "--collect", session=integrator).returncode == 0
        assert strict_cli(repo, "gate", TASK_ID, session=integrator).returncode == 0
    finally:
        daemon.stop()


def _add_remote(repo: Path, tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    install_fake_gh(repo, tmp_path)


def _mark_effect_requested(repo: Path, effect_id: str) -> None:
    import sqlite3

    common = Path(git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = repo / common
    env_root = json.loads(strict_cli(repo, "daemon", "status").stdout)["result"]["daemon"][
        "runtime_root"
    ]
    db_path = Path(env_root or common / "harness-runtime") / "state" / "workflow-state.db"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            UPDATE external_effects
            SET status = 'requested',
                external_ref = NULL,
                observed_hash = NULL,
                result_event_sha256 = NULL,
                last_error = NULL
            WHERE effect_id = ?
            """,
            (effect_id,),
        )

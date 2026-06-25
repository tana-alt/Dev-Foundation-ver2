from __future__ import annotations

from pathlib import Path

from workflow_core.contract_harness.review_comment_adapter import (
    acquire_review_lock,
    parse_review_command,
)

from .conftest import git


def test_parse_review_command_modes() -> None:
    normal = parse_review_command("/review", sha="abc123", comment_id="1", actor="dev")
    arch = parse_review_command("/review arch", sha="abc123", comment_id="2", actor="dev")
    full = parse_review_command("/review full", sha="abc123", comment_id="3", actor="dev")
    bare = parse_review_command("review", sha="abc123", comment_id="4", actor="dev")
    architecture = parse_review_command(
        "architecture review",
        sha="abc123",
        comment_id="5",
        actor="dev",
    )

    assert normal is not None
    assert normal.mode == "normal"
    assert arch is not None
    assert arch.mode == "arch"
    assert full is not None
    assert full.mode == "full"
    assert bare is not None
    assert bare.mode == "normal"
    assert architecture is not None
    assert architecture.mode == "arch"


def test_parse_review_command_ignores_unknown_comment() -> None:
    assert parse_review_command("/review later", sha="abc123", comment_id="1", actor="dev") is None
    assert parse_review_command("please /review", sha="abc123", comment_id="1", actor="dev") is None


def test_acquire_review_lock_is_create_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    sha = git(repo, "rev-parse", "HEAD").stdout.strip()

    assert acquire_review_lock(repo, sha=sha, mode="arch") is True
    assert acquire_review_lock(repo, sha=sha, mode="arch") is False
    assert git(repo, "rev-parse", "refs/harness/locks/" + sha + "-arch").stdout.strip() == sha

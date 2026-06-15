from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from workflow_core.abrun import (
    AbrunError,
    SideSpec,
    clean,
    ensure_worktree,
    load_config,
    orchestrate,
    resolve_ref,
)
from workflow_core.runstore import RunStore

# Deterministic stdout-metric values committed into the scratch repo.
BASE = [100.0, 101.0, 99.0, 100.5, 100.2, 99.8, 100.1, 100.3, 99.9, 100.0]
CAND = [112.0, 113.0, 111.0, 112.5, 112.2, 111.8, 112.1, 112.3, 111.9, 112.0]

MEASURE_TEMPLATE = """import os
VALUES = {values}
print(VALUES[int(os.environ["ABRUN_ITERATION"]) % len(VALUES)])
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Scratch repo: main prints BASE values, branch 'cand' prints CAND values."""
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True, text=True
    )
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "t")
    (path / "measure.py").write_text(MEASURE_TEMPLATE.format(values=BASE), encoding="utf-8")
    git(path, "add", "measure.py")
    git(path, "commit", "-m", "baseline")
    git(path, "checkout", "-b", "cand")
    (path / "measure.py").write_text(MEASURE_TEMPLATE.format(values=CAND), encoding="utf-8")
    git(path, "commit", "-am", "candidate")
    git(path, "checkout", "main")
    return path


def write_config(tmp_path: Path, **overrides: object) -> Path:
    data: dict[str, object] = {
        "baseline": {"ref": "main", "worktree": str(tmp_path / "wts" / "base")},
        "candidate": {"ref": "cand", "worktree": str(tmp_path / "wts" / "cand")},
        "measure": {
            "tool": "command",
            "command": [sys.executable, "measure.py"],
            "metric": "demo.value",
            "unit": "ms",
            "value_from": "stdout",
        },
        "iterations": 10,
        "warmup": 0,
    }
    data.update(overrides)
    path = tmp_path / "ab.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def make_store(tmp_path: Path) -> RunStore:
    return RunStore(tmp_path / "runs.db")


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_returns_hash(tmp_path: Path) -> None:
    config, config_hash = load_config(write_config(tmp_path))
    assert config.iterations == 10
    assert config.measure.metric == "demo.value"
    assert len(config_hash) == 64
    _, other_hash = load_config(write_config(tmp_path, iterations=11))
    assert other_hash != config_hash


def test_load_config_rejects_bad_shape(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"baseline": {"ref": "main", "worktree": "x"}}', encoding="utf-8")
    with pytest.raises(AbrunError, match="invalid config"):
        load_config(path)
    with pytest.raises(AbrunError, match="iterations"):
        load_config(write_config(tmp_path, iterations=0))


# ---------------------------------------------------------------------------
# worktree guard rails
# ---------------------------------------------------------------------------


def test_ensure_worktree_creates_with_marker(tmp_path: Path, repo: Path) -> None:
    sha = resolve_ref(repo, "main")
    assert len(sha) == 40
    worktree = ensure_worktree(repo, SideSpec(ref="main", worktree=str(tmp_path / "wt")), sha)
    assert (worktree / ".abrun-worktree").is_file()
    assert (worktree / "measure.py").is_file()
    # idempotent reuse at the same sha
    assert ensure_worktree(repo, SideSpec(ref="main", worktree=str(worktree)), sha) == worktree


def test_worktree_inside_repo_rejected(tmp_path: Path, repo: Path) -> None:
    sha = resolve_ref(repo, "main")
    with pytest.raises(AbrunError, match="outside tracked repo paths"):
        ensure_worktree(repo, SideSpec(ref="main", worktree=str(repo / "inner")), sha)


def test_foreign_directory_rejected(tmp_path: Path, repo: Path) -> None:
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    sha = resolve_ref(repo, "main")
    with pytest.raises(AbrunError, match="not an abrun worktree"):
        ensure_worktree(repo, SideSpec(ref="main", worktree=str(foreign)), sha)


def test_stale_worktree_sha_rejected(tmp_path: Path, repo: Path) -> None:
    spec = SideSpec(ref="main", worktree=str(tmp_path / "wt"))
    ensure_worktree(repo, spec, resolve_ref(repo, "main"))
    with pytest.raises(AbrunError, match="abrun clean"):
        ensure_worktree(repo, spec, resolve_ref(repo, "cand"))


# ---------------------------------------------------------------------------
# orchestrate
# ---------------------------------------------------------------------------


def test_orchestrate_records_both_sides(tmp_path: Path, repo: Path) -> None:
    config, config_hash = load_config(write_config(tmp_path))
    with make_store(tmp_path) as store:
        result = orchestrate(repo, store, config, config_hash)
        assert not result.baseline_cached and not result.candidate_cached
        assert store.sample_values(result.baseline_run_id, "demo.value") == BASE
        assert store.sample_values(result.candidate_run_id, "demo.value") == CAND
        run = store.get_run(result.candidate_run_id)
        assert run is not None
        assert run.commit_sha == resolve_ref(repo, "cand")
        assert run.config_hash == config_hash
        assert run.env_fingerprint
        assert store.metric_names(result.candidate_run_id) == ["demo.value"]


def test_orchestrate_reuses_cached_runs(tmp_path: Path, repo: Path) -> None:
    config, config_hash = load_config(write_config(tmp_path))
    with make_store(tmp_path) as store:
        first = orchestrate(repo, store, config, config_hash)
        second = orchestrate(repo, store, config, config_hash)
        assert second.baseline_cached and second.candidate_cached
        assert second.baseline_run_id == first.baseline_run_id
        fresh = orchestrate(repo, store, config, config_hash, no_cache=True)
        assert not fresh.baseline_cached
        assert fresh.baseline_run_id != first.baseline_run_id


def test_orchestrate_failing_measure_raises(tmp_path: Path, repo: Path) -> None:
    failing = {
        "tool": "command",
        "command": [sys.executable, "-c", "import sys; sys.exit(3)"],
        "metric": "demo.value",
        "value_from": "stdout",
    }
    config, config_hash = load_config(write_config(tmp_path, measure=failing, iterations=1))
    with make_store(tmp_path) as store, pytest.raises(AbrunError, match="exited 3"):
        orchestrate(repo, store, config, config_hash)


def test_wallclock_mode_records_positive_ms(tmp_path: Path, repo: Path) -> None:
    wallclock = {
        "tool": "command",
        "command": [sys.executable, "-c", "pass"],
        "metric": "demo.wall_ms",
        "value_from": "wallclock",
    }
    config, config_hash = load_config(
        write_config(
            tmp_path,
            measure=wallclock,
            iterations=7,
            candidate={"ref": "main", "worktree": str(tmp_path / "wts" / "cand")},
        )
    )
    with make_store(tmp_path) as store:
        result = orchestrate(repo, store, config, config_hash)
        values = store.sample_values(result.baseline_run_id, "demo.wall_ms")
        assert len(values) == 7
        assert all(v > 0 for v in values)


# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------


def test_clean_removes_only_owned_worktrees(tmp_path: Path, repo: Path) -> None:
    config, config_hash = load_config(write_config(tmp_path, iterations=1))
    with make_store(tmp_path) as store:
        orchestrate(repo, store, config, config_hash)
    removed = clean(repo, config)
    assert len(removed) == 2
    assert not (tmp_path / "wts" / "base").exists()
    assert "wts" not in git(repo, "worktree", "list")


def test_clean_refuses_foreign_directory(tmp_path: Path, repo: Path) -> None:
    foreign = tmp_path / "wts" / "base"
    foreign.mkdir(parents=True)
    config, _ = load_config(write_config(tmp_path))
    with pytest.raises(AbrunError, match="refusing to remove"):
        clean(repo, config)


# ---------------------------------------------------------------------------
# server lifecycle
# ---------------------------------------------------------------------------


def test_server_lifecycle_start_healthy_stop(tmp_path: Path) -> None:
    from workflow_core.abrun import HealthcheckSpec, ServerSpec, _Server

    spec = ServerSpec(
        start=f"{sys.executable} -m http.server {{port}} --bind 127.0.0.1",
        healthcheck=HealthcheckSpec(path="/", timeout_sec=15),
    )
    server = _Server(spec, tmp_path)
    try:
        server.wait_healthy()
    finally:
        server.stop()

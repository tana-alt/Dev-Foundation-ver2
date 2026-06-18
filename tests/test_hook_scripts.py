"""Subprocess-level tests for the three hook scripts.

Tests exercise:
  - hook_post_tool_use.py: happy path writes trajectory JSONL
  - hook_post_tool_use.py: malformed stdin exits 0 and writes nothing
  - hook_stop.py: ungated project exits 0 with empty stdout
  - hook_stop.py: stop_hook_active guard exits 0 (even when gated)
  - hook_session_start.py: empty stdin + no issues file exits 0
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"


def _env(**overrides: str) -> dict[str, str]:
    """Merge os.environ with overrides so scripts can find the venv / python paths."""
    return {**os.environ, **overrides}


def _load_hook_stop() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "hook_stop_test_module",
        _SCRIPTS / "hook_stop.py",
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# hook_post_tool_use.py
# ---------------------------------------------------------------------------


def test_hook_post_tool_use_writes_trajectory(tmp_path: Path) -> None:
    import subprocess

    session_id = "test-session-42"
    payload = json.dumps(
        {
            "session_id": session_id,
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_response": {"exit_code": 0},
        }
    )
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_post_tool_use.py")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(
            FOUNDATION_REPO_ROOT=str(tmp_path),
            FOUNDATION_PROJECT_ID="t",
            HARNESS_ROLE="writer",
        ),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    trajectory_dir = tmp_path / "artifact" / "t" / "trajectory"
    jsonl_file = trajectory_dir / f"{session_id}.jsonl"
    assert jsonl_file.is_file(), f"JSONL file not found at {jsonl_file}"

    lines = jsonl_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["tool"] == "Bash"
    assert event["run_id"] == session_id
    assert event["role"] == "writer"


def test_hook_post_tool_use_infers_repo_and_task_from_harness_worktree(
    tmp_path: Path,
) -> None:
    import subprocess

    session_id = "test-session-worktree"
    task_id = "task-from-marker"
    (tmp_path / ".harness-worktree.json").write_text(
        json.dumps({"task_id": task_id, "kind": "writer"}),
        encoding="utf-8",
    )
    payload = json.dumps(
        {
            "session_id": session_id,
            "tool_name": "Bash",
            "tool_input": {"command": "harness verify"},
            "tool_response": {"exit_code": 0},
        }
    )

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_post_tool_use.py")],
        input=payload,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(HARNESS_ROLE="writer"),
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    jsonl_file = tmp_path / "artifact" / task_id / "trajectory" / f"{session_id}.jsonl"
    assert jsonl_file.is_file()
    event = json.loads(jsonl_file.read_text(encoding="utf-8").splitlines()[0])
    assert event["role"] == "writer"
    assert event["target"] == "harness"


def test_hook_post_tool_use_in_linked_worktree_writes_to_canonical_artifact_root(
    tmp_path: Path,
) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "base"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    writer = tmp_path / "writer"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(writer), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    task_id = "task-from-linked-worktree"
    session_id = "test-session-linked-worktree"
    (writer / ".harness-worktree.json").write_text(
        json.dumps({"task_id": task_id, "kind": "writer"}),
        encoding="utf-8",
    )
    payload = json.dumps(
        {
            "session_id": session_id,
            "tool_name": "Bash",
            "tool_input": {"command": "harness verify"},
            "tool_response": {"exit_code": 0},
        }
    )

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_post_tool_use.py")],
        input=payload,
        cwd=writer,
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(HARNESS_ROLE="writer"),
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    jsonl_file = repo / "artifact" / task_id / "trajectory" / f"{session_id}.jsonl"
    assert jsonl_file.is_file()
    assert not (writer / "artifact" / task_id / "trajectory" / f"{session_id}.jsonl").exists()


def test_hook_post_tool_use_malformed_stdin_exits_0(tmp_path: Path) -> None:
    import subprocess

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_post_tool_use.py")],
        input="not json",
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(
            FOUNDATION_REPO_ROOT=str(tmp_path),
            FOUNDATION_PROJECT_ID="t",
        ),
    )
    assert result.returncode == 0

    trajectory_dir = tmp_path / "artifact" / "t" / "trajectory"
    # Nothing should have been written.
    assert not trajectory_dir.exists() or not list(trajectory_dir.iterdir())


# ---------------------------------------------------------------------------
# hook_stop.py
# ---------------------------------------------------------------------------


def test_hook_stop_ungated_exits_0_empty_stdout(tmp_path: Path) -> None:
    """With no Plan dir, the project is ungated: hook exits 0 with no stdout."""
    import subprocess

    harness = tmp_path / "harness"
    marker = tmp_path / "called.txt"
    harness.write_text(f"#!/usr/bin/env sh\ntouch {marker}\nexit 99\n", encoding="utf-8")
    harness.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_stop.py")],
        input=json.dumps({}),
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(FOUNDATION_REPO_ROOT=str(tmp_path)),
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert not marker.exists()


def test_hook_stop_planned_delegates_to_harness_gate(tmp_path: Path) -> None:
    """Plan-gated work without submission does not start background dispatch."""
    import subprocess

    project = "t"
    plans_dir = tmp_path / "Plan" / project / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "Plan_N0001.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
    harness = tmp_path / "harness"
    marker = tmp_path / "called.txt"
    harness.write_text(
        f"#!/usr/bin/env sh\ntouch {marker}\nexit 99\n",
        encoding="utf-8",
    )
    harness.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_stop.py")],
        input=json.dumps({}),
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(
            FOUNDATION_REPO_ROOT=str(tmp_path),
            FOUNDATION_PROJECT_ID=project,
            HARNESS_RUNTIME_ROOT=str(tmp_path / "runtime"),
        ),
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert not marker.exists()


def test_hook_stop_submitted_delegates_to_harness_dispatch(tmp_path: Path) -> None:
    """Submitted work is delegated to HARNESS_ROLE=integrator ./harness dispatch."""
    import subprocess

    project = "t"
    plans_dir = tmp_path / "Plan" / project / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "Plan_N0001.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    submission = runtime / "state" / "tasks" / project / "submission.json"
    submission.parent.mkdir(parents=True)
    submission.write_text('{"status":"submitted"}\n', encoding="utf-8")
    harness = tmp_path / "harness"
    harness.write_text(
        "#!/usr/bin/env sh\n"
        'printf "%s %s %s\\n" "$HARNESS_ROLE" "$1" "$2" > "$FOUNDATION_REPO_ROOT/called.txt"\n'
        'printf \'{"mergeable":false,"reason":"review_quorum_unmet"}\\n\'\n'
        "exit 1\n",
        encoding="utf-8",
    )
    harness.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_stop.py")],
        input=json.dumps({}),
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(
            FOUNDATION_REPO_ROOT=str(tmp_path),
            FOUNDATION_PROJECT_ID=project,
            HARNESS_RUNTIME_ROOT=str(runtime),
        ),
    )
    assert result.returncode == 0
    assert (tmp_path / "called.txt").read_text(encoding="utf-8").strip() == "integrator dispatch t"
    assert json.loads(result.stdout) == {
        "decision": "allow",
        "dispatch_returncode": 1,
        "reason": "review_quorum_unmet",
    }
    observation = json.loads(
        (runtime / "state" / "tasks" / project / "hook-stop-dispatch.json").read_text(
            encoding="utf-8"
        )
    )
    assert observation["status"] == "failed"
    assert observation["reason"] == "review_quorum_unmet"
    assert observation["dispatch_returncode"] == 1


def test_hook_stop_submitted_without_plan_still_dispatches(tmp_path: Path) -> None:
    """Submission evidence is enough for observational dispatch; Plan records are not required."""
    import subprocess

    project = "t"
    runtime = tmp_path / "runtime"
    submission = runtime / "state" / "tasks" / project / "submission.json"
    submission.parent.mkdir(parents=True)
    submission.write_text('{"status":"submitted"}\n', encoding="utf-8")
    harness = tmp_path / "harness"
    harness.write_text(
        "#!/usr/bin/env sh\n"
        'printf "%s %s %s\\n" "$HARNESS_ROLE" "$1" "$2" > "$FOUNDATION_REPO_ROOT/called.txt"\n'
        'printf \'{"status":"integrated","reason":"ok"}\\n\'\n'
        "exit 0\n",
        encoding="utf-8",
    )
    harness.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_stop.py")],
        input=json.dumps({}),
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(
            FOUNDATION_REPO_ROOT=str(tmp_path),
            FOUNDATION_PROJECT_ID=project,
            HARNESS_RUNTIME_ROOT=str(runtime),
        ),
    )

    assert result.returncode == 0
    assert (tmp_path / "called.txt").read_text(encoding="utf-8").strip() == "integrator dispatch t"
    assert json.loads(result.stdout) == {
        "decision": "allow",
        "dispatch_returncode": 0,
        "reason": "ok",
    }


def test_hook_stop_infers_repo_and_task_from_linked_writer_worktree(
    tmp_path: Path,
) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "base"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    writer = tmp_path / "writer"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(writer), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    task_id = "task-from-stop-marker"
    (writer / ".harness-worktree.json").write_text(
        json.dumps({"task_id": task_id, "kind": "writer"}),
        encoding="utf-8",
    )
    submission = repo / ".git" / "harness-runtime" / "state" / "tasks" / task_id / "submission.json"
    submission.parent.mkdir(parents=True)
    submission.write_text('{"status":"submitted"}\n', encoding="utf-8")
    harness = repo / "harness"
    harness.write_text(
        "#!/usr/bin/env sh\n"
        'printf "%s %s %s\\n" "$HARNESS_ROLE" "$1" "$2" > called.txt\n'
        'printf \'{"status":"integrated","reason":"ok"}\\n\'\n'
        "exit 0\n",
        encoding="utf-8",
    )
    harness.chmod(0o755)
    env = _env()
    for key in list(env):
        if key.startswith("FOUNDATION_") or key == "HARNESS_RUNTIME_ROOT":
            env.pop(key, None)

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_stop.py")],
        input=json.dumps({}),
        cwd=writer,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert (repo / "called.txt").read_text(encoding="utf-8").strip() == (
        f"integrator dispatch {task_id}"
    )
    assert json.loads(result.stdout) == {
        "decision": "allow",
        "dispatch_returncode": 0,
        "reason": "ok",
    }


def test_hook_stop_missing_harness_is_observational_fail_open(tmp_path: Path) -> None:
    import subprocess

    project = "t"
    plans_dir = tmp_path / "Plan" / project / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "Plan_N0001.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    submission = runtime / "state" / "tasks" / project / "submission.json"
    submission.parent.mkdir(parents=True)
    submission.write_text('{"status":"submitted"}\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_stop.py")],
        input=json.dumps({}),
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(
            FOUNDATION_REPO_ROOT=str(tmp_path),
            FOUNDATION_PROJECT_ID=project,
            HARNESS_RUNTIME_ROOT=str(runtime),
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert "harness gate skipped" in result.stderr
    observation = json.loads(
        (runtime / "state" / "tasks" / project / "hook-stop-dispatch.json").read_text(
            encoding="utf-8"
        )
    )
    assert observation["status"] == "skipped"
    assert observation["reason"] == "FileNotFoundError"


def test_hook_stop_responsibility_classification_is_explicit() -> None:
    hook_stop = _load_hook_stop()
    responsibilities = hook_stop.hook_responsibilities()

    assert responsibilities["strict_enforcement"] == []
    assert "runtime_root_discovery" in responsibilities["observational"]
    assert "submission_detection" in responsibilities["observational"]
    assert "submitted_dispatch" in responsibilities["observational"]


def test_hook_stop_stop_hook_active_guard_exits_0(tmp_path: Path) -> None:
    """stop_hook_active=true must exit 0 unconditionally, even for gated projects."""
    import subprocess

    # Create a Plan_N file so the project would be gated (no index.yaml → gates on file presence).
    project = "t"
    plans_dir = tmp_path / "Plan" / project / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "Plan_N0001.md").write_text(
        "---\nstatus: active\ntitle: test plan\n---\n", encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_stop.py")],
        input=json.dumps({"stop_hook_active": True}),
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(
            FOUNDATION_REPO_ROOT=str(tmp_path),
            FOUNDATION_PROJECT_ID=project,
        ),
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# hook_session_start.py
# ---------------------------------------------------------------------------


def test_hook_session_start_empty_stdin_no_issues_exits_0(tmp_path: Path) -> None:
    """With no open-issues.json the script is silent and exits 0."""
    import subprocess

    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "hook_session_start.py")],
        input="",
        capture_output=True,
        text=True,
        timeout=30,
        env=_env(
            FOUNDATION_REPO_ROOT=str(tmp_path),
            FOUNDATION_PROJECT_ID="t",
        ),
    )
    assert result.returncode == 0
    assert result.stdout == ""

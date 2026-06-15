"""Subprocess-level tests for the three hook scripts.

Tests exercise:
  - hook_post_tool_use.py: happy path writes trajectory JSONL
  - hook_post_tool_use.py: malformed stdin exits 0 and writes nothing
  - hook_stop.py: ungated project exits 0 with empty stdout
  - hook_stop.py: stop_hook_active guard exits 0 (even when gated)
  - hook_session_start.py: empty stdin + no issues file exits 0
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"


def _env(**overrides: str) -> dict[str, str]:
    """Merge os.environ with overrides so scripts can find the venv / python paths."""
    return {**os.environ, **overrides}


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

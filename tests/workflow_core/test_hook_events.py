from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from workflow_core.hook_events import event_dict_from_post_tool_use, from_post_tool_use

_SRC = Path(__file__).resolve().parents[2] / "src"

TS = "2026-06-11T00:00:00Z"


def test_edit_tool_maps_file_path_target() -> None:
    event = from_post_tool_use(
        {
            "session_id": "sess-1",
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/feature/core.py", "old_string": "x"},
            "tool_response": {"is_error": False},
        },
        ts=TS,
    )
    assert event.run_id == "sess-1"
    assert event.kind == "tool_call"
    assert event.tool == "Edit"
    assert event.target == "src/feature/core.py"
    assert event.args_hash.startswith("sha256:")
    assert event.exit_code is None


def test_bash_tool_maps_command_head_and_exit_code() -> None:
    event = from_post_tool_use(
        {
            "session_id": "s",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest -q tests/"},
            "tool_response": {"exit_code": 1},
        },
        ts=TS,
    )
    assert event.tool == "Bash"
    assert event.target == "pytest"
    assert event.exit_code == 1


def test_skill_tool_maps_skill_name() -> None:
    event = from_post_tool_use(
        {"session_id": "s", "tool_name": "Skill", "tool_input": {"name": "code-review"}},
        ts=TS,
    )
    assert event.tool == "Skill"
    assert event.target == "code-review"


def test_error_response_without_exit_code_is_failure() -> None:
    event = from_post_tool_use(
        {
            "session_id": "s",
            "tool_name": "Bash",
            "tool_input": {"command": "false"},
            "tool_response": {"is_error": True},
        },
        ts=TS,
    )
    assert event.exit_code == 1


def test_missing_fields_are_tolerated() -> None:
    event = from_post_tool_use({"session_id": "s"}, ts=TS)
    assert event.tool == ""
    assert event.target == ""
    assert event.run_id == "s"


# ---------------------------------------------------------------------------
# event_dict_from_post_tool_use parity tests
# ---------------------------------------------------------------------------

_BASH_PAYLOAD = {
    "session_id": "sess-abc",
    "tool_name": "Bash",
    "tool_input": {"command": "uv run pytest -q"},
    "tool_response": {"exit_code": 0},
}


def test_event_dict_parity_with_model_dump() -> None:
    """event_dict_from_post_tool_use must produce the same keys/values as model_dump()."""
    raw = event_dict_from_post_tool_use(_BASH_PAYLOAD, ts=TS)
    expected = from_post_tool_use(_BASH_PAYLOAD, ts=TS).model_dump()
    assert raw == expected


def test_event_dict_exit_code_none_when_missing() -> None:
    payload = {
        "session_id": "s",
        "tool_name": "Edit",
        "tool_input": {"file_path": "foo.py"},
        "tool_response": {"is_error": False},
    }
    raw = event_dict_from_post_tool_use(payload, ts=TS)
    assert raw["exit_code"] is None


def test_event_dict_exit_code_one_when_is_error() -> None:
    payload = {
        "session_id": "s",
        "tool_name": "Bash",
        "tool_input": {"command": "false"},
        "tool_response": {"is_error": True},
    }
    raw = event_dict_from_post_tool_use(payload, ts=TS)
    assert raw["exit_code"] == 1


def test_stdlib_only_import_guarantee() -> None:
    """hook_events and plans must be importable without pydantic in sys.modules."""
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(_SRC)!r}); "
        "import workflow_core.hook_events, workflow_core.plans; "
        "assert 'pydantic' not in sys.modules, "
        "'pydantic was imported: ' + str([k for k in sys.modules if k.startswith('pydantic')])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"

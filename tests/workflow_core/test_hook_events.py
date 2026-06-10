from __future__ import annotations

from workflow_core.hook_events import from_post_tool_use

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

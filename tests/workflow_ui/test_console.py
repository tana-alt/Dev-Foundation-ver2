from src.workflow_ui import build_console_snapshot, load_sanitized_runs, render_console
from src.workflow_ui.console import assert_sanitized


def test_console_renders_expected_mock_screens() -> None:
    output = render_console()

    assert "Work queue:" in output
    assert "Proposal review:" in output
    assert "Approved contract:" in output
    assert "Execution run:" in output
    assert "Verification:" in output
    assert "Handoff:" in output
    assert "Real App Server smoke: skipped" in output


def test_console_snapshot_uses_sanitized_fixture_refs() -> None:
    snapshot = build_console_snapshot()

    assert snapshot["real_app_server_smoke"] == "skipped_human_gate_required"
    for run in load_sanitized_runs():
        assert_sanitized(run)
        assert run["runner"] == "mock"
        assert run["external_refs"][0].startswith("app-server-thread:")


def test_sanitized_fixture_does_not_expose_denied_context_markers() -> None:
    fixture_text = repr(load_sanitized_runs()).lower()

    for marker in (
        "raw_thread_body",
        "raw_terminal_log",
        "credential",
        "browser_session",
        "local_runtime_state",
    ):
        assert marker not in fixture_text

import subprocess
import sys
from pathlib import Path

from app.workflow_console.__main__ import main
from src.workflow_ui import (
    build_console_snapshot,
    load_sanitized_runs,
    render_console,
    render_html_console,
)
from src.workflow_ui.console import assert_sanitized

ROOT = Path(__file__).resolve().parents[2]


def test_console_renders_expected_mock_screens() -> None:
    output = render_console()

    assert "Work queue:" in output
    assert "Proposal review:" in output
    assert "Approved contract:" in output
    assert "Execution run:" in output
    assert "App Server:" in output
    assert "App Server gate:" in output
    assert "Verification:" in output
    assert "Handoff:" in output
    assert "Real App Server smoke: skipped" in output


def test_console_snapshot_uses_sanitized_fixture_refs() -> None:
    snapshot = build_console_snapshot()

    assert snapshot["real_app_server_smoke"] == "skipped_human_gate_required"
    for run in load_sanitized_runs():
        assert_sanitized(run)
        assert run["runner"] == "app_server"
        assert run["external_refs"][0].startswith("app-server-thread:")
        assert run["app_server"]["thread_ref"].startswith("app-server-thread:")
        assert run["app_server"]["events"][0]["external_event_ref"].startswith("app-server-event:")


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


def test_console_renders_accessible_static_html() -> None:
    html = render_html_console()

    assert "<!doctype html>" in html
    assert "<main>" in html
    assert 'aria-label="App Server integration"' in html
    assert "Workflow Core authority" in html
    assert "app-server-thread:demo-thread" in html
    assert "approval_requested" in html


def test_console_html_escapes_sanitized_fixture_content() -> None:
    run = load_sanitized_runs()[0]
    run["title"] = "<script>alert('x')</script>"

    html = render_html_console([run])

    assert "<script>" not in html
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html


def test_console_cli_writes_html(tmp_path: Path) -> None:
    output_path = tmp_path / "workflow-console.html"

    main(["--format", "html", "--output", str(output_path)])

    output = output_path.read_text()
    assert output.startswith("<!doctype html>")
    assert "Workflow Console" in output


def test_console_script_writes_html_when_run_directly(tmp_path: Path) -> None:
    output_path = tmp_path / "workflow-console.html"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run-workflow-console.py"),
            "--format",
            "html",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""
    assert output_path.read_text().startswith("<!doctype html>")

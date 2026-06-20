from __future__ import annotations

from pathlib import Path

from .conftest import TASK_ID, load_runtime_json, run_harness


def test_expected_paths_outside_change_is_warning_not_block(harness_repo: Path) -> None:
    (harness_repo / "tests").mkdir()
    (harness_repo / "tests" / "test_app.py").write_text("def test_app():\n    assert True\n")

    verified = run_harness(harness_repo, "verify", TASK_ID)

    assert verified.returncode == 0, verified.stdout + verified.stderr
    result = load_runtime_json(harness_repo, "verify-result.json")
    assert result["status"] == "pass"
    assert result["scope"]["violation_count"] == 0
    assert result["impact_result"]["status"] == "review_required"
    assert result["impact_result"]["findings"] == [
        {
            "path": "tests/test_app.py",
            "reason": "outside_expected_paths",
            "severity": "warning",
        }
    ]


def test_forbidden_path_is_block(harness_repo: Path) -> None:
    (harness_repo / "forbidden").mkdir()
    (harness_repo / "forbidden" / "secret.txt").write_text("do not ship\n")

    verified = run_harness(harness_repo, "verify", TASK_ID)

    assert verified.returncode == 1
    result = load_runtime_json(harness_repo, "verify-result.json")
    assert result["status"] == "fail"
    assert result["scope"]["violation_count"] == 1
    assert result["impact_result"]["status"] == "blocked"
    assert result["impact_result"]["findings"] == [
        {
            "path": "forbidden/secret.txt",
            "reason": "forbidden_path",
            "severity": "block",
        }
    ]


def test_reader_scope_alias_does_not_block_warning_only_scope(harness_repo: Path) -> None:
    (harness_repo / "tests").mkdir()
    (harness_repo / "tests" / "test_app.py").write_text("def test_app():\n    assert True\n")

    assert run_harness(harness_repo, "verify", TASK_ID).returncode == 0
    verdict = run_harness(harness_repo, "review", TASK_ID, "--run", "reader-scope", role="reviewer")

    assert verdict.returncode == 0, verdict.stdout + verdict.stderr
    review = load_runtime_json(harness_repo, "reviews/reader-scope.json")
    assert review["verdict"] == "approve"

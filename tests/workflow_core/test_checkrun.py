from __future__ import annotations

import shlex
import sys
from pathlib import Path

from workflow_core.checkrun import run_checks
from workflow_core.runstore import RunStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PY = shlex.quote(sys.executable)
OK_CMD = f"{PY} -c pass"
FAIL_SNIPPET = shlex.quote("import sys; print('boom'); sys.exit(2)")
FAIL_CMD = f"{PY} -c {FAIL_SNIPPET}"

# ---------------------------------------------------------------------------
# run_checks
# ---------------------------------------------------------------------------


def test_all_pass_overall_pass(tmp_path: Path) -> None:
    report = run_checks([("test", OK_CMD), ("lint", OK_CMD)], cwd=tmp_path)
    assert report.overall == "pass"
    assert [r.status for r in report.results] == ["pass", "pass"]
    assert all(r.duration_s >= 0 for r in report.results)


def test_one_failure_fails_overall_and_captures_tail(tmp_path: Path) -> None:
    report = run_checks([("test", OK_CMD), ("typecheck", FAIL_CMD)], cwd=tmp_path)
    assert report.overall == "fail"
    failed = report.results[1]
    assert failed.status == "fail"
    assert failed.failures[0] == "exit 2"
    assert "boom" in "\n".join(failed.failures)


def test_missing_binary_is_failure(tmp_path: Path) -> None:
    report = run_checks([("test", "definitely-not-a-binary-xyz")], cwd=tmp_path)
    assert report.overall == "fail"
    assert report.results[0].failures


def test_payload_shape(tmp_path: Path) -> None:
    report = run_checks([("test", OK_CMD), ("lint", FAIL_CMD)], cwd=tmp_path)
    payload = report.to_payload()
    assert payload["tool"] == "check"
    assert payload["overall"] == "fail"
    results = payload["results"]
    assert isinstance(results, dict)
    assert set(results) == {"test", "lint"}
    assert "failures" not in results["test"]
    assert "failures" in results["lint"]


# ---------------------------------------------------------------------------
# record_report
# ---------------------------------------------------------------------------


def test_record_report_roundtrip(tmp_path: Path) -> None:
    from workflow_core.checkrun import record_report

    report = run_checks([("test", OK_CMD), ("lint", FAIL_CMD)], cwd=tmp_path)
    with RunStore(tmp_path / "runs.db") as store:
        record_report(store, "cand_1", report)
        rows = store.checks_for_run("cand_1")
        assert [row.name for row in rows] == ["test", "lint"]
        assert rows[0].status == "pass"
        assert rows[1].status == "fail"
        assert rows[1].failures[0] == "exit 2"

from pathlib import Path

from test_agent_operational_helpers import ROOT, run_operational_check, write_file


def test_review_convergence_passes_current_templates() -> None:
    result = run_operational_check("check-review-convergence.py", ROOT)

    assert result.returncode == 0


def test_convergence_complete_rejects_unresolved_high_items(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/convergence-decision-record.yaml",
        """schema_version: "0.1"
record_type: convergence_decision_record
status: draft
open_items:
  critical_inc: 0
  high_inc: 1
  unresolved_fix: 0
decision:
  status: complete
""",
    )

    result = run_operational_check("check-review-convergence.py", tmp_path)

    assert result.returncode == 1
    assert "complete cannot have unresolved critical/high INC or FIX" in result.stderr


def test_review_mode_must_match_record_type(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/narrow-review-record.yaml",
        """schema_version: "0.1"
record_type: narrow_review_record
status: draft
identity:
  review_mode: wide
verdict:
  status: pass
findings: []
""",
    )

    result = run_operational_check("check-review-convergence.py", tmp_path)

    assert result.returncode == 1
    assert "review_mode must be narrow" in result.stderr

from pathlib import Path

from test_agent_operational_helpers import ROOT, run_operational_check, write_file


def envelope(
    status: str,
    *,
    missing_context: bool = False,
    completion_support: bool = False,
) -> str:
    missing = (
        """
    - FOUNDATION_LANE_MAP_REF
"""
        if missing_context
        else "[]\n"
    )
    return f"""schema_version: "0.1"
record_type: check_result_envelope
status: draft
checker:
  name: example
  version: "0.1"
  mode: local
identity:
  project_id: example
  work_id: work
  created_at: "2026-06-08T00:00:00Z"
result:
  status: {status}
  reason: "reason"
  severity: high
  completion_support: {str(completion_support).lower()}
scope:
  checked_paths: []
  required_context: []
  missing_context: {missing}
  denied_context_checked:
    - secrets
    - runtime_state
    - broad_repo_scan
evidence:
  source_refs:
    - "AGENTS.md"
  output_ref: ""
  source_snapshot_lock_ref: ""
next_action:
  type: residual_risk
  target_ref: ""
"""


def test_check_result_envelope_passes_current_template() -> None:
    result = run_operational_check("check-result-envelope.py", ROOT)

    assert result.returncode == 0


def test_required_context_missing_cannot_support_completion(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/check-result-envelope.yaml",
        envelope("required_context_missing", missing_context=True, completion_support=True),
    )

    result = run_operational_check("check-result-envelope.py", tmp_path)

    assert result.returncode == 1
    assert "required_context_missing cannot support completion" in result.stderr


def test_pass_cannot_hide_missing_context(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/check-result-envelope.yaml",
        envelope("pass", missing_context=True, completion_support=True),
    )

    result = run_operational_check("check-result-envelope.py", tmp_path)

    assert result.returncode == 1
    assert "pass result must not have missing_context" in result.stderr

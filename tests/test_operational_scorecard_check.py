from pathlib import Path

from test_agent_operational_helpers import ROOT, run_operational_check, write_file


def scorecard(*, overall_claim: bool = False, violation_count: int = 0) -> str:
    claim_value = str(overall_claim).lower()
    return f"""schema_version: "0.1"
record_type: operational_scorecard
status: draft
scores:
  context_slimming:
    score: 10.0
    required_min: 9.5
    violations:
      broad_repo_scan: {violation_count}
      unexplained_context_expansion: 0
      over_budget_without_override: 0
      active_doc_budget_violation: 0
      skill_line_budget_violation: 0
      missing_denied_context_entry: 0
  robustness:
    score: 10.0
    required_min: 9.5
    violations:
      required_context_missing_treated_as_not_applicable: 0
      not_run_reported_as_pass: 0
      human_gate_terminal_blocked_misuse: 0
      high_or_critical_risk_without_owner_or_human_path: 0
      hook_wired_before_false_positive_review: 0
      final_handoff_complete_with_unresolved_fix: 0
  auditability:
    score: 10.0
    required_min: 9.5
    violations:
      important_record_without_source_snapshot: 0
      important_snapshot_without_hash: 0
      verification_without_command_or_exit_code: 0
      final_handoff_without_audit_index: 0
      traceability_matrix_missing_required_id_family: 0
      residual_risk_without_next_flow_seed: 0
fixtures:
  required_fixture_set_present: false
claim:
  can_claim_95_plus:
    context_slimming: {claim_value}
    robustness: {claim_value}
    auditability: {claim_value}
    overall: {claim_value}
  audit_trail_index_ref: ""
"""


def test_operational_scorecard_passes_current_template() -> None:
    result = run_operational_check("check-operational-scorecard.py", ROOT)

    assert result.returncode == 0


def test_operational_scorecard_rejects_manual_score_inflation(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/operational-scorecard.yaml",
        scorecard(violation_count=1),
    )

    result = run_operational_check("check-operational-scorecard.py", tmp_path)

    assert result.returncode == 1
    assert "score exceeds recomputed score" in result.stderr


def test_operational_scorecard_claim_requires_fixtures(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/operational-scorecard.yaml",
        scorecard(overall_claim=True),
    )

    result = run_operational_check("check-operational-scorecard.py", tmp_path)

    assert result.returncode == 1
    assert "9.5+ claim missing fixture" in result.stderr

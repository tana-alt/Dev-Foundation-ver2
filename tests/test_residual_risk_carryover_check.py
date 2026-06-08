from pathlib import Path

from test_agent_operational_helpers import ROOT, run_operational_check, write_file


def test_residual_risk_carryover_passes_current_templates() -> None:
    result = run_operational_check("check-residual-risk-carryover.py", ROOT)

    assert result.returncode == 0


def test_high_risk_requires_owner_or_human_path(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/residual-risk-carryover-record.yaml",
        """schema_version: "0.1"
record_type: residual_risk_carryover_record
status: draft
risks:
  - id: RISK-001
    severity: high
    type: human_gate_pending
    summary: "human review pending"
    affected_requirement_ids: []
    source_refs:
      - "artifact/example/output/final-handoffs/work.yaml"
    owner_lane: ""
    human_decision_required: false
    next_flow_seed:
      problem: "review"
      source_refs:
        - "artifact/example/output/final-handoffs/work.yaml"
""",
    )

    result = run_operational_check("check-residual-risk-carryover.py", tmp_path)

    assert result.returncode == 1
    assert "high/critical risk needs owner or human path" in result.stderr


def test_final_handoff_rejects_terminal_blocked(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/final-handoff-record.yaml",
        """schema_version: "0.1"
record_type: final_handoff_record
status: draft
completion:
  decision: blocked
human_gate:
  required: true
  status: required
carryover: {}
""",
    )

    result = run_operational_check("check-residual-risk-carryover.py", tmp_path)

    assert result.returncode == 1
    assert "must not use terminal blocked" in result.stderr

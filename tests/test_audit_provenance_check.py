from pathlib import Path

from test_agent_operational_helpers import ROOT, run_operational_check, write_file


def test_audit_provenance_passes_current_templates() -> None:
    result = run_operational_check("check-audit-provenance.py", ROOT)

    assert result.returncode == 0


def test_source_snapshot_unknown_hash_requires_risk_ref(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/source-snapshot-lock.yaml",
        """schema_version: "0.1"
record_type: source_snapshot_lock
status: draft
hash_policy:
  unknown_hash_requires_residual_risk: true
source_snapshots:
  - ref: "AGENTS.md"
    content_hash: "sha256:unknown"
    hash_status: unknown
    local_file: true
residual_risk_refs: []
""",
    )

    result = run_operational_check("check-audit-provenance.py", tmp_path)

    assert result.returncode == 1
    assert "unknown hash needs residual risk ref" in result.stderr


def test_final_handoff_requires_audit_index(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/final-handoff-record.yaml",
        """schema_version: "0.1"
record_type: final_handoff_record
status: draft
completion:
  decision: complete
human_gate:
  required: false
carryover: {}
""",
    )

    result = run_operational_check("check-audit-provenance.py", tmp_path)

    assert result.returncode == 1
    assert "requires audit_trail_index_ref" in result.stderr

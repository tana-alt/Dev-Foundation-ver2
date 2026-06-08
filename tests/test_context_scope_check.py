from pathlib import Path

from test_agent_operational_helpers import run_operational_check, write_file


def context_manifest(source_ref: str, *, expansion: bool = False) -> str:
    expansion_text = (
        f"""
    - ref: "{source_ref}"
      reason: "Explicit bounded expansion."
"""
        if expansion
        else "[]\n"
    )
    return f"""schema_version: "0.1"
record_type: context_scope_manifest
status: draft
identity:
  project_id: example
  work_id: work
  agent_role: implementer
  created_at: "2026-06-08T00:00:00Z"
scope:
  task_intent: "task"
  selected_skill_refs:
    - ".agents/skills/scope-routing-governance/SKILL.md"
  source_refs_opened:
    - ref: "{source_ref}"
      reason: "needed"
  allowed_write_targets:
    - "templates/"
  denied_context:
    - broad_repo_scan
    - secrets
    - runtime_state
  context_expansion: {expansion_text}
  unopened_optional_refs: []
budget:
  max_selected_skills: 2
  max_source_refs: 6
  max_reference_docs: 2
  broad_repo_scan_allowed: false
source_snapshot: []
handoff:
  next_action: continue
  notes: ""
"""


def test_context_scope_accepts_explicit_expansion(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/context-scope-manifest.yaml",
        context_manifest(".", expansion=True),
    )

    result = run_operational_check("check-context-scope.py", tmp_path)

    assert result.returncode == 0


def test_context_scope_rejects_broad_ref_without_expansion(tmp_path: Path) -> None:
    write_file(tmp_path / "templates/context-scope-manifest.yaml", context_manifest("."))

    result = run_operational_check("check-context-scope.py", tmp_path)

    assert result.returncode == 1
    assert "broad source ref lacks expansion reason" in result.stderr


def test_context_scope_rejects_missing_denied_context(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/context-scope-manifest.yaml",
        context_manifest("AGENTS.md").replace("    - secrets\n", ""),
    )

    result = run_operational_check("check-context-scope.py", tmp_path)

    assert result.returncode == 1
    assert "scope.denied_context missing" in result.stderr


def test_budget_override_requires_allowed_by(tmp_path: Path) -> None:
    write_file(
        tmp_path / "templates/budget-override-record.yaml",
        """schema_version: "0.1"
record_type: budget_override_record
status: draft
override:
  reason: "Wide review needs neighboring lane refs."
  allowed_by: []
  requested_budget:
    broad_repo_scan_allowed: false
scope_control:
  still_forbidden:
    - broad_repo_scan
    - secrets
    - runtime_state
""",
    )

    result = run_operational_check("check-context-scope.py", tmp_path)

    assert result.returncode == 1
    assert "override.allowed_by must be non-empty" in result.stderr

#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))

ACTIVE_GOVERNANCE_SKILLS = {
    "scope-routing-governance",
    "spec-authority-governance",
}

RETIRED_GOVERNANCE_SKILLS = {
    "review-fix-convergence-governance",
}

ACTIVE_SKILL_REQUIRED_SECTIONS = (
    "## Purpose",
    "## Use When",
    "## Do Not Use When",
    "## Method",
    "## Output",
)

REQUIRED_DENIED_CONTEXT = {"secrets", "runtime_state", "broad_repo_scan"}
CHECK_STATUSES = {"pass", "fail", "not_applicable", "required_context_missing", "not_run"}
CHECK_SEVERITIES = {"none", "low", "medium", "high", "critical"}
CHECK_NEXT_ACTIONS = {
    "none",
    "rework",
    "residual_risk",
    "human_review_required",
    "add_required_context",
}
RISK_SEVERITIES = {"low", "medium", "high", "critical"}
RISK_TYPES = {
    "human_gate_pending",
    "deferred_implementation",
    "external_environment_unverified",
    "accepted_partial_coverage",
    "future_decision_required",
    "semantic_conflict_unverified",
}
REVIEW_MODES = {"narrow", "wide", "security", "fix"}
REVIEW_STATUSES = {"pass", "pass_with_risk", "rework_required", "human_review_required"}
CONVERGENCE_STATUSES = {
    "complete",
    "human_review_required",
    "complete_with_residual_risk",
    "rework_required",
}
TRACEABILITY_STATUSES = {"covered", "gap", "carried_risk"}
TRACEABILITY_PREFIXES = ("REQ-", "AC-", "NFR-", "EXC-", "SEC-", "DATA-", "API-", "TEST-")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
INDEX_ENTRY_RE = re.compile(r"^- `([^`]+)`$")


def load_yaml(path: Path) -> dict[str, Any]:
    raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        raise ValueError(f"{path}: expected YAML mapping")
    return cast(dict[str, Any], raw_data)


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def mappings(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [cast(dict[str, Any], item) for item in value if isinstance(item, dict)]


def strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def bool_value(value: object) -> bool:
    return value is True


def add_issue(issues: list[str], label: str, message: str) -> None:
    issues.append(f"{label}: {message}")


def yaml_paths(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(path for path in root.glob(pattern) if path.is_file())
    return sorted(dict.fromkeys(paths))


def ref_from_item(item: object) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return string(item.get("ref"))
    return ""


def is_broad_ref(ref: str) -> bool:
    normalized = ref.strip().removesuffix("/").lower()
    broad_refs = {
        "",
        ".",
        "./",
        "repo root",
        "repository root",
        "all files",
        "all tests",
        "all docs",
        "docs",
        "docs/reference",
        "archive",
        "runtime",
        "source-docs",
    }
    return normalized in broad_refs


def has_expansion_for_ref(expansions: list[dict[str, Any]], ref: str) -> bool:
    for expansion in expansions:
        if ref_from_item(expansion) == ref and string(expansion.get("reason")):
            return True
    return False


def parse_skill_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing YAML front matter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError("invalid YAML front matter")
    raw_data = yaml.safe_load(parts[1])
    if not isinstance(raw_data, dict):
        raise ValueError("front matter must be mapping")
    return cast(dict[str, Any], raw_data)


def skill_index_entries(index_text: str) -> list[str]:
    return [
        match.group(1) for line in index_text.splitlines() if (match := INDEX_ENTRY_RE.match(line))
    ]


def validate_skill_routes(root: Path) -> list[str]:
    issues: list[str] = []
    skill_root = root / ".agents" / "skills"
    index = (skill_root / "SKILL_INDEX.md").read_text(encoding="utf-8")
    indexed = set(skill_index_entries(index))
    skill_dirs = sorted(path for path in skill_root.iterdir() if path.is_dir())
    actual = {path.name for path in skill_dirs}

    if indexed != actual:
        add_issue(
            issues,
            ".agents/skills/SKILL_INDEX.md",
            f"index entries must match skill directories: missing={sorted(actual - indexed)} "
            f"extra={sorted(indexed - actual)}",
        )

    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        label = rel(skill_file, root)
        if not skill_file.is_file():
            add_issue(issues, rel(skill_dir, root), "missing SKILL.md")
            continue
        try:
            metadata = parse_skill_frontmatter(skill_file)
        except ValueError as exc:
            add_issue(issues, label, str(exc))
            continue
        name = string(metadata.get("name"))
        description = string(metadata.get("description"))
        if name != skill_dir.name:
            add_issue(issues, label, "front matter name must match directory")
        if not description:
            add_issue(issues, label, "description must be non-empty")

        text = skill_file.read_text(encoding="utf-8")
        if skill_dir.name in ACTIVE_GOVERNANCE_SKILLS:
            if len(text.splitlines()) > 140:
                add_issue(issues, label, "governance skill exceeds 140-line budget")
            for section in ACTIVE_SKILL_REQUIRED_SECTIONS:
                if section not in text:
                    add_issue(issues, label, f"missing required section {section}")
            for template_ref in re.findall(r"`(templates/[^`]+)`", text):
                if not (root / template_ref).exists():
                    add_issue(issues, label, f"references missing template {template_ref}")
        elif skill_dir.name in RETIRED_GOVERNANCE_SKILLS:
            lowered = text.lower()
            if "retired" not in lowered or "do not use" not in lowered:
                add_issue(issues, label, "retired governance skill must state retired/do not use")

    return issues


def validate_context_scope_data(data: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    scope = mapping(data.get("scope"))
    budget = mapping(data.get("budget"))
    selected_skill_refs = strings(scope.get("selected_skill_refs"))
    source_refs = [ref_from_item(item) for item in mappings(scope.get("source_refs_opened"))]
    denied_context = set(strings(scope.get("denied_context")))
    expansions = mappings(scope.get("context_expansion"))

    missing_denied = sorted(REQUIRED_DENIED_CONTEXT - denied_context)
    if missing_denied:
        add_issue(issues, label, f"scope.denied_context missing {missing_denied}")

    max_skills = int(budget.get("max_selected_skills", 0) or 0)
    max_refs = int(budget.get("max_source_refs", 0) or 0)
    max_reference_docs = int(budget.get("max_reference_docs", 0) or 0)
    broad_allowed = bool_value(budget.get("broad_repo_scan_allowed"))

    if max_skills < 1 or len(selected_skill_refs) > max_skills:
        add_issue(issues, label, "selected skills exceed budget or budget is invalid")
    if max_refs < 1 or len(source_refs) > max_refs:
        add_issue(issues, label, "source refs exceed budget or budget is invalid")

    reference_doc_count = sum(1 for ref in source_refs if ref.startswith("docs/reference/"))
    if reference_doc_count > max_reference_docs:
        add_issue(issues, label, "reference docs exceed budget")

    for ref in source_refs:
        if is_broad_ref(ref) and not broad_allowed and not has_expansion_for_ref(expansions, ref):
            add_issue(issues, label, f"broad source ref lacks expansion reason: {ref!r}")

    for expansion in expansions:
        if not ref_from_item(expansion) or not string(expansion.get("reason")):
            add_issue(issues, label, "context_expansion entries require ref and reason")
    return issues


def validate_budget_override_data(data: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    override = mapping(data.get("override"))
    scope_control = mapping(data.get("scope_control"))
    requested = mapping(override.get("requested_budget"))
    allowed_by = strings(override.get("allowed_by"))
    still_forbidden = set(strings(scope_control.get("still_forbidden")))

    if not string(override.get("reason")):
        add_issue(issues, label, "override.reason is required")
    if not allowed_by:
        add_issue(issues, label, "override.allowed_by must be non-empty")
    missing_forbidden = sorted(REQUIRED_DENIED_CONTEXT - still_forbidden)
    if missing_forbidden:
        add_issue(issues, label, f"scope_control.still_forbidden missing {missing_forbidden}")
    if requested.get("broad_repo_scan_allowed") is True:
        add_issue(issues, label, "budget override must not allow broad_repo_scan")
    return issues


def validate_context_scope(root: Path) -> list[str]:
    issues: list[str] = []
    paths = yaml_paths(
        root,
        (
            "templates/context-scope-manifest.yaml",
            "templates/budget-override-record.yaml",
            "artifact/*/evidence/context-scope-*.yaml",
            "artifact/*/evidence/budget-override-*.yaml",
        ),
    )
    for path in paths:
        label = rel(path, root)
        data = load_yaml(path)
        record_type = string(data.get("record_type"))
        if path.name == "budget-override-record.yaml" or record_type == "budget_override_record":
            issues.extend(validate_budget_override_data(data, label))
        else:
            issues.extend(validate_context_scope_data(data, label))
    return issues


def validate_check_result_envelope_data(data: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    result = mapping(data.get("result"))
    scope = mapping(data.get("scope"))
    evidence = mapping(data.get("evidence"))
    next_action = mapping(data.get("next_action"))
    status = string(result.get("status"))
    severity = string(result.get("severity"))
    source_refs = strings(evidence.get("source_refs"))
    missing_context = strings(scope.get("missing_context"))

    if status not in CHECK_STATUSES:
        add_issue(issues, label, f"invalid result.status {status!r}")
    if severity not in CHECK_SEVERITIES:
        add_issue(issues, label, f"invalid result.severity {severity!r}")
    if status != "pass" and not string(result.get("reason")):
        add_issue(issues, label, "non-pass result requires reason")
    if status == "pass" and missing_context:
        add_issue(issues, label, "pass result must not have missing_context")
    incomplete_status = status in {"required_context_missing", "not_run"}
    if incomplete_status and result.get("completion_support") is True:
        add_issue(issues, label, f"{status} cannot support completion")
    if status == "not_applicable" and missing_context:
        add_issue(issues, label, "missing required context is not not_applicable")
    if status == "required_context_missing" and not missing_context:
        add_issue(issues, label, "required_context_missing needs missing_context")
    if status in {"fail", "required_context_missing", "not_run"} and severity == "none":
        add_issue(issues, label, "failing or incomplete results need non-none severity")
    if status != "not_applicable" and not source_refs:
        add_issue(issues, label, "evidence.source_refs must be non-empty")
    if string(next_action.get("type")) not in CHECK_NEXT_ACTIONS:
        add_issue(issues, label, "next_action.type is invalid")
    return issues


def validate_check_result_envelopes(root: Path) -> list[str]:
    issues: list[str] = []
    paths = yaml_paths(
        root,
        (
            "templates/check-result-envelope.yaml",
            "artifact/*/verification/check-result-*.yaml",
        ),
    )
    for path in paths:
        data = load_yaml(path)
        issues.extend(validate_check_result_envelope_data(data, rel(path, root)))
    return issues


def validate_residual_risk_data(data: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    for risk in mappings(data.get("risks")):
        risk_id = string(risk.get("id"))
        severity = string(risk.get("severity"))
        risk_type = string(risk.get("type"))
        source_refs = strings(risk.get("source_refs"))
        next_flow_seed = mapping(risk.get("next_flow_seed"))
        owner_lane = string(risk.get("owner_lane"))
        human_decision_required = bool_value(risk.get("human_decision_required"))
        affected_requirement_ids = strings(risk.get("affected_requirement_ids"))

        if not risk_id.startswith("RISK-"):
            add_issue(issues, label, "risk id must start with RISK-")
        if severity not in RISK_SEVERITIES:
            add_issue(issues, label, f"invalid risk severity {severity!r}")
        if risk_type not in RISK_TYPES:
            add_issue(issues, label, f"invalid risk type {risk_type!r}")
        if not source_refs:
            add_issue(issues, label, f"{risk_id} missing source_refs")
        next_seed_problem = string(next_flow_seed.get("problem"))
        next_seed_refs = strings(next_flow_seed.get("source_refs"))
        if not next_seed_problem or not next_seed_refs:
            add_issue(issues, label, f"{risk_id} missing next_flow_seed")
        if severity in {"high", "critical"} and not owner_lane and not human_decision_required:
            add_issue(issues, label, f"{risk_id} high/critical risk needs owner or human path")
        if risk_type == "deferred_implementation" and not affected_requirement_ids:
            add_issue(issues, label, f"{risk_id} deferred implementation needs requirement IDs")
    if not mappings(data.get("risks")):
        add_issue(issues, label, "risks must be non-empty")
    return issues


def validate_final_handoff_data(
    data: dict[str, Any],
    label: str,
    *,
    audit_required: bool,
) -> list[str]:
    issues: list[str] = []
    completion = mapping(data.get("completion"))
    human_gate = mapping(data.get("human_gate"))
    carryover = mapping(data.get("carryover"))
    next_goal_seed = mapping(carryover.get("next_goal_seed"))
    decision = string(completion.get("decision"))

    if decision == "blocked":
        add_issue(issues, label, "final handoff must not use terminal blocked")
    if decision == "complete_with_residual_risk":
        if not string(carryover.get("residual_risk_ref")):
            add_issue(issues, label, "complete_with_residual_risk needs residual_risk_ref")
        next_goal_problem = string(next_goal_seed.get("problem"))
        next_goal_refs = strings(next_goal_seed.get("source_refs"))
        if not next_goal_problem or not next_goal_refs:
            add_issue(issues, label, "complete_with_residual_risk needs next_goal_seed")
    if (
        human_gate.get("required") is True
        and string(human_gate.get("status")) == "required"
        and decision == "complete"
    ):
        add_issue(issues, label, "complete cannot hide required human gate")
    if audit_required and not string(data.get("audit_trail_index_ref")):
        add_issue(issues, label, "final handoff requires audit_trail_index_ref")
    return issues


def validate_residual_risk(root: Path) -> list[str]:
    issues: list[str] = []
    paths = yaml_paths(
        root,
        (
            "templates/residual-risk-carryover-record.yaml",
            "templates/final-handoff-record.yaml",
            "artifact/*/output/residual-risk/**/*.yaml",
            "artifact/*/output/final-handoffs/**/*.yaml",
        ),
    )
    for path in paths:
        data = load_yaml(path)
        label = rel(path, root)
        record_type = string(data.get("record_type"))
        if path.name == "final-handoff-record.yaml" or record_type == "final_handoff_record":
            issues.extend(validate_final_handoff_data(data, label, audit_required=False))
        else:
            issues.extend(validate_residual_risk_data(data, label))
    return issues


def validate_review_record_data(
    data: dict[str, Any],
    label: str,
    expected_mode: str,
) -> list[str]:
    issues: list[str] = []
    identity = mapping(data.get("identity"))
    verdict = mapping(data.get("verdict"))
    review_mode = string(identity.get("review_mode"))
    if review_mode != expected_mode:
        add_issue(issues, label, f"review_mode must be {expected_mode}")
    if review_mode not in REVIEW_MODES:
        add_issue(issues, label, f"invalid review mode {review_mode!r}")
    if string(verdict.get("status")) not in REVIEW_STATUSES:
        add_issue(issues, label, "invalid verdict.status")
    for finding in mappings(data.get("findings")):
        finding_id = string(finding.get("id"))
        if not finding_id.startswith("REV-"):
            add_issue(issues, label, "finding id must start with REV-")
    return issues


def validate_fix_handoff_data(data: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    if not strings(data.get("source_review_refs")):
        add_issue(issues, label, "source_review_refs must be non-empty")
    if not strings(data.get("must_not_change")):
        add_issue(issues, label, "must_not_change must be non-empty")
    if not strings(data.get("verification_required")):
        add_issue(issues, label, "verification_required must be non-empty")
    for item in mappings(data.get("must_fix")):
        if not string(item.get("id")).startswith("FIX-"):
            add_issue(issues, label, "must_fix id must start with FIX-")
    return issues


def validate_fix_review_data(data: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    identity = mapping(data.get("identity"))
    if string(identity.get("review_mode")) != "fix":
        add_issue(issues, label, "fix review must use review_mode fix")
    new_risk_check = mapping(data.get("new_risk_check"))
    for key, value in new_risk_check.items():
        if value not in {"none", "present"}:
            add_issue(issues, label, f"new_risk_check.{key} must be none or present")
    for item in mappings(data.get("fix_resolution")):
        if not string(item.get("fix_id")).startswith("FIX-"):
            add_issue(issues, label, "fix_resolution fix_id must start with FIX-")
    return issues


def validate_traceability_data(data: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    items = mappings(data.get("items"))
    coverage = mapping(data.get("coverage"))

    for item in items:
        item_id = string(item.get("id"))
        if not item_id.startswith(TRACEABILITY_PREFIXES):
            add_issue(issues, label, f"invalid traceability id {item_id!r}")
        if string(item.get("status")) not in TRACEABILITY_STATUSES:
            add_issue(issues, label, f"invalid traceability status for {item_id}")

    coverage_items = [
        *mappings(coverage.get("functional_requirements")),
        *mappings(coverage.get("non_functional_requirements")),
        *mappings(coverage.get("exception_cases")),
    ]
    for requirement in mappings(coverage.get("functional_requirements")):
        requirement_id = string(requirement.get("requirement_id"))
        if not requirement_id.startswith("REQ-"):
            add_issue(issues, label, f"invalid functional requirement id {requirement_id!r}")
        for acceptance in mappings(requirement.get("acceptance_criteria")):
            ac_id = string(acceptance.get("ac_id"))
            if not ac_id.startswith("AC-"):
                add_issue(issues, label, f"invalid acceptance criterion id {ac_id!r}")
    for requirement in mappings(coverage.get("non_functional_requirements")):
        requirement_id = string(requirement.get("requirement_id"))
        if not requirement_id.startswith("NFR-"):
            add_issue(issues, label, f"invalid non-functional requirement id {requirement_id!r}")
    for exception_case in mappings(coverage.get("exception_cases")):
        case_id = string(exception_case.get("case_id"))
        if not case_id.startswith("EXC-"):
            add_issue(issues, label, f"invalid exception case id {case_id!r}")

    if not items and not coverage_items:
        add_issue(issues, label, "traceability items or coverage must be non-empty")
    return issues


def validate_convergence_data(data: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    open_items = mapping(data.get("open_items"))
    decision = mapping(data.get("decision"))
    status = string(decision.get("status"))
    if status not in CONVERGENCE_STATUSES:
        add_issue(issues, label, "invalid decision.status")
    critical = int(open_items.get("critical_inc", 0) or 0)
    high = int(open_items.get("high_inc", 0) or 0)
    unresolved_fix = int(open_items.get("unresolved_fix", 0) or 0)
    if status == "complete" and (critical or high or unresolved_fix):
        add_issue(issues, label, "complete cannot have unresolved critical/high INC or FIX")
    return issues


def validate_review_convergence(root: Path) -> list[str]:
    issues: list[str] = []
    paths = yaml_paths(
        root,
        (
            "templates/*review-record.yaml",
            "templates/fix-handoff-record.yaml",
            "templates/requirement-traceability-matrix.yaml",
            "templates/convergence-decision-record.yaml",
            "templates/final-handoff-record.yaml",
            "artifact/*/reviews/**/*.yaml",
            "artifact/*/fixes/**/*.yaml",
            "artifact/*/output/traceability/**/*.yaml",
            "artifact/*/output/convergence/**/*.yaml",
            "artifact/*/output/final-handoffs/**/*.yaml",
        ),
    )
    mode_by_name = {
        "narrow-review-record.yaml": "narrow",
        "wide-review-record.yaml": "wide",
        "security-review-record.yaml": "security",
        "fix-review-record.yaml": "fix",
    }
    for path in paths:
        data = load_yaml(path)
        label = rel(path, root)
        record_type = string(data.get("record_type"))
        if path.name in mode_by_name:
            issues.extend(validate_review_record_data(data, label, mode_by_name[path.name]))
        elif record_type in {
            "narrow_review_record",
            "wide_review_record",
            "security_review_record",
        }:
            expected = record_type.removesuffix("_review_record")
            issues.extend(validate_review_record_data(data, label, expected))
        elif path.name == "fix-review-record.yaml" or record_type == "fix_review_record":
            issues.extend(validate_fix_review_data(data, label))
        elif path.name == "fix-handoff-record.yaml" or record_type == "fix_handoff_record":
            issues.extend(validate_fix_handoff_data(data, label))
        elif record_type == "requirement_traceability_matrix":
            issues.extend(validate_traceability_data(data, label))
        elif record_type == "convergence_decision_record":
            issues.extend(validate_convergence_data(data, label))
        elif record_type == "final_handoff_record":
            issues.extend(validate_final_handoff_data(data, label, audit_required=False))
    return issues


def validate_source_snapshot_data(data: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    residual_risk_refs = strings(data.get("residual_risk_refs"))
    policy = mapping(data.get("hash_policy"))
    unknown_requires_risk = policy.get("unknown_hash_requires_residual_risk") is True
    for snapshot in mappings(data.get("source_snapshots")):
        ref = string(snapshot.get("ref"))
        hash_status = string(snapshot.get("hash_status"))
        content_hash = string(snapshot.get("content_hash"))
        local_file = snapshot.get("local_file") is True
        if not ref:
            add_issue(issues, label, "source snapshot ref is required")
        if local_file and hash_status == "present" and not SHA256_RE.match(content_hash):
            add_issue(issues, label, f"{ref} has invalid sha256 hash")
        if (
            local_file
            and hash_status in {"unknown", "unavailable"}
            and unknown_requires_risk
            and not residual_risk_refs
        ):
            add_issue(issues, label, f"{ref} unknown hash needs residual risk ref")
        if hash_status not in {"present", "unknown", "unavailable"}:
            add_issue(issues, label, f"{ref} invalid hash_status")
    if not mappings(data.get("source_snapshots")):
        add_issue(issues, label, "source_snapshots must be non-empty")
    return issues


def validate_audit_trail_data(data: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    audit_trail = mapping(data.get("audit_trail"))
    coverage = mapping(data.get("coverage"))
    required_refs = (
        "context_scope_ref",
        "traceability_ref",
        "convergence_decision_ref",
        "residual_risk_refs",
        "source_snapshot_lock_ref",
        "final_handoff_ref",
    )
    for key in required_refs:
        value = audit_trail.get(key)
        if isinstance(value, list):
            if not value:
                add_issue(issues, label, f"audit_trail.{key} must be non-empty")
        elif not string(value):
            add_issue(issues, label, f"audit_trail.{key} must be non-empty")
    if coverage.get("has_final_handoff") is not True:
        add_issue(issues, label, "coverage.has_final_handoff must be true")
    return issues


def validate_audit_provenance(root: Path) -> list[str]:
    issues: list[str] = []
    paths = yaml_paths(
        root,
        (
            "templates/source-snapshot-lock.yaml",
            "templates/audit-trail-index.yaml",
            "templates/final-handoff-record.yaml",
            "artifact/*/audit/**/*.yaml",
            "artifact/*/output/final-handoffs/**/*.yaml",
        ),
    )
    for path in paths:
        data = load_yaml(path)
        label = rel(path, root)
        record_type = string(data.get("record_type"))
        if record_type == "source_snapshot_lock":
            issues.extend(validate_source_snapshot_data(data, label))
        elif record_type == "audit_trail_index":
            issues.extend(validate_audit_trail_data(data, label))
        elif record_type == "final_handoff_record":
            issues.extend(validate_final_handoff_data(data, label, audit_required=True))
    return issues


SCORE_PENALTIES = {
    "context_slimming": {
        "broad_repo_scan": -3.0,
        "unexplained_context_expansion": -1.5,
        "over_budget_without_override": -1.5,
        "active_doc_budget_violation": -0.75,
        "skill_line_budget_violation": -0.75,
        "missing_denied_context_entry": -1.0,
    },
    "robustness": {
        "required_context_missing_treated_as_not_applicable": -3.0,
        "not_run_reported_as_pass": -3.0,
        "human_gate_terminal_blocked_misuse": -1.0,
        "high_or_critical_risk_without_owner_or_human_path": -2.0,
        "hook_wired_before_false_positive_review": -1.5,
        "final_handoff_complete_with_unresolved_fix": -3.0,
    },
    "auditability": {
        "important_record_without_source_snapshot": -2.0,
        "important_snapshot_without_hash": -1.5,
        "verification_without_command_or_exit_code": -1.5,
        "final_handoff_without_audit_index": -2.0,
        "traceability_matrix_missing_required_id_family": -2.0,
        "residual_risk_without_next_flow_seed": -1.5,
    },
}

REQUIRED_FIXTURE_DIRS = {
    "success_minimal",
    "success_with_wide_review_override",
    "fail_broad_context",
    "fail_required_context_missing",
    "fail_unrun_check_claimed_passed",
    "fail_source_snapshot_missing_hash",
    "residual_human_gate_pending",
    "residual_deferred_implementation",
}


def recompute_score(dimension: str, violations: dict[str, Any]) -> float:
    score = 10.0
    for key, penalty in SCORE_PENALTIES[dimension].items():
        count = int(violations.get(key, 0) or 0)
        score += count * penalty
    return max(0.0, round(score, 2))


def validate_scorecard_data(data: dict[str, Any], label: str, root: Path) -> list[str]:
    issues: list[str] = []
    scores = mapping(data.get("scores"))
    for dimension in SCORE_PENALTIES:
        section = mapping(scores.get(dimension))
        violations = mapping(section.get("violations"))
        recorded_score = float(section.get("score", -1.0) or 0.0)
        recomputed = recompute_score(dimension, violations)
        if recorded_score > recomputed:
            add_issue(issues, label, f"{dimension} score exceeds recomputed score")
        required_min = float(section.get("required_min", 9.5) or 9.5)
        claim_dimension = mapping(data.get("claim")).get("can_claim_95_plus", {})
        if (
            isinstance(claim_dimension, dict)
            and claim_dimension.get(dimension) is True
            and recorded_score < required_min
        ):
            add_issue(issues, label, f"{dimension} claim below required minimum")

    claim = mapping(mapping(data.get("claim")).get("can_claim_95_plus"))
    if claim.get("overall") is True:
        fixtures = mapping(data.get("fixtures"))
        missing_flags = [name for name in REQUIRED_FIXTURE_DIRS if fixtures.get(name) is not True]
        if missing_flags:
            add_issue(issues, label, f"9.5+ claim missing fixture flags {sorted(missing_flags)}")
        fixture_root = root / "tests" / "fixtures" / "agent_ops_95"
        missing_dirs = [
            name for name in REQUIRED_FIXTURE_DIRS if not (fixture_root / name).is_dir()
        ]
        if missing_dirs:
            add_issue(issues, label, f"9.5+ claim missing fixture dirs {sorted(missing_dirs)}")
        if not string(mapping(data.get("claim")).get("audit_trail_index_ref")):
            add_issue(issues, label, "9.5+ claim needs audit_trail_index_ref")
    return issues


def validate_operational_scorecard(root: Path) -> list[str]:
    issues: list[str] = []
    paths = yaml_paths(
        root,
        (
            "templates/operational-scorecard.yaml",
            "artifact/*/audit/operational-scorecard-*.yaml",
        ),
    )
    for path in paths:
        data = load_yaml(path)
        issues.extend(validate_scorecard_data(data, rel(path, root), root))
    return issues


def run_check(name: str, validator: Any, root: Path = ROOT) -> int:
    try:
        issues = validator(root)
    except Exception as exc:  # noqa: BLE001 - CLI should report validation crashes.
        print(f"{name}: failed", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1
    if issues:
        print(f"{name}: failed", file=sys.stderr)
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print(f"{name}: passed")
    return 0

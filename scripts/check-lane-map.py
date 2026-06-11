#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

import yaml

ROOT = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))

SUPPORTED_SCHEMA_VERSIONS = {"0.1"}
VALID_RECORD_STATUSES = {"draft", "active", "review", "complete"}
VALID_LANE_STATUSES = {
    "planned",
    "assigned",
    "in_progress",
    "blocked",
    "ready_for_review",
    "complete",
    "rework",
}
VALID_CONFLICT_POLICIES = {"no_overlap", "report_overlap", "explicitly_scoped"}
VALID_MAP_OWNERS = {"human", "agent", "scheduler"}
VALID_NEXT_ACTIONS = {"complete", "rework", "review", "continue"}
VALID_FRESHNESS_STATES = {
    "current",
    "stale_fast_forwardable",
    "blocked_dirty_primary",
    "blocked_detached_primary",
    "blocked_missing_primary",
    "blocked_diverged_primary",
    "explicit_base_not_primary",
    "not_applicable",
}
BLOCKING_FRESHNESS_STATES = {
    "blocked_dirty_primary",
    "blocked_detached_primary",
    "blocked_missing_primary",
    "blocked_diverged_primary",
}
FRESHNESS_REMOTE_TRACKING_STATES = {
    "current",
    "stale_fast_forwardable",
    "blocked_diverged_primary",
}
BLOCKING_OUTCOMES = {"blocked", "rework"}
LANE_PHASES_REQUIRING_REFS = {
    "lane_mapping",
    "parallel_build",
    "parallel_review",
    "integration_review",
    "inconsistency_check",
    "rework_execution",
    "convergence_check",
    "final_handoff",
    "human_final_review",
    "complete",
}
PR_HANDOFF_LABEL_MARKERS = {
    "pr_handoff",
    "pull_request_handoff",
    "review_handoff",
}
REQUIRED_PR_HANDOFF_FIELDS = {
    "owned_source_branch",
    "intended_target_branch",
    "base_ref",
    "merge_target",
    "branch_worktree_ownership",
    "canonical_primary_freshness_result",
    "stale_merge_target_handling",
}
PR_HANDOFF_TRIGGER_FIELDS = REQUIRED_PR_HANDOFF_FIELDS - {"base_ref", "merge_target"}
VALID_STALE_MERGE_TARGET_HANDLING = {
    "checked_against_newer_target",
    "requires_rework",
    "explicit_residual_risk",
    "not_applicable",
}
REQUIRED_HANDOFF_EVIDENCE = {"source_refs", "changed_paths", "verification_results"}
REQ_ID_PREFIX = "REQ-"
REQ_ID_RE = re.compile(r"\bREQ-\d+\b")
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TEMPLATE_PLACEHOLDERS = {"<work-id>", "<project-id>", "<repo>", "<short-slug>"}


@dataclass(frozen=True)
class LaneMapSummary:
    path: Path
    project_id: str
    work_id: str
    approved_spec_ref: str | None
    spec_review_ref: str | None
    base_ref: str | None
    merge_target: str | None
    lanes_by_name: dict[str, dict[str, Any]]
    lanes_by_branch: dict[str, dict[str, Any]]


def lane_map_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    template = root / "templates" / "parallel-lane-map.yaml"
    if template.exists():
        paths.append(template)

    plan_root = root / "Plan"
    if plan_root.exists():
        paths.extend(sorted(plan_root.glob("*/lane-maps/*.yaml")))
        paths.extend(sorted(plan_root.glob("*/lane-maps/*.yml")))

    return sorted(dict.fromkeys(paths))


def workflow_run_paths(root: Path) -> list[Path]:
    artifact_root = root / "artifact"
    if not artifact_root.exists():
        return []
    paths = [
        *artifact_root.glob("*/output/workflows/*.yaml"),
        *artifact_root.glob("*/output/workflows/*.yml"),
    ]
    return sorted(dict.fromkeys(paths))


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw_data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{issue_path(path)}: invalid YAML: {exc}") from exc
    if not isinstance(raw_data, dict):
        raise ValueError(f"{issue_path(path)}: expected YAML mapping")
    return cast(dict[str, Any], raw_data)


def add_issue(issues: list[str], path: Path, message: str) -> None:
    issues.append(f"{issue_path(path)}: {message}")


def issue_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def mapping(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return None


def string_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        result.append(item.strip())
    return result


def is_template_path(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        relative = path.as_posix()
    return relative == "templates/parallel-lane-map.yaml"


def plan_lane_map_identity_from_path(path: Path) -> tuple[str, str] | None:
    try:
        parts = path.relative_to(ROOT).parts
    except ValueError:
        return None
    if len(parts) == 4 and parts[0] == "Plan" and parts[2] == "lane-maps":
        return parts[1], Path(parts[3]).stem
    return None


def contains_placeholder(value: str) -> bool:
    return "<" in value or ">" in value


def validate_token(value: str, label: str, *, allow_template_placeholder: bool) -> str | None:
    if allow_template_placeholder and value in TEMPLATE_PLACEHOLDERS:
        return None
    if value == "none":
        return f"{label} must not be none"
    if "/" in value or value.strip() != value or any(ch.isspace() for ch in value):
        return f"{label} must not contain slashes or whitespace"
    if not TOKEN_RE.match(value):
        return f"{label} must use letters, numbers, dots, underscores, or hyphens"
    return None


def normalize_write_target(raw_path: str) -> str | None:
    pure_path = PurePosixPath(raw_path.strip())
    if pure_path.is_absolute() or ".." in pure_path.parts:
        return None
    normalized = str(pure_path).strip("/")
    if normalized in {"", "."}:
        return None
    return normalized


def normalized_write_targets(value: object) -> list[str] | None:
    targets = string_list(value)
    if targets is None:
        return None

    normalized_targets: list[str] = []
    for target in targets:
        normalized = normalize_write_target(target)
        if normalized is None:
            return None
        normalized_targets.append(normalized)
    return sorted(normalized_targets)


def normalized_repo_path(raw_path: str) -> str | None:
    pure_path = PurePosixPath(raw_path.strip())
    if pure_path.is_absolute() or ".." in pure_path.parts:
        return None
    normalized = str(pure_path).strip("/")
    if normalized in {"", "."}:
        return None
    return normalized


def path_is_within_targets(path: str, targets: list[str]) -> bool:
    return any(path == target or path.startswith(f"{target}/") for target in targets)


def resolve_record_ref(ref: str) -> Path | None:
    pure_path = PurePosixPath(ref.strip())
    if pure_path.is_absolute() or ".." in pure_path.parts:
        return None
    normalized = str(pure_path).strip("/")
    if normalized in {"", "."}:
        return None
    return ROOT / normalized


def prefixes_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/")


def validate_no_placeholder(
    issues: list[str],
    path: Path,
    label: str,
    value: object,
    *,
    actual_record: bool,
) -> None:
    if not actual_record:
        return
    if isinstance(value, str) and contains_placeholder(value):
        add_issue(issues, path, f"{label} must not contain template placeholders in Plan lane maps")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and contains_placeholder(item):
                add_issue(
                    issues,
                    path,
                    f"{label} must not contain template placeholders in Plan lane maps",
                )
                return


def validate_requirement_ids(
    issues: list[str],
    path: Path,
    label: str,
    value: object,
    *,
    actual_record: bool,
) -> list[str] | None:
    requirement_ids = string_list(value)
    if requirement_ids is None or not requirement_ids:
        add_issue(issues, path, f"{label} must be a non-empty string list")
        return None
    validate_no_placeholder(issues, path, label, requirement_ids, actual_record=actual_record)
    invalid_ids = sorted(
        requirement_id
        for requirement_id in requirement_ids
        if not requirement_id.startswith(REQ_ID_PREFIX)
    )
    if invalid_ids:
        add_issue(issues, path, f"{label} IDs must start with {REQ_ID_PREFIX}: {invalid_ids}")
    return requirement_ids


def collect_requirement_ids(value: object) -> set[str]:
    requirement_ids: set[str] = set()

    def walk(item: object) -> None:
        if isinstance(item, str):
            requirement_ids.update(REQ_ID_RE.findall(item))
            return
        if isinstance(item, dict):
            for child in item.values():
                walk(child)
            return
        if isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return requirement_ids


def explicit_outcome(value: dict[str, Any]) -> str | None:
    for field in ("next_action", "outcome", "status", "lane_status", "handoff_state"):
        outcome = string_value(value.get(field))
        if outcome is not None:
            return outcome
    return None


def record_next_action(data: dict[str, Any]) -> str | None:
    for field in ("continuation", "handoff", "phase"):
        section = mapping(data.get(field))
        if section is None:
            continue
        next_action = string_value(section.get("next_action"))
        if next_action is not None:
            return next_action
    return None


def validate_spec_scope(
    issues: list[str],
    path: Path,
    data: dict[str, Any],
    *,
    actual_record: bool,
) -> set[str] | None:
    if "spec_scope" not in data:
        return None

    spec_scope = mapping(data.get("spec_scope"))
    if spec_scope is None:
        add_issue(issues, path, "spec_scope must be a mapping")
        return None

    for field in ("approved_spec_ref", "spec_review_ref"):
        value = string_value(spec_scope.get(field))
        if value is None:
            add_issue(issues, path, f"spec_scope.{field} must be a non-empty string")
            continue
        validate_no_placeholder(
            issues,
            path,
            f"spec_scope.{field}",
            value,
            actual_record=actual_record,
        )

    requirement_ids = validate_requirement_ids(
        issues,
        path,
        "spec_scope.requirement_ids",
        spec_scope.get("requirement_ids"),
        actual_record=actual_record,
    )
    if requirement_ids is None:
        return None
    return set(requirement_ids)


def validate_optional_lane_spec_fields(
    issues: list[str],
    path: Path,
    lane: dict[str, Any],
    lane_name: str,
    *,
    scoped_requirement_ids: set[str] | None,
    actual_record: bool,
) -> None:
    if "requirement_ids" in lane:
        lane_requirement_ids = validate_requirement_ids(
            issues,
            path,
            f"{lane_name}.requirement_ids",
            lane.get("requirement_ids"),
            actual_record=actual_record,
        )
        if lane_requirement_ids is not None and scoped_requirement_ids is not None:
            outside_scope = sorted(set(lane_requirement_ids) - scoped_requirement_ids)
            if outside_scope:
                add_issue(
                    issues,
                    path,
                    f"{lane_name}.requirement_ids outside spec_scope: {outside_scope}",
                )

    if "implementation_policy_refs" in lane:
        implementation_policy_refs = string_list(lane.get("implementation_policy_refs"))
        if implementation_policy_refs is None or not implementation_policy_refs:
            add_issue(
                issues,
                path,
                f"{lane_name}.implementation_policy_refs must be a non-empty string list",
            )
            return
        validate_no_placeholder(
            issues,
            path,
            f"{lane_name}.implementation_policy_refs",
            implementation_policy_refs,
            actual_record=actual_record,
        )


def validate_branch_target(
    branch_target: str,
    work_id: str,
    lane_name: str,
    *,
    allow_template_placeholder: bool,
) -> str | None:
    parts = branch_target.split("/")
    if len(parts) != 4:
        return "branch_target must be agent/<work_id>/<lane>/<slug>"

    agent, branch_work_id, branch_lane, slug = parts
    if agent != "agent":
        return "branch_target must start with agent/"
    if branch_work_id != work_id:
        return f"branch_target work_id must be {work_id}"
    if branch_lane != lane_name:
        return f"branch_target lane must be {lane_name}"

    for label, value in (
        ("branch_target work_id", branch_work_id),
        ("branch_target lane", branch_lane),
        ("branch_target slug", slug),
    ):
        issue = validate_token(value, label, allow_template_placeholder=allow_template_placeholder)
        if issue:
            return issue
    return None


def validate_handoff(
    issues: list[str],
    path: Path,
    data: dict[str, Any],
    *,
    actual_record: bool,
) -> None:
    handoff = mapping(data.get("handoff"))
    if handoff is None:
        add_issue(issues, path, "handoff must be a mapping")
        return

    evidence_required = string_list(handoff.get("evidence_required"))
    if evidence_required is None or not evidence_required:
        add_issue(issues, path, "handoff.evidence_required must be a non-empty string list")
        evidence_required = []
    else:
        missing = sorted(REQUIRED_HANDOFF_EVIDENCE - set(evidence_required))
        if missing:
            add_issue(
                issues,
                path,
                "handoff.evidence_required must include " + ", ".join(missing),
            )
        validate_no_placeholder(
            issues,
            path,
            "handoff.evidence_required",
            evidence_required,
            actual_record=actual_record,
        )

    next_action = string_value(handoff.get("next_action"))
    if not actual_record and next_action == "complete | rework | review | continue":
        return
    if next_action not in VALID_NEXT_ACTIONS:
        add_issue(issues, path, f"handoff.next_action must be one of {sorted(VALID_NEXT_ACTIONS)}")
    else:
        validate_no_placeholder(
            issues,
            path,
            "handoff.next_action",
            next_action,
            actual_record=actual_record,
        )


def summarize_lane_map(path: Path, data: dict[str, Any]) -> LaneMapSummary | None:
    identity = mapping(data.get("identity"))
    if identity is None:
        return None
    work_id = string_value(identity.get("work_id"))
    project_id = string_value(identity.get("project_id"))
    if work_id is None or project_id is None:
        return None

    spec_scope = mapping(data.get("spec_scope")) or {}
    git_scope = mapping(data.get("git_scope")) or {}
    lanes_raw = data.get("lanes")
    if not isinstance(lanes_raw, list):
        return None

    lanes_by_name: dict[str, dict[str, Any]] = {}
    lanes_by_branch: dict[str, dict[str, Any]] = {}
    for raw_lane in lanes_raw:
        lane = mapping(raw_lane)
        if lane is None:
            continue
        lane_name = string_value(lane.get("lane"))
        branch_target = string_value(lane.get("branch_target"))
        if lane_name is not None:
            lanes_by_name[lane_name] = lane
        if branch_target is not None:
            lanes_by_branch[branch_target] = lane

    return LaneMapSummary(
        path=path,
        project_id=project_id,
        work_id=work_id,
        approved_spec_ref=string_value(spec_scope.get("approved_spec_ref")),
        spec_review_ref=string_value(spec_scope.get("spec_review_ref")),
        base_ref=string_value(git_scope.get("base_ref")),
        merge_target=string_value(git_scope.get("merge_target")),
        lanes_by_name=lanes_by_name,
        lanes_by_branch=lanes_by_branch,
    )


def freshness_block_label(path_parts: tuple[str, ...]) -> str:
    return ".".join(path_parts) if path_parts else "<root>"


def is_freshness_block(path_parts: tuple[str, ...], value: dict[str, Any]) -> bool:
    label = freshness_block_label(path_parts).lower()
    return "freshness" in label or "freshness_state" in value


def require_freshness_fields(
    issues: list[str],
    path: Path,
    block: dict[str, Any],
    label: str,
    fields: tuple[str, ...],
) -> None:
    for field in fields:
        if string_value(block.get(field)) is None:
            add_issue(issues, path, f"{label}.{field} must be explicit for freshness evidence")


def validate_freshness_block(
    issues: list[str],
    path: Path,
    block: dict[str, Any],
    label: str,
    *,
    inherited_outcome: str | None,
) -> None:
    state = string_value(block.get("freshness_state"))
    alternate_state = string_value(block.get("state"))
    if state is not None and alternate_state is not None:
        add_issue(issues, path, f"{label} must not include both state and freshness_state")
        return

    if state is None and alternate_state is None:
        add_issue(issues, path, f"{label} must include exactly one of state or freshness_state")
        return

    state = state or alternate_state
    if state not in VALID_FRESHNESS_STATES:
        add_issue(
            issues,
            path,
            f"{label}.state must be one of {sorted(VALID_FRESHNESS_STATES)}",
        )
        return

    if state in {
        "current",
        "stale_fast_forwardable",
        "blocked_dirty_primary",
        "blocked_detached_primary",
        "blocked_diverged_primary",
    }:
        require_freshness_fields(
            issues,
            path,
            block,
            label,
            (
                "canonical_repo_root",
                "primary_branch",
                "intended_base_ref",
                "intended_merge_target",
                "local_primary_ref",
            ),
        )

    if state in FRESHNESS_REMOTE_TRACKING_STATES:
        require_freshness_fields(issues, path, block, label, ("remote_tracking_ref",))

    if state == "stale_fast_forwardable":
        require_freshness_fields(issues, path, block, label, ("post_update_primary_ref",))
    elif state == "blocked_missing_primary":
        require_freshness_fields(
            issues,
            path,
            block,
            label,
            (
                "canonical_repo_root",
                "intended_base_ref",
                "intended_merge_target",
                "missing_primary_reason",
            ),
        )
    elif state == "explicit_base_not_primary":
        require_freshness_fields(issues, path, block, label, ("explicit_base_ref", "reason"))
    elif state == "not_applicable":
        require_freshness_fields(issues, path, block, label, ("reason",))

    outcome = explicit_outcome(block) or inherited_outcome
    if state in BLOCKING_FRESHNESS_STATES and outcome not in BLOCKING_OUTCOMES:
        add_issue(
            issues,
            path,
            f"{label} must record rework or blocked outcome for blocking freshness state {state}",
        )


def validate_freshness_blocks(
    issues: list[str],
    path: Path,
    value: object,
    path_parts: tuple[str, ...] = (),
    *,
    inherited_outcome: str | None = None,
) -> None:
    if isinstance(value, dict):
        data = cast(dict[str, Any], value)
        if is_freshness_block(path_parts, data):
            validate_freshness_block(
                issues,
                path,
                data,
                freshness_block_label(path_parts),
                inherited_outcome=inherited_outcome,
            )
        for key, child in data.items():
            validate_freshness_blocks(
                issues,
                path,
                child,
                (*path_parts, str(key)),
                inherited_outcome=inherited_outcome,
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_freshness_blocks(
                issues,
                path,
                child,
                (*path_parts, str(index)),
                inherited_outcome=inherited_outcome,
            )


def is_pr_handoff_block(path_parts: tuple[str, ...], value: dict[str, Any]) -> bool:
    label = freshness_block_label(path_parts).lower().replace("-", "_")
    return any(marker in label for marker in PR_HANDOFF_LABEL_MARKERS) or bool(
        PR_HANDOFF_TRIGGER_FIELDS & set(value)
    )


def validate_pr_handoff_block(
    issues: list[str],
    path: Path,
    block: dict[str, Any],
    label: str,
    *,
    owned_branches: set[str] | None,
    expected_base_ref: str | None,
    expected_merge_target: str | None,
    inherited_outcome: str | None,
) -> None:
    for field in sorted(REQUIRED_PR_HANDOFF_FIELDS):
        if field == "branch_worktree_ownership":
            if mapping(block.get(field)) is None:
                add_issue(issues, path, f"{label}.{field} must be a mapping")
            continue
        if string_value(block.get(field)) is None:
            add_issue(issues, path, f"{label}.{field} must be explicit")

    source_branch = string_value(block.get("owned_source_branch"))
    if source_branch is not None:
        if not source_branch.startswith("agent/"):
            add_issue(issues, path, f"{label}.owned_source_branch must be an agent/* branch")
        if owned_branches is not None and source_branch not in owned_branches:
            add_issue(
                issues,
                path,
                f"{label}.owned_source_branch must match a lane branch_target",
            )

    base_ref = string_value(block.get("base_ref"))
    if expected_base_ref is not None and base_ref is not None and base_ref != expected_base_ref:
        add_issue(issues, path, f"{label}.base_ref must match lane map base_ref")

    merge_target = string_value(block.get("merge_target"))
    if (
        expected_merge_target is not None
        and merge_target is not None
        and merge_target != expected_merge_target
    ):
        add_issue(issues, path, f"{label}.merge_target must match lane map merge_target")

    ownership = mapping(block.get("branch_worktree_ownership"))
    if ownership is not None:
        ownership_branch = string_value(ownership.get("branch_target"))
        ownership_worktree = string_value(ownership.get("worktree_target"))
        if ownership_branch is None:
            add_issue(
                issues, path, f"{label}.branch_worktree_ownership.branch_target must be explicit"
            )
        elif source_branch is not None and ownership_branch != source_branch:
            add_issue(
                issues,
                path,
                f"{label}.branch_worktree_ownership.branch_target must match owned_source_branch",
            )
        if ownership_worktree is None:
            add_issue(
                issues,
                path,
                f"{label}.branch_worktree_ownership.worktree_target must be explicit",
            )

    freshness_result = string_value(block.get("canonical_primary_freshness_result"))
    if freshness_result is not None and freshness_result not in VALID_FRESHNESS_STATES:
        add_issue(
            issues,
            path,
            f"{label}.canonical_primary_freshness_result must be one of "
            f"{sorted(VALID_FRESHNESS_STATES)}",
        )

    stale_handling = string_value(block.get("stale_merge_target_handling"))
    if stale_handling is not None and stale_handling not in VALID_STALE_MERGE_TARGET_HANDLING:
        add_issue(
            issues,
            path,
            f"{label}.stale_merge_target_handling must be one of "
            f"{sorted(VALID_STALE_MERGE_TARGET_HANDLING)}",
        )
    if stale_handling == "explicit_residual_risk":
        residual_risk = block.get("residual_risk")
        if string_value(residual_risk) is None and not string_list(residual_risk):
            add_issue(
                issues,
                path,
                f"{label}.residual_risk must be explicit when stale target handling "
                "is residual risk",
            )

    if inherited_outcome == "complete" or explicit_outcome(block) == "complete":
        add_issue(issues, path, f"{label} must not map PR or review handoff to complete")


def validate_pr_handoff_blocks(
    issues: list[str],
    path: Path,
    value: object,
    path_parts: tuple[str, ...] = (),
    *,
    owned_branches: set[str] | None,
    expected_base_ref: str | None,
    expected_merge_target: str | None,
    inherited_outcome: str | None,
) -> None:
    if isinstance(value, dict):
        data = cast(dict[str, Any], value)
        if is_pr_handoff_block(path_parts, data):
            validate_pr_handoff_block(
                issues,
                path,
                data,
                freshness_block_label(path_parts),
                owned_branches=owned_branches,
                expected_base_ref=expected_base_ref,
                expected_merge_target=expected_merge_target,
                inherited_outcome=inherited_outcome,
            )
            return
        for key, child in data.items():
            validate_pr_handoff_blocks(
                issues,
                path,
                child,
                (*path_parts, str(key)),
                owned_branches=owned_branches,
                expected_base_ref=expected_base_ref,
                expected_merge_target=expected_merge_target,
                inherited_outcome=inherited_outcome,
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_pr_handoff_blocks(
                issues,
                path,
                child,
                (*path_parts, str(index)),
                owned_branches=owned_branches,
                expected_base_ref=expected_base_ref,
                expected_merge_target=expected_merge_target,
                inherited_outcome=inherited_outcome,
            )


def validate_lane_map(path: Path) -> list[str]:
    issues: list[str] = []
    data = load_yaml(path)
    template = is_template_path(path)
    actual_record = plan_lane_map_identity_from_path(path) is not None
    allow_template_placeholder = template and not actual_record

    if not template and not actual_record:
        add_issue(
            issues,
            path,
            "lane maps must be templates/parallel-lane-map.yaml "
            "or Plan/<project_id>/lane-maps/<work_id>.yaml",
        )

    schema_version = string_value(data.get("schema_version"))
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        add_issue(
            issues,
            path,
            f"schema_version must be one of {sorted(SUPPORTED_SCHEMA_VERSIONS)}",
        )

    if data.get("record_type") != "parallel_lane_map":
        add_issue(issues, path, "record_type must be parallel_lane_map")

    status = string_value(data.get("status"))
    if status not in VALID_RECORD_STATUSES:
        add_issue(issues, path, f"status must be one of {sorted(VALID_RECORD_STATUSES)}")

    identity = mapping(data.get("identity"))
    if identity is None:
        add_issue(issues, path, "identity must be a mapping")
        identity = {}
    work_id = string_value(identity.get("work_id"))
    project_id = string_value(identity.get("project_id"))
    if work_id is None:
        add_issue(issues, path, "identity.work_id must be explicit")
        work_id = "<missing-work-id>"
    else:
        validate_no_placeholder(
            issues,
            path,
            "identity.work_id",
            work_id,
            actual_record=actual_record,
        )
        issue = validate_token(
            work_id,
            "identity.work_id",
            allow_template_placeholder=allow_template_placeholder,
        )
        if issue:
            add_issue(issues, path, issue)
    if project_id is None:
        add_issue(issues, path, "identity.project_id must be explicit")
    else:
        validate_no_placeholder(
            issues,
            path,
            "identity.project_id",
            project_id,
            actual_record=actual_record,
        )
        issue = validate_token(
            project_id,
            "identity.project_id",
            allow_template_placeholder=allow_template_placeholder,
        )
        if issue:
            add_issue(issues, path, issue)
    if string_value(identity.get("created_at")) is None:
        add_issue(issues, path, "identity.created_at must be explicit")

    path_identity = plan_lane_map_identity_from_path(path)
    if path_identity is not None:
        path_project_id, path_work_id = path_identity
        if project_id != path_project_id:
            add_issue(
                issues,
                path,
                f"identity.project_id must match Plan path project_id: {path_project_id}",
            )
        if work_id != path_work_id:
            add_issue(
                issues,
                path,
                f"identity.work_id must match lane-map filename: {path_work_id}",
            )
        if (
            project_id
            and work_id
            and work_id != project_id
            and not work_id.startswith(f"{project_id}-")
        ):
            add_issue(
                issues,
                path,
                "identity.work_id must equal or be prefixed by identity.project_id",
            )

    governance = mapping(data.get("governance"))
    if governance is None:
        add_issue(issues, path, "governance must be a mapping")
        governance = {}
    map_owner = string_value(governance.get("map_owner"))
    if map_owner is None:
        add_issue(issues, path, "governance.map_owner must be explicit")
    elif actual_record and map_owner not in VALID_MAP_OWNERS:
        add_issue(issues, path, f"governance.map_owner must be one of {sorted(VALID_MAP_OWNERS)}")
    if string_value(governance.get("update_rule")) is None:
        add_issue(issues, path, "governance.update_rule must be explicit")
    budget = mapping(governance.get("context_budget"))
    if budget is None:
        add_issue(issues, path, "governance.context_budget must be a mapping")
        budget = {}
    max_source_refs = budget.get("required_source_refs_per_lane_max")
    if not isinstance(max_source_refs, int) or max_source_refs < 1:
        add_issue(issues, path, "context_budget.required_source_refs_per_lane_max must be positive")
        max_source_refs = 999999
    if budget.get("deny_broad_repo_scan") is not True:
        add_issue(issues, path, "context_budget.deny_broad_repo_scan must be true")

    git_scope = mapping(data.get("git_scope"))
    if git_scope is None:
        add_issue(issues, path, "git_scope must be a mapping")
        git_scope = {}
    if git_scope.get("mode") != "parallel":
        add_issue(issues, path, "git_scope.mode must be parallel")
    for field in ("base_ref", "merge_target"):
        value = string_value(git_scope.get(field))
        if value is None:
            add_issue(issues, path, f"git_scope.{field} must be explicit")
        else:
            validate_no_placeholder(
                issues,
                path,
                f"git_scope.{field}",
                value,
                actual_record=actual_record,
            )
    conflict_policy = string_value(git_scope.get("conflict_policy"))
    if conflict_policy not in VALID_CONFLICT_POLICIES:
        add_issue(
            issues,
            path,
            f"git_scope.conflict_policy must be one of {sorted(VALID_CONFLICT_POLICIES)}",
        )
        conflict_policy = "no_overlap"
    sibling_refs = string_list(git_scope.get("sibling_branch_refs"))
    if sibling_refs is None:
        add_issue(issues, path, "git_scope.sibling_branch_refs must be a string list")
    else:
        validate_no_placeholder(
            issues,
            path,
            "git_scope.sibling_branch_refs",
            sibling_refs,
            actual_record=actual_record,
        )

    scoped_requirement_ids = validate_spec_scope(
        issues,
        path,
        data,
        actual_record=actual_record,
    )

    lanes_raw = data.get("lanes")
    if not isinstance(lanes_raw, list) or not lanes_raw:
        add_issue(issues, path, "lanes must be a non-empty list")
        lanes_raw = []

    seen_lanes: set[str] = set()
    seen_branches: set[str] = set()
    seen_worktrees: set[str] = set()
    lane_targets: list[tuple[str, str]] = []

    for index, raw_lane in enumerate(lanes_raw):
        lane_label = f"lanes[{index}]"
        lane = mapping(raw_lane)
        if lane is None:
            add_issue(issues, path, f"{lane_label} must be a mapping")
            continue

        lane_name = string_value(lane.get("lane"))
        if lane_name is None:
            add_issue(issues, path, f"{lane_label}.lane must be explicit")
            lane_name = f"<missing-lane-{index}>"
        else:
            validate_no_placeholder(
                issues,
                path,
                f"{lane_label}.lane",
                lane_name,
                actual_record=actual_record,
            )
            issue = validate_token(
                lane_name,
                f"{lane_label}.lane",
                allow_template_placeholder=False,
            )
            if issue:
                add_issue(issues, path, issue)
        if lane_name in seen_lanes:
            add_issue(issues, path, f"duplicate lane name: {lane_name}")
        seen_lanes.add(lane_name)

        owner = string_value(lane.get("owner"))
        if owner is None:
            add_issue(issues, path, f"{lane_name}.owner must be explicit")
        else:
            validate_no_placeholder(
                issues,
                path,
                f"{lane_name}.owner",
                owner,
                actual_record=actual_record,
            )
        if string_value(lane.get("task_intent")) is None:
            add_issue(issues, path, f"{lane_name}.task_intent must be explicit")
        lane_status = string_value(lane.get("status"))
        if lane_status not in VALID_LANE_STATUSES:
            add_issue(
                issues,
                path,
                f"{lane_name}.status must be one of {sorted(VALID_LANE_STATUSES)}",
            )
        if actual_record and owner == "unassigned" and lane_status != "planned":
            add_issue(
                issues,
                path,
                f"{lane_name}.owner may be unassigned only while status is planned",
            )

        source_refs = string_list(lane.get("source_refs"))
        if source_refs is None or not source_refs:
            add_issue(issues, path, f"{lane_name}.source_refs must be a non-empty string list")
            source_refs = []
        else:
            validate_no_placeholder(
                issues,
                path,
                f"{lane_name}.source_refs",
                source_refs,
                actual_record=actual_record,
            )
        if len(source_refs) > max_source_refs:
            add_issue(
                issues,
                path,
                f"{lane_name}.source_refs exceeds context budget "
                f"({len(source_refs)} > {max_source_refs})",
            )

        validate_optional_lane_spec_fields(
            issues,
            path,
            lane,
            lane_name,
            scoped_requirement_ids=scoped_requirement_ids,
            actual_record=actual_record,
        )

        for field in (
            "allowed_write_targets",
            "denied_context",
            "expected_outputs",
            "verification_required",
        ):
            values = string_list(lane.get(field))
            if values is None or not values:
                add_issue(issues, path, f"{lane_name}.{field} must be a non-empty string list")
                continue
            validate_no_placeholder(
                issues,
                path,
                f"{lane_name}.{field}",
                values,
                actual_record=actual_record,
            )
            if field == "allowed_write_targets":
                for target in values:
                    normalized = normalize_write_target(target)
                    if normalized is None:
                        add_issue(
                            issues,
                            path,
                            f"{lane_name}.allowed_write_targets has invalid path: {target}",
                        )
                        continue
                    lane_targets.append((lane_name, normalized))

        branch_target = string_value(lane.get("branch_target"))
        if branch_target is None:
            add_issue(issues, path, f"{lane_name}.branch_target must be explicit")
        else:
            validate_no_placeholder(
                issues,
                path,
                f"{lane_name}.branch_target",
                branch_target,
                actual_record=actual_record,
            )
            issue = validate_branch_target(
                branch_target,
                work_id,
                lane_name,
                allow_template_placeholder=allow_template_placeholder,
            )
            if issue:
                add_issue(issues, path, f"{lane_name}.{issue}")
            if branch_target in seen_branches:
                add_issue(issues, path, f"duplicate branch_target: {branch_target}")
            seen_branches.add(branch_target)

        worktree_target = string_value(lane.get("worktree_target"))
        if worktree_target is None:
            add_issue(issues, path, f"{lane_name}.worktree_target must be explicit")
        else:
            validate_no_placeholder(
                issues,
                path,
                f"{lane_name}.worktree_target",
                worktree_target,
                actual_record=actual_record,
            )
            expected_fragment = f"{work_id}-{lane_name}"
            if expected_fragment not in worktree_target:
                add_issue(
                    issues,
                    path,
                    f"{lane_name}.worktree_target must include {expected_fragment}",
                )
            if worktree_target in seen_worktrees:
                add_issue(issues, path, f"duplicate worktree_target: {worktree_target}")
            seen_worktrees.add(worktree_target)

    if conflict_policy == "no_overlap":
        for left_index, (left_lane, left_target) in enumerate(lane_targets):
            for right_lane, right_target in lane_targets[left_index + 1 :]:
                if left_lane != right_lane and prefixes_overlap(left_target, right_target):
                    add_issue(
                        issues,
                        path,
                        "allowed_write_targets overlap under no_overlap: "
                        f"{left_lane}:{left_target} <-> {right_lane}:{right_target}",
                    )

    validate_handoff(issues, path, data, actual_record=actual_record)
    validate_freshness_blocks(issues, path, data)
    return issues


def validate_complete_lane_evidence(
    issues: list[str],
    workflow_path: Path,
    lane_name: str,
    contract_data: dict[str, Any],
    *,
    allowed_targets: list[str] | None,
) -> None:
    outputs = mapping(contract_data.get("outputs")) or {}
    evidence_and_verification = mapping(contract_data.get("evidence_and_verification")) or {}
    changed_paths = string_list(outputs.get("changed_paths"))
    verification_results = evidence_and_verification.get("verification_results")
    residual_risk = evidence_and_verification.get("residual_risk")

    if changed_paths is None or not changed_paths:
        add_issue(
            issues,
            workflow_path,
            f"{lane_name}.complete lane requires work contract outputs.changed_paths evidence",
        )
        changed_paths = []
    if not isinstance(verification_results, list) or not verification_results:
        add_issue(
            issues,
            workflow_path,
            f"{lane_name}.complete lane requires work contract verification_results",
        )
    if not isinstance(residual_risk, list) or not residual_risk:
        add_issue(
            issues,
            workflow_path,
            f"{lane_name}.complete lane requires explicit residual_risk",
        )

    for changed_path in changed_paths:
        normalized_changed_path = normalized_repo_path(changed_path)
        if normalized_changed_path is None:
            add_issue(
                issues,
                workflow_path,
                f"{lane_name}.complete lane has invalid changed_path: {changed_path}",
            )
            continue
        if allowed_targets is None or not path_is_within_targets(
            normalized_changed_path,
            allowed_targets,
        ):
            add_issue(
                issues,
                workflow_path,
                f"{lane_name}.complete lane changed_path outside allowed_write_targets: "
                f"{changed_path}",
            )


def validate_work_contract_correspondence(
    issues: list[str],
    workflow_path: Path,
    contract_path: Path,
    contract_data: dict[str, Any],
    lane_map: LaneMapSummary,
) -> str | None:
    if contract_data.get("record_type") != "work_contract":
        add_issue(issues, workflow_path, f"{issue_path(contract_path)} must be a work_contract")
        return None

    inherited_outcome = record_next_action(contract_data)
    validate_freshness_blocks(
        issues,
        contract_path,
        contract_data,
        inherited_outcome=inherited_outcome,
    )

    identity = mapping(contract_data.get("identity"))
    if identity is None:
        add_issue(issues, workflow_path, f"{issue_path(contract_path)} identity must be a mapping")
        return None

    project_id = string_value(identity.get("project_id"))
    work_id = string_value(identity.get("work_id"))
    if project_id != lane_map.project_id:
        add_issue(
            issues,
            workflow_path,
            f"{issue_path(contract_path)} identity.project_id must match lane map project_id",
        )
    if work_id != lane_map.work_id:
        add_issue(
            issues,
            workflow_path,
            f"{issue_path(contract_path)} identity.work_id must match lane map work_id",
        )

    boundaries = mapping(contract_data.get("boundaries"))
    if boundaries is None:
        add_issue(
            issues, workflow_path, f"{issue_path(contract_path)} boundaries must be a mapping"
        )
        return None
    git_scope = mapping(boundaries.get("git_scope"))
    if git_scope is None:
        add_issue(
            issues,
            workflow_path,
            f"{issue_path(contract_path)} boundaries.git_scope must be a mapping",
        )
        return None

    branch_target = string_value(git_scope.get("branch_target"))
    if branch_target is None:
        add_issue(
            issues,
            workflow_path,
            f"{issue_path(contract_path)} boundaries.git_scope.branch_target must be explicit",
        )
        return None

    lane = lane_map.lanes_by_branch.get(branch_target)
    if lane is None:
        add_issue(
            issues,
            workflow_path,
            f"{issue_path(contract_path)} branch_target must match a lane-map branch_target",
        )
        return None

    lane_name = cast(str, lane["lane"])
    for contract_field, lane_value in (
        ("base_ref", lane_map.base_ref),
        ("merge_target", lane_map.merge_target),
    ):
        contract_value = string_value(git_scope.get(contract_field))
        if lane_value is not None and contract_value != lane_value:
            add_issue(
                issues,
                workflow_path,
                f"{issue_path(contract_path)} git_scope.{contract_field} must match lane map",
            )

    worktree_target = string_value(git_scope.get("worktree_target"))
    if worktree_target != string_value(lane.get("worktree_target")):
        add_issue(
            issues,
            workflow_path,
            f"{issue_path(contract_path)} worktree_target must match lane {lane_name}",
        )

    normalized_contract_targets = normalized_write_targets(boundaries.get("allowed_write_targets"))
    normalized_lane_targets = normalized_write_targets(lane.get("allowed_write_targets"))
    if normalized_contract_targets != normalized_lane_targets:
        add_issue(
            issues,
            workflow_path,
            f"{issue_path(contract_path)} allowed_write_targets must match lane {lane_name}",
        )

    validate_pr_handoff_blocks(
        issues,
        contract_path,
        contract_data,
        owned_branches={branch_target},
        expected_base_ref=lane_map.base_ref,
        expected_merge_target=lane_map.merge_target,
        inherited_outcome=inherited_outcome,
    )

    lane_requirement_ids = set(string_list(lane.get("requirement_ids")) or [])
    contract_requirement_ids = collect_requirement_ids(contract_data)
    if lane_requirement_ids and not lane_requirement_ids <= contract_requirement_ids:
        missing = sorted(lane_requirement_ids - contract_requirement_ids)
        add_issue(
            issues,
            workflow_path,
            f"{issue_path(contract_path)} must record lane requirement_ids: {missing}",
        )

    if string_value(lane.get("status")) == "complete":
        validate_complete_lane_evidence(
            issues,
            workflow_path,
            lane_name,
            contract_data,
            allowed_targets=normalized_contract_targets,
        )

    return lane_name


def validate_workflow_run(
    path: Path,
    lane_maps_by_ref: dict[str, LaneMapSummary],
) -> list[str]:
    issues: list[str] = []
    data = load_yaml(path)
    inherited_outcome = record_next_action(data)
    validate_freshness_blocks(issues, path, data, inherited_outcome=inherited_outcome)

    if data.get("record_type") != "workflow_run_record":
        add_issue(issues, path, "record_type must be workflow_run_record")
        return issues

    identity = mapping(data.get("identity"))
    if identity is None:
        add_issue(issues, path, "identity must be a mapping")
        identity = {}
    workflow_project_id = string_value(identity.get("project_id"))
    workflow_work_id = string_value(identity.get("work_id"))

    phase = mapping(data.get("phase")) or {}
    current_phase = string_value(phase.get("current"))
    next_action = string_value(phase.get("next_action"))
    phase_requires_lane_refs = bool({current_phase, next_action} & LANE_PHASES_REQUIRING_REFS)

    record_refs = mapping(data.get("record_refs"))
    if record_refs is None:
        add_issue(issues, path, "record_refs must be a mapping")
        return issues

    for field in ("goal_ref", "approved_spec_ref", "spec_review_ref"):
        if phase_requires_lane_refs and string_value(record_refs.get(field)) is None:
            add_issue(issues, path, f"record_refs.{field} must be explicit")

    lane_map_ref = string_value(record_refs.get("lane_map_ref"))
    if lane_map_ref is None:
        if phase_requires_lane_refs:
            add_issue(issues, path, "record_refs.lane_map_ref must be explicit")
        return issues

    lane_map_path = resolve_record_ref(lane_map_ref)
    if lane_map_path is None:
        add_issue(issues, path, "record_refs.lane_map_ref must be a repo-relative path")
        return issues
    lane_map = lane_maps_by_ref.get(lane_map_path.as_posix())
    if lane_map is None:
        add_issue(issues, path, "record_refs.lane_map_ref must point to a validated lane map")
        return issues

    if workflow_project_id != lane_map.project_id:
        add_issue(issues, path, "identity.project_id must match referenced lane map")
    if workflow_work_id != lane_map.work_id:
        add_issue(issues, path, "identity.work_id must match referenced lane map")

    if record_refs.get("approved_spec_ref") != lane_map.approved_spec_ref:
        add_issue(issues, path, "record_refs.approved_spec_ref must match lane map spec_scope")
    if record_refs.get("spec_review_ref") != lane_map.spec_review_ref:
        add_issue(issues, path, "record_refs.spec_review_ref must match lane map spec_scope")

    validate_pr_handoff_blocks(
        issues,
        path,
        data,
        owned_branches=set(lane_map.lanes_by_branch),
        expected_base_ref=lane_map.base_ref,
        expected_merge_target=lane_map.merge_target,
        inherited_outcome=inherited_outcome,
    )

    work_contract_refs = string_list(record_refs.get("work_contract_refs"))
    if work_contract_refs is None or not work_contract_refs:
        add_issue(issues, path, "record_refs.work_contract_refs must be a non-empty string list")
        return issues

    matched_lanes: set[str] = set()
    for contract_ref in work_contract_refs:
        contract_path = resolve_record_ref(contract_ref)
        if contract_path is None:
            add_issue(
                issues,
                path,
                f"record_refs.work_contract_refs entry must be repo-relative: {contract_ref}",
            )
            continue
        if not contract_path.is_file():
            add_issue(
                issues,
                path,
                f"record_refs.work_contract_refs entry does not exist: {contract_ref}",
            )
            continue
        contract_data = load_yaml(contract_path)
        matched_lane = validate_work_contract_correspondence(
            issues,
            path,
            contract_path,
            contract_data,
            lane_map,
        )
        if matched_lane is None:
            continue
        if matched_lane in matched_lanes:
            add_issue(issues, path, f"duplicate work contract for lane: {matched_lane}")
        matched_lanes.add(matched_lane)

    missing_lanes = sorted(set(lane_map.lanes_by_name) - matched_lanes)
    if missing_lanes:
        add_issue(
            issues,
            path,
            f"record_refs.work_contract_refs missing lane work contracts: {missing_lanes}",
        )

    return issues


def main() -> int:
    paths = lane_map_paths(ROOT)
    workflow_paths = workflow_run_paths(ROOT)
    if not paths and not workflow_paths:
        print("lane map check: no lane maps or workflow records found")
        return 0

    issues: list[str] = []
    lane_maps_by_ref: dict[str, LaneMapSummary] = {}
    for path in paths:
        try:
            lane_issues = validate_lane_map(path)
        except ValueError as exc:
            issues.append(str(exc))
            continue
        issues.extend(lane_issues)
        if lane_issues or is_template_path(path):
            continue
        summary = summarize_lane_map(path, load_yaml(path))
        if summary is not None:
            lane_maps_by_ref[path.as_posix()] = summary

    for path in workflow_paths:
        try:
            issues.extend(validate_workflow_run(path, lane_maps_by_ref))
        except ValueError as exc:
            issues.append(str(exc))

    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1

    lane_plural = "s" if len(paths) != 1 else ""
    workflow_plural = "s" if len(workflow_paths) != 1 else ""
    print(
        "lane map check: passed "
        f"({len(paths)} lane-map file{lane_plural}, "
        f"{len(workflow_paths)} workflow file{workflow_plural})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

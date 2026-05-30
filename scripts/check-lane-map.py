#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
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
REQUIRED_HANDOFF_EVIDENCE = {"source_refs", "changed_paths", "verification_results"}
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TEMPLATE_PLACEHOLDERS = {"<work-id>", "<project-id>", "<repo>", "<short-slug>"}


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


def load_yaml(path: Path) -> dict[str, Any]:
    raw_data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        raise ValueError(f"{path}: expected YAML mapping")
    return cast(dict[str, Any], raw_data)


def add_issue(issues: list[str], path: Path, message: str) -> None:
    issues.append(f"{path.relative_to(ROOT)}: {message}")


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
    return issues


def main() -> int:
    paths = lane_map_paths(ROOT)
    if not paths:
        print("lane map check: no lane maps found")
        return 0

    issues: list[str] = []
    for path in paths:
        issues.extend(validate_lane_map(path))

    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1

    plural = "s" if len(paths) != 1 else ""
    print(f"lane map check: passed ({len(paths)} file{plural})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]


def lane_map_template() -> dict[str, Any]:
    raw = yaml.safe_load((ROOT / "templates/parallel-lane-map.yaml").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast(dict[str, Any], raw)


def write_actual_lane_map(tmp_path: Path, data: dict[str, Any]) -> Path:
    identity = cast(dict[str, Any], data["identity"])
    project_id = cast(str, identity["project_id"])
    work_id = cast(str, identity["work_id"])
    path = tmp_path / "Plan" / project_id / "lane-maps" / f"{work_id}.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def repo_ref(tmp_path: Path, path: Path) -> str:
    return path.relative_to(tmp_path).as_posix()


def valid_actual_lane_map() -> dict[str, Any]:
    data = lane_map_template()
    data["status"] = "active"
    data["identity"] = {
        "work_id": "foundation-lane-map-ci",
        "project_id": "foundation",
        "created_at": "2026-05-30",
    }
    data["governance"]["map_owner"] = "agent"
    data["handoff"]["next_action"] = "review"
    data["spec_scope"] = {
        "approved_spec_ref": "artifact/foundation/output/specs/foundation-lane-map-ci.md",
        "spec_review_ref": "artifact/foundation/evidence/spec-review-foundation-lane-map-ci.yaml",
        "requirement_ids": ["REQ-001", "REQ-002", "REQ-003"],
    }

    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["owner"] = "unassigned"
    lanes[0]["requirement_ids"] = ["REQ-001", "REQ-002", "REQ-003"]
    lanes[0]["branch_target"] = "agent/foundation-lane-map-ci/docs/lane-map-docs"
    lanes[0]["worktree_target"] = "../worktrees/foundation/foundation-lane-map-ci-docs"
    lanes[1]["owner"] = "unassigned"
    lanes[1]["requirement_ids"] = ["REQ-001", "REQ-002", "REQ-003"]
    lanes[1]["branch_target"] = "agent/foundation-lane-map-ci/verification/lane-map-tests"
    lanes[1]["worktree_target"] = "../worktrees/foundation/foundation-lane-map-ci-verification"
    return data


def valid_work_contract(lane: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "record_type": "work_contract",
        "status": "draft",
        "identity": {
            "work_id": "foundation-lane-map-ci",
            "project_id": "foundation",
            "work_type": "verification",
            "created_at": "2026-05-30",
        },
        "intent": {
            "task_intent": "Validate lane workflow correspondence.",
            "success_criteria": ["Validation covers REQ-001, REQ-002, and REQ-003."],
            "non_goals": [],
        },
        "inputs": {
            "source_refs": ["artifact/foundation/output/specs/foundation-lane-map-ci.md"],
            "required_context": ["Approved requirements REQ-001, REQ-002, and REQ-003."],
            "optional_context": [],
            "templates": [],
        },
        "boundaries": {
            "allowed_write_targets": lane["allowed_write_targets"],
            "git_scope": {
                "mode": "parallel",
                "base_ref": "origin/main",
                "merge_target": "origin/main",
                "branch_target": lane["branch_target"],
                "worktree_target": lane["worktree_target"],
                "sibling_branch_refs": [],
                "conflict_policy": "no_overlap",
            },
            "denied_context": ["past_source_material", "secrets", "runtime_state"],
            "risk_flags": [],
        },
        "design_gate": {
            "architecture_significance": "local",
            "system_design_skill_required": False,
            "reason": "Local validation only.",
        },
        "outputs": {
            "expected_outputs": ["Changed validation scripts and tests."],
            "artifact_refs": [],
            "changed_paths": [],
            "decision_refs": [],
        },
        "evidence_and_verification": {
            "evidence_required": ["changed_paths"],
            "verification_required": ["Run targeted tests."],
            "verification_results": [],
            "residual_risk": [],
        },
        "continuation": {
            "blockers": [],
            "open_questions": [],
            "next_action": "review",
        },
    }


def write_work_contract(
    tmp_path: Path,
    lane: dict[str, Any],
    *,
    mutate: Any | None = None,
) -> Path:
    data = valid_work_contract(lane)
    if mutate is not None:
        mutate(data)
    lane_name = cast(str, lane["lane"])
    path = (
        tmp_path
        / "artifact"
        / "foundation"
        / "output"
        / "work-contracts"
        / "foundation-lane-map-ci"
        / f"{lane_name}.yaml"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def valid_workflow_run(
    tmp_path: Path,
    lane_map_path: Path,
    work_contract_paths: list[Path],
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "record_type": "workflow_run_record",
        "status": "draft",
        "identity": {
            "project_id": "foundation",
            "work_id": "foundation-lane-map-ci",
            "goal_id": "goal-foundation-lane-map-ci",
            "created_at": "2026-05-30",
        },
        "phase": {"current": "lane_mapping", "next_action": "parallel_build"},
        "record_refs": {
            "goal_ref": "artifact/foundation/output/goals/goal-foundation-lane-map-ci.md",
            "approved_spec_ref": "artifact/foundation/output/specs/foundation-lane-map-ci.md",
            "spec_review_ref": (
                "artifact/foundation/evidence/spec-review-foundation-lane-map-ci.yaml"
            ),
            "lane_map_ref": repo_ref(tmp_path, lane_map_path),
            "work_contract_refs": [repo_ref(tmp_path, path) for path in work_contract_paths],
            "build_result_refs": [],
            "review_record_refs": [],
            "integration_review_refs": [],
            "inconsistency_register_ref": "",
            "rework_refs": [],
            "convergence_check_ref": "",
            "final_handoff_ref": "",
        },
        "communication_rules": {
            "human_interface": "main_lane_only",
            "subagent_to_human_direct": "prohibited",
            "subagent_to_subagent_direct": "prohibited",
            "state_authority": "record_refs_not_conversation",
        },
        "human_gates": {
            "spec_approval": {
                "required": True,
                "status": "approved",
                "evidence_ref": "artifact/foundation/evidence/human-approval.yaml",
            },
            "final_merge": {
                "required": True,
                "status": "required",
                "evidence_ref": "",
            },
        },
        "open_questions": [],
        "blocked_reasons": [],
        "residual_risk": ["none"],
        "handoff": {"next_action": "parallel_build"},
    }


def write_workflow_run(
    tmp_path: Path,
    data: dict[str, Any],
) -> Path:
    path = tmp_path / "artifact" / "foundation" / "output" / "workflows" / "foundation.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def write_valid_workflow_set(tmp_path: Path) -> tuple[dict[str, Any], Path, list[Path]]:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    contract_paths = [write_work_contract(tmp_path, lane) for lane in lanes]
    write_workflow_run(tmp_path, valid_workflow_run(tmp_path, lane_map_path, contract_paths))
    return lane_map, lane_map_path, contract_paths


def pr_handoff_for_lane(lane: dict[str, Any]) -> dict[str, Any]:
    return {
        "owned_source_branch": lane["branch_target"],
        "intended_target_branch": "main",
        "base_ref": "origin/main",
        "merge_target": "origin/main",
        "branch_worktree_ownership": {
            "branch_target": lane["branch_target"],
            "worktree_target": lane["worktree_target"],
        },
        "canonical_primary_freshness_result": "current",
        "stale_merge_target_handling": "checked_against_newer_target",
        "next_action": "review",
    }


def add_contract_evidence(data: dict[str, Any], key: str, value: object) -> None:
    evidence = cast(dict[str, Any], data["evidence_and_verification"])
    evidence[key] = value


def mark_contract_complete(data: dict[str, Any], changed_paths: list[str]) -> None:
    outputs = cast(dict[str, Any], data["outputs"])
    evidence = cast(dict[str, Any], data["evidence_and_verification"])
    outputs["changed_paths"] = changed_paths
    evidence["verification_results"] = [{"name": "targeted tests", "result": "passed"}]
    evidence["residual_risk"] = ["none"]


def run_lane_check(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-lane-map.py")],
        cwd=ROOT,
        env={**os.environ, "FOUNDATION_REPO_ROOT": str(tmp_path)},
        check=False,
        capture_output=True,
        text=True,
    )


def test_check_lane_map_accepts_valid_plan_lane_map(tmp_path: Path) -> None:
    write_actual_lane_map(tmp_path, valid_actual_lane_map())

    result = run_lane_check(tmp_path)

    assert result.returncode == 0
    assert "lane map check: passed" in result.stdout


def test_check_lane_map_rejects_branch_target_with_extra_segments(tmp_path: Path) -> None:
    data = valid_actual_lane_map()
    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["branch_target"] = "agent/foundation-lane-map-ci/docs/lane-map-docs/extra"
    write_actual_lane_map(tmp_path, data)

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "branch_target must be agent/<work_id>/<lane>/<slug>" in result.stderr


def test_check_lane_map_rejects_placeholders_in_plan_lane_map(tmp_path: Path) -> None:
    data = valid_actual_lane_map()
    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["branch_target"] = "agent/foundation-lane-map-ci/docs/<short-slug>"
    write_actual_lane_map(tmp_path, data)

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "must not contain template placeholders in Plan lane maps" in result.stderr


def test_check_lane_map_rejects_plan_project_id_mismatch(tmp_path: Path) -> None:
    data = valid_actual_lane_map()
    path = tmp_path / "Plan" / "other-project" / "lane-maps" / "foundation-lane-map-ci.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "identity.project_id must match Plan path project_id: other-project" in result.stderr


def test_check_lane_map_allows_same_lane_overlapping_targets(tmp_path: Path) -> None:
    data = valid_actual_lane_map()
    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["allowed_write_targets"] = ["docs/", "docs/reference/"]
    lanes[1]["allowed_write_targets"] = ["tests/"]
    write_actual_lane_map(tmp_path, data)

    result = run_lane_check(tmp_path)

    assert result.returncode == 0


def test_check_lane_map_accepts_workflow_lane_contract_correspondence(
    tmp_path: Path,
) -> None:
    write_valid_workflow_set(tmp_path)

    result = run_lane_check(tmp_path)

    assert result.returncode == 0
    assert "workflow file" in result.stdout


def test_check_lane_map_rejects_work_contract_target_mismatch(tmp_path: Path) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: cast(dict[str, Any], data["boundaries"])[
            "allowed_write_targets"
        ].append("scripts/"),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "allowed_write_targets must match lane docs" in result.stderr


def test_check_lane_map_accepts_pr_handoff_evidence(tmp_path: Path) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: add_contract_evidence(
            data,
            "pr_handoff_evidence",
            pr_handoff_for_lane(lanes[0]),
        ),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 0


def test_check_lane_map_rejects_pr_handoff_missing_stale_target_handling(
    tmp_path: Path,
) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])

    def mutate(data: dict[str, Any]) -> None:
        handoff = pr_handoff_for_lane(lanes[0])
        del handoff["stale_merge_target_handling"]
        add_contract_evidence(data, "pr_handoff_evidence", handoff)

    first_contract = write_work_contract(tmp_path, lanes[0], mutate=mutate)
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "pr_handoff_evidence.stale_merge_target_handling must be explicit" in result.stderr


def test_check_lane_map_rejects_pr_handoff_mapping_to_complete(tmp_path: Path) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])

    def mutate(data: dict[str, Any]) -> None:
        handoff = pr_handoff_for_lane(lanes[0])
        handoff["next_action"] = "complete"
        add_contract_evidence(data, "review_handoff_evidence", handoff)

    first_contract = write_work_contract(tmp_path, lanes[0], mutate=mutate)
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "review_handoff_evidence must not map PR or review handoff to complete" in result.stderr


def test_check_lane_map_rejects_invalid_freshness_state(tmp_path: Path) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: cast(dict[str, Any], data["evidence_and_verification"]).update(
            {
                "canonical_primary_freshness": {
                    "state": "fresh",
                    "intended_base_ref": "origin/main",
                    "intended_merge_target": "origin/main",
                }
            }
        ),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "canonical_primary_freshness.state must be one of" in result.stderr


def test_check_lane_map_rejects_freshness_evidence_without_state(tmp_path: Path) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: add_contract_evidence(
            data,
            "canonical_primary_freshness",
            {
                "canonical_repo_root": "/repo",
                "primary_branch": "main",
                "intended_base_ref": "origin/main",
                "intended_merge_target": "origin/main",
                "local_primary_ref": "abc123",
                "remote_tracking_ref": "abc123",
            },
        ),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "canonical_primary_freshness must include exactly one of state" in result.stderr


def test_check_lane_map_accepts_blocking_freshness_with_rework_outcome(
    tmp_path: Path,
) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: add_contract_evidence(
            data,
            "canonical_primary_freshness",
            {
                "state": "blocked_dirty_primary",
                "canonical_repo_root": "/repo",
                "primary_branch": "main",
                "intended_base_ref": "origin/main",
                "intended_merge_target": "origin/main",
                "local_primary_ref": "abc123",
                "next_action": "rework",
            },
        ),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 0


def test_check_lane_map_rejects_blocking_freshness_inherited_review_outcome(
    tmp_path: Path,
) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: add_contract_evidence(
            data,
            "canonical_primary_freshness",
            {
                "state": "blocked_dirty_primary",
                "canonical_repo_root": "/repo",
                "primary_branch": "main",
                "intended_base_ref": "origin/main",
                "intended_merge_target": "origin/main",
                "local_primary_ref": "abc123",
            },
        ),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "must record rework or blocked outcome for blocking freshness state" in result.stderr


def test_check_lane_map_rejects_duplicate_freshness_state_aliases(tmp_path: Path) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: add_contract_evidence(
            data,
            "canonical_primary_freshness",
            {
                "state": "current",
                "freshness_state": "current",
                "canonical_repo_root": "/repo",
                "primary_branch": "main",
                "intended_base_ref": "origin/main",
                "intended_merge_target": "origin/main",
                "local_primary_ref": "abc123",
                "remote_tracking_ref": "abc123",
            },
        ),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "must not include both state and freshness_state" in result.stderr


def test_check_lane_map_rejects_current_freshness_without_remote_tracking_ref(
    tmp_path: Path,
) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: add_contract_evidence(
            data,
            "canonical_primary_freshness",
            {
                "state": "current",
                "canonical_repo_root": "/repo",
                "primary_branch": "main",
                "intended_base_ref": "origin/main",
                "intended_merge_target": "origin/main",
                "local_primary_ref": "abc123",
            },
        ),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "remote_tracking_ref must be explicit" in result.stderr


def test_check_lane_map_rejects_missing_primary_without_observable_reason(
    tmp_path: Path,
) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: add_contract_evidence(
            data,
            "canonical_primary_freshness",
            {
                "state": "blocked_missing_primary",
                "canonical_repo_root": "/repo",
                "intended_base_ref": "origin/main",
                "intended_merge_target": "origin/main",
                "next_action": "blocked",
            },
        ),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "missing_primary_reason must be explicit" in result.stderr


def test_check_lane_map_rejects_stale_freshness_without_post_update_ref(
    tmp_path: Path,
) -> None:
    lane_map = valid_actual_lane_map()
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: cast(dict[str, Any], data["evidence_and_verification"]).update(
            {
                "canonical_primary_freshness": {
                    "state": "stale_fast_forwardable",
                    "canonical_repo_root": "/repo",
                    "primary_branch": "main",
                    "intended_base_ref": "origin/main",
                    "intended_merge_target": "origin/main",
                    "local_primary_ref": "abc123",
                    "remote_tracking_ref": "def456",
                }
            }
        ),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "post_update_primary_ref must be explicit" in result.stderr


def test_check_lane_map_accepts_complete_lane_changed_paths_in_allowed_targets(
    tmp_path: Path,
) -> None:
    lane_map = valid_actual_lane_map()
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    for lane in lanes:
        lane["status"] = "complete"
        lane["owner"] = f"worker-{lane['lane']}"
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: mark_contract_complete(data, ["docs/reference/workflow.md"]),
    )
    second_contract = write_work_contract(
        tmp_path,
        lanes[1],
        mutate=lambda data: mark_contract_complete(data, ["tests/test_lane_map_check.py"]),
    )
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 0


def test_check_lane_map_rejects_complete_lane_changed_path_outside_allowed_targets(
    tmp_path: Path,
) -> None:
    lane_map = valid_actual_lane_map()
    lanes = cast(list[dict[str, Any]], lane_map["lanes"])
    lanes[0]["status"] = "complete"
    lanes[0]["owner"] = "worker-docs"
    lane_map_path = write_actual_lane_map(tmp_path, lane_map)
    first_contract = write_work_contract(
        tmp_path,
        lanes[0],
        mutate=lambda data: mark_contract_complete(data, ["scripts/check-lane-map.py"]),
    )
    second_contract = write_work_contract(tmp_path, lanes[1])
    write_workflow_run(
        tmp_path,
        valid_workflow_run(tmp_path, lane_map_path, [first_contract, second_contract]),
    )

    result = run_lane_check(tmp_path)

    assert result.returncode == 1
    assert "docs.complete lane changed_path outside allowed_write_targets" in result.stderr

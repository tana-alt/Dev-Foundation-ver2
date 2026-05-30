from pathlib import Path
from typing import Any, Literal, Self, cast

import pytest
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

ROOT = Path(__file__).resolve().parents[1]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemplateIdentity(StrictModel):
    work_id: str | None = None
    evidence_id: str | None = None
    verification_id: str | None = None
    rework_id: str | None = None
    project_id: str | None = None
    created_at: str
    work_type: str | None = None


class GitScopeTemplate(StrictModel):
    mode: Literal["single", "parallel"]
    base_ref: str | None = None
    merge_target: str | None = None
    branch_target: str | None = None
    worktree_target: str | None = None
    sibling_branch_refs: list[str]
    conflict_policy: Literal["no_overlap", "report_overlap", "explicitly_scoped"]


class SourceRef(StrictModel):
    path: str


class EvidenceSources(StrictModel):
    source_refs: list[SourceRef]
    commands: list[Any]
    screenshots: list[Any]
    external_refs: list[Any]

    @model_validator(mode="after")
    def source_refs_must_be_explicit(self) -> Self:
        if not self.source_refs:
            raise ValueError("source_refs must be explicit")
        return self


class ChangeRefs(StrictModel):
    changed_paths: list[str]
    artifact_refs: list[str]

    @model_validator(mode="after")
    def changed_path_or_artifact_ref_required(self) -> Self:
        if not self.changed_paths and not self.artifact_refs:
            raise ValueError("changed_paths or artifact_refs must be present")
        return self


class VerificationAttempt(StrictModel):
    name: str
    command: str
    result: Literal["passed", "failed", "blocked", "skipped", "not_applicable"]


class VerificationSummary(StrictModel):
    attempted: list[VerificationAttempt]
    result: Literal["passed", "failed", "blocked", "skipped", "not_applicable"]
    unverified_surfaces: list[str]

    @model_validator(mode="after")
    def verification_fields_must_be_explicit(self) -> Self:
        if not self.attempted:
            raise ValueError("verification attempted must be explicit")
        if not self.unverified_surfaces:
            raise ValueError("unverified_surfaces must use explicit values such as 'none'")
        return self


class HumanGate(StrictModel):
    required: bool
    status: Literal["approved", "blocked", "not_applicable", "required"]
    reason: str


class EvidenceLimits(StrictModel):
    missing_evidence: list[Any]
    stale_refs: list[Any]
    confidence: Literal["low", "medium", "high"]
    residual_risk: list[str]

    @model_validator(mode="after")
    def residual_risk_must_be_explicit(self) -> Self:
        if not self.residual_risk:
            raise ValueError("residual_risk must use explicit values such as 'none'")
        return self


class VerificationCheck(StrictModel):
    name: str
    command: str
    result: Literal["passed", "failed", "blocked", "skipped", "not_applicable"]
    evidence_ref: str
    notes: str

    @model_validator(mode="after")
    def non_passing_results_need_context(self) -> Self:
        if self.result in {"failed", "blocked", "skipped"}:
            if not self.command.strip():
                raise ValueError("failed, blocked, and skipped checks need a command or method")
            if not self.notes.strip():
                raise ValueError("failed, blocked, and skipped checks need a reason")
        return self


class EvidenceObservations(StrictModel):
    facts: list[str]
    inferences: list[str]
    decisions: list[str]


class WorkContractBoundaries(StrictModel):
    allowed_write_targets: list[str]
    git_scope: GitScopeTemplate
    denied_context: list[str]
    risk_flags: list[str]


class LaneMapIdentity(StrictModel):
    work_id: str
    project_id: str
    created_at: str


class LaneMapContextBudget(StrictModel):
    required_source_refs_per_lane_max: int
    deny_broad_repo_scan: bool

    @model_validator(mode="after")
    def budget_must_limit_context(self) -> Self:
        if self.required_source_refs_per_lane_max < 1:
            raise ValueError("required_source_refs_per_lane_max must be positive")
        if not self.deny_broad_repo_scan:
            raise ValueError("lane maps must deny broad repo scans")
        return self


class LaneMapGovernance(StrictModel):
    map_owner: str
    update_rule: str
    context_budget: LaneMapContextBudget


class LaneMapGitScope(StrictModel):
    mode: Literal["parallel"]
    base_ref: str
    merge_target: str
    conflict_policy: Literal["no_overlap", "report_overlap", "explicitly_scoped"]
    sibling_branch_refs: list[str]


class LaneEntry(StrictModel):
    lane: str
    status: Literal[
        "planned",
        "assigned",
        "in_progress",
        "blocked",
        "ready_for_review",
        "complete",
        "rework",
    ]
    owner: str
    task_intent: str
    source_refs: list[str]
    allowed_write_targets: list[str]
    denied_context: list[str]
    expected_outputs: list[str]
    verification_required: list[str]
    branch_target: str
    worktree_target: str

    @model_validator(mode="after")
    def lane_fields_must_be_explicit(self) -> Self:
        for field_name in (
            "source_refs",
            "allowed_write_targets",
            "denied_context",
            "expected_outputs",
            "verification_required",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be explicit")

        branch_parts = self.branch_target.split("/")
        if len(branch_parts) != 4:
            raise ValueError("branch_target must be agent/<work-id>/<lane>/<slug>")
        agent, branch_work_id, branch_lane, slug = branch_parts
        if (
            agent != "agent"
            or branch_work_id != "<work-id>"
            or branch_lane != self.lane
            or not slug
            or slug == "none"
        ):
            raise ValueError("branch_target must match lane ownership")

        expected_worktree_fragment = f"<work-id>-{self.lane}"
        if expected_worktree_fragment not in self.worktree_target:
            raise ValueError("worktree_target must include work_id and lane")

        return self


class ParallelLaneMapTemplate(StrictModel):
    schema_version: str
    record_type: Literal["parallel_lane_map"]
    status: Literal["draft", "active", "review", "complete"]
    identity: LaneMapIdentity
    governance: LaneMapGovernance
    git_scope: LaneMapGitScope
    lanes: list[LaneEntry]
    handoff: dict[str, Any]

    @model_validator(mode="after")
    def lanes_must_be_unique_and_non_overlapping(self) -> Self:
        lane_names = [lane.lane for lane in self.lanes]
        if not lane_names:
            raise ValueError("lanes must be explicit")
        if len(lane_names) != len(set(lane_names)):
            raise ValueError("lane names must be unique")

        if self.git_scope.conflict_policy == "no_overlap":
            targets: list[tuple[str, str]] = []
            for lane in self.lanes:
                targets.extend(
                    (lane.lane, normalize_prefix(target)) for target in lane.allowed_write_targets
                )
            for left_index, (left_lane, left_target) in enumerate(targets):
                for right_lane, right_target in targets[left_index + 1 :]:
                    if left_lane != right_lane and prefixes_overlap(left_target, right_target):
                        raise ValueError(
                            f"allowed_write_targets overlap: {left_lane}:{left_target} "
                            f"<-> {right_lane}:{right_target}"
                        )
        return self


class DesignGate(StrictModel):
    architecture_significance: Literal["none", "local", "significant"]
    system_design_skill_required: bool
    reason: str

    @model_validator(mode="after")
    def design_gate_must_be_consistent(self) -> Self:
        if self.architecture_significance == "significant":
            if not self.system_design_skill_required:
                raise ValueError("significant work requires system-design skill")
        if self.architecture_significance != "significant" and self.system_design_skill_required:
            raise ValueError("system-design skill is only required for significant work")
        if not self.reason.strip():
            raise ValueError("design_gate reason must be explicit")
        return self


class WorkContractTemplate(StrictModel):
    schema_version: str
    record_type: Literal["work_contract"]
    status: Literal["draft"]
    identity: TemplateIdentity
    intent: dict[str, Any]
    inputs: dict[str, Any]
    boundaries: WorkContractBoundaries
    design_gate: DesignGate
    outputs: dict[str, Any]
    evidence_and_verification: dict[str, Any]
    continuation: dict[str, Any]


class EvidenceRecordTemplate(StrictModel):
    schema_version: str
    record_type: Literal["evidence_record"]
    status: Literal["draft"]
    identity: TemplateIdentity
    sources: EvidenceSources
    change: ChangeRefs
    verification_summary: VerificationSummary
    human_gate: HumanGate
    observations: EvidenceObservations
    limits: EvidenceLimits


class VerificationRecordTemplate(StrictModel):
    schema_version: str
    record_type: Literal["verification_record"]
    status: Literal["draft"]
    identity: TemplateIdentity
    checks: list[VerificationCheck]
    unverified_surfaces: list[str]
    residual_risk: list[str]
    human_gate: HumanGate
    next_action: Literal["complete", "rework", "review", "continue"]

    @model_validator(mode="after")
    def verification_record_must_be_explicit(self) -> Self:
        if not self.checks:
            raise ValueError("checks must be explicit")
        if not self.unverified_surfaces:
            raise ValueError("unverified_surfaces must use explicit values such as 'none'")
        if not self.residual_risk:
            raise ValueError("residual_risk must use explicit values such as 'none'")
        return self


class ReworkRecordTemplate(StrictModel):
    schema_version: str
    record_type: Literal["rework_record"]
    status: Literal["draft"]
    identity: TemplateIdentity
    rework: dict[str, Any]
    closure: dict[str, Any]


class ProjectStorageMapTemplate(StrictModel):
    schema_version: str
    record_type: Literal["project_storage_map"]
    status: Literal["draft"]
    project: dict[str, Any]
    canonical_records: dict[str, Any]
    overlays: list[dict[str, Any]]
    rules: dict[str, Any]


def normalize_prefix(raw_path: str) -> str:
    return raw_path.strip().lstrip("./").rstrip("/")


def prefixes_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/")


def load_yaml(relative_path: str) -> dict[str, Any]:
    raw_data: object = yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))
    assert isinstance(raw_data, dict), relative_path
    return cast(dict[str, Any], raw_data)


def test_templates_validate_with_pydantic_models() -> None:
    cases: tuple[tuple[str, type[BaseModel]], ...] = (
        ("templates/work-contract.yaml", WorkContractTemplate),
        ("templates/evidence-record.yaml", EvidenceRecordTemplate),
        ("templates/verification-record.yaml", VerificationRecordTemplate),
        ("templates/rework-record.yaml", ReworkRecordTemplate),
        ("templates/project-storage-map.yaml", ProjectStorageMapTemplate),
        ("templates/parallel-lane-map.yaml", ParallelLaneMapTemplate),
    )

    for relative_path, model in cases:
        model.model_validate(load_yaml(relative_path))


def test_evidence_record_rejects_missing_source_refs() -> None:
    data = load_yaml("templates/evidence-record.yaml")
    sources = cast(dict[str, Any], data["sources"])
    sources["source_refs"] = []

    with pytest.raises(ValidationError):
        EvidenceRecordTemplate.model_validate(data)


def test_evidence_record_rejects_invalid_confidence() -> None:
    data = load_yaml("templates/evidence-record.yaml")
    limits = cast(dict[str, Any], data["limits"])
    limits["confidence"] = "certain"

    with pytest.raises(ValidationError):
        EvidenceRecordTemplate.model_validate(data)


def test_verification_record_rejects_invalid_result() -> None:
    data = load_yaml("templates/verification-record.yaml")
    checks = cast(list[dict[str, Any]], data["checks"])
    checks[0]["result"] = "unknown"

    with pytest.raises(ValidationError):
        VerificationRecordTemplate.model_validate(data)


def test_verification_record_rejects_skipped_check_without_reason() -> None:
    data = load_yaml("templates/verification-record.yaml")
    checks = cast(list[dict[str, Any]], data["checks"])
    checks[1]["notes"] = ""

    with pytest.raises(ValidationError):
        VerificationRecordTemplate.model_validate(data)


def test_work_contract_rejects_significant_design_without_skill() -> None:
    data = load_yaml("templates/work-contract.yaml")
    design_gate = cast(dict[str, Any], data["design_gate"])
    design_gate["architecture_significance"] = "significant"
    design_gate["system_design_skill_required"] = False

    with pytest.raises(ValidationError):
        WorkContractTemplate.model_validate(data)


def test_work_contract_rejects_non_significant_design_with_skill() -> None:
    data = load_yaml("templates/work-contract.yaml")
    design_gate = cast(dict[str, Any], data["design_gate"])
    design_gate["architecture_significance"] = "local"
    design_gate["system_design_skill_required"] = True

    with pytest.raises(ValidationError):
        WorkContractTemplate.model_validate(data)


def test_parallel_lane_map_rejects_duplicate_lane_names() -> None:
    data = load_yaml("templates/parallel-lane-map.yaml")
    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[1]["lane"] = lanes[0]["lane"]
    lanes[1]["branch_target"] = "agent/<work-id>/docs/<short-slug-2>"
    lanes[1]["worktree_target"] = "../worktrees/<repo>/<work-id>-docs-2"

    with pytest.raises(ValidationError):
        ParallelLaneMapTemplate.model_validate(data)


def test_parallel_lane_map_rejects_contextless_lanes() -> None:
    data = load_yaml("templates/parallel-lane-map.yaml")
    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["source_refs"] = []

    with pytest.raises(ValidationError):
        ParallelLaneMapTemplate.model_validate(data)


def test_parallel_lane_map_rejects_no_overlap_path_collisions() -> None:
    data = load_yaml("templates/parallel-lane-map.yaml")
    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["allowed_write_targets"] = ["docs/"]
    lanes[1]["allowed_write_targets"] = ["docs/reference/"]

    with pytest.raises(ValidationError):
        ParallelLaneMapTemplate.model_validate(data)

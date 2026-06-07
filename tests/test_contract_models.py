from pathlib import Path
from typing import Any, Literal, Self, cast

import pytest
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

ROOT = Path(__file__).resolve().parents[1]

REQ_ID_PREFIX = "REQ-"
AC_ID_PREFIX = "AC-"
INC_ID_PREFIX = "INC-"
CHECK_RESULTS = {"passed", "failed", "blocked", "skipped", "not_applicable"}
CHECK_RESULT_TEMPLATE = "passed | failed | blocked | skipped | not_applicable"
SPEC_REVIEW_DECISIONS = {"approved_for_human_review", "rework"}
SPEC_REVIEW_DECISION_TEMPLATE = "approved_for_human_review | rework"
SPEC_REVIEW_NEXT_ACTIONS = {"human_spec_review", "rework"}
SPEC_REVIEW_NEXT_ACTION_TEMPLATE = "human_spec_review | rework"
WORKFLOW_PHASES = {
    "goal_set",
    "specification_draft",
    "specification_review",
    "human_spec_review",
    "approved_spec_freeze",
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
    "blocked",
}
WORKFLOW_PHASE_TEMPLATE = (
    "goal_set | specification_draft | specification_review | human_spec_review | "
    "approved_spec_freeze | lane_mapping | parallel_build | parallel_review | "
    "integration_review | inconsistency_check | rework_execution | convergence_check | "
    "final_handoff | human_final_review | complete | blocked"
)
WORKFLOW_NEXT_ACTIONS = (WORKFLOW_PHASES - {"goal_set"}) | {"rework"}
WORKFLOW_NEXT_ACTION_TEMPLATE = (
    "specification_draft | specification_review | human_spec_review | approved_spec_freeze | "
    "lane_mapping | parallel_build | parallel_review | integration_review | "
    "rework_execution | convergence_check | final_handoff | human_final_review | "
    "complete | rework | blocked"
)
HUMAN_GATE_STATUSES = {"required", "approved", "blocked", "not_applicable"}
HUMAN_GATE_STATUS_TEMPLATE = "required | approved | blocked | not_applicable"
INCONSISTENCY_TYPES = {
    "spec_vs_implementation",
    "implementation_vs_tests",
    "lane_conflict",
    "missing_requirement",
    "verification_gap",
    "human_decision_required",
}
INCONSISTENCY_TYPE_TEMPLATE = (
    "spec_vs_implementation | implementation_vs_tests | lane_conflict | "
    "missing_requirement | verification_gap | human_decision_required"
)
INCONSISTENCY_SEVERITIES = {"critical", "high", "medium", "low"}
INCONSISTENCY_SEVERITY_TEMPLATE = "critical | high | medium | low"
INCONSISTENCY_STATUSES = {"open", "in_rework", "resolved", "accepted_residual", "blocked"}
INCONSISTENCY_STATUS_TEMPLATE = "open | in_rework | resolved | accepted_residual | blocked"
INCONSISTENCY_NEXT_ACTIONS = {"rework", "human_review", "convergence_check", "blocked"}
INCONSISTENCY_NEXT_ACTION_TEMPLATE = "rework | human_review | convergence_check | blocked"
FORBIDDEN_OPERATIVE_SPEC_KEYS = {
    "implementation_refs",
    "implementation_policy_refs",
    "coding_style",
    "file_layout",
    "function_names",
    "class_names",
    "lint_rules",
    "library_choice",
    "branch_strategy",
    "worktree_commands",
    "test_command_selection",
    "refactor_strategy",
    "internal_algorithm_choice",
}
RUNTIME_STATE_KEY_TOKENS = {
    "queue",
    "queues",
    "lock",
    "locks",
    "heartbeat",
    "heartbeats",
    "polling",
    "dashboard",
    "dashboards",
    "scheduler",
    "schedulers",
}
BEHAVIOR_REDEFINITION_KEYS = {
    "behavior_contract",
    "requirements",
    "acceptance_criteria",
    "user_visible_behavior",
    "public_contract",
    "data_contract",
    "trust_boundary",
}


def ids_start_with(values: list[str], prefix: str) -> bool:
    return bool(values) and all(value.startswith(prefix) for value in values)


def reject_operational_spec_keys(data: object) -> None:
    def walk(value: object, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                if key_text in FORBIDDEN_OPERATIVE_SPEC_KEYS:
                    joined_path = ".".join((*path, key_text))
                    raise ValueError(
                        f"specification packet contains implementation key: {joined_path}"
                    )
                walk(item, (*path, key_text))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, (*path, str(index)))

    walk(data, ())


def reject_runtime_state_keys(data: object) -> None:
    def walk(value: object, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                tokens = set(key_text.lower().replace("-", "_").split("_"))
                if tokens & RUNTIME_STATE_KEY_TOKENS:
                    joined_path = ".".join((*path, key_text))
                    raise ValueError(f"workflow run contains runtime-state key: {joined_path}")
                walk(item, (*path, key_text))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, (*path, str(index)))

    walk(data, ())


def reject_behavior_redefinition_keys(data: object) -> None:
    def walk(value: object, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                if key_text in BEHAVIOR_REDEFINITION_KEYS:
                    joined_path = ".".join((*path, key_text))
                    raise ValueError(
                        f"implementation policy redefines behavior authority: {joined_path}"
                    )
                walk(item, (*path, key_text))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, (*path, str(index)))

    walk(data, ())


def require_non_empty_string_list(values: list[str], label: str) -> None:
    if not values or any(not value.strip() for value in values):
        raise ValueError(f"{label} must be a non-empty string list")


def require_allowed_or_template(
    value: str,
    allowed: set[str],
    template_value: str,
    label: str,
) -> None:
    if value not in allowed and value != template_value:
        raise ValueError(f"{label} must be one of {sorted(allowed)}")


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


class RequirementAcceptanceCriterion(StrictModel):
    id: str
    method: str
    expected_result: str

    @model_validator(mode="after")
    def acceptance_criterion_fields_must_be_explicit(self) -> Self:
        if not self.id.startswith(AC_ID_PREFIX):
            raise ValueError("acceptance criterion IDs must start with AC-")
        if not self.method.strip():
            raise ValueError("acceptance criterion method must be explicit")
        if not self.expected_result.strip():
            raise ValueError("acceptance criterion expected_result must be explicit")
        return self


class SpecificationRequirement(StrictModel):
    id: str
    statement: str
    observable_outcome: str
    acceptance_criteria: list[RequirementAcceptanceCriterion]
    non_goals: list[str]

    @model_validator(mode="after")
    def requirement_fields_must_be_explicit(self) -> Self:
        if not self.id.startswith(REQ_ID_PREFIX):
            raise ValueError("requirement IDs must start with REQ-")
        if not self.statement.strip():
            raise ValueError("requirement statement must be explicit")
        if not self.observable_outcome.strip():
            raise ValueError("observable_outcome must be explicit")
        if not self.acceptance_criteria:
            raise ValueError("acceptance_criteria must be explicit")
        return self


class SpecificationPacketIdentity(StrictModel):
    project_id: str
    spec_id: str
    goal_ref: str
    created_at: str


class SpecificationPacketScope(StrictModel):
    source_refs: list[str]
    denied_context: list[str]

    @model_validator(mode="after")
    def spec_scope_must_bound_context(self) -> Self:
        require_non_empty_string_list(self.source_refs, "scope.source_refs")
        required_denials = {"implementation_policy", "broad_repo_scan", "secrets"}
        if not required_denials <= set(self.denied_context):
            missing = sorted(required_denials - set(self.denied_context))
            raise ValueError(f"scope.denied_context must include {missing}")
        return self


class SpecificationBehaviorContract(StrictModel):
    requirements: list[SpecificationRequirement]

    @model_validator(mode="after")
    def requirements_must_be_explicit(self) -> Self:
        if not self.requirements:
            raise ValueError("behavior_contract.requirements must be explicit")
        return self


class SpecificationInterfaces(StrictModel):
    public_contracts: list[Any]
    data_contracts: list[Any]
    trust_boundaries: list[Any]
    side_effects: list[Any]


class SpecificationImplementationBoundary(StrictModel):
    allowed_in_spec: list[str]
    forbidden_in_spec: list[str]


class SpecificationVerificationExpectation(StrictModel):
    required_evidence: list[str]
    review_gate: str


class SpecificationHandoff(StrictModel):
    next_action: Literal["specification_review"]


class SpecificationPacketTemplate(StrictModel):
    schema_version: str
    record_type: Literal["specification_packet"]
    status: Literal["draft"]
    identity: SpecificationPacketIdentity
    scope: SpecificationPacketScope
    behavior_contract: SpecificationBehaviorContract
    interfaces: SpecificationInterfaces
    implementation_boundary: SpecificationImplementationBoundary
    verification_expectation: SpecificationVerificationExpectation
    handoff: SpecificationHandoff

    @model_validator(mode="before")
    @classmethod
    def reject_implementation_policy_leakage(cls, data: object) -> object:
        reject_operational_spec_keys(data)
        return data


class SpecificationReviewIdentity(StrictModel):
    project_id: str
    spec_id: str
    review_id: str
    created_at: str


class SpecificationReviewSources(StrictModel):
    source_refs: list[str]

    @model_validator(mode="after")
    def source_refs_must_be_explicit(self) -> Self:
        require_non_empty_string_list(self.source_refs, "sources.source_refs")
        return self


class SpecificationReviewCheck(StrictModel):
    name: str
    result: str
    evidence_ref: str
    notes: str

    @model_validator(mode="after")
    def check_result_must_be_valid(self) -> Self:
        require_allowed_or_template(
            self.result,
            CHECK_RESULTS,
            CHECK_RESULT_TEMPLATE,
            "review check result",
        )
        if not self.name.strip():
            raise ValueError("review check name must be explicit")
        if not self.evidence_ref.strip():
            raise ValueError("review check evidence_ref must be explicit")
        return self


class SpecificationReviewObservations(StrictModel):
    facts: list[str]
    inferences: list[str]
    decisions: list[str]


class SpecificationReviewDecision(StrictModel):
    result: str
    rework_required: list[str]
    next_action: str

    @model_validator(mode="after")
    def decision_must_be_valid(self) -> Self:
        require_allowed_or_template(
            self.result,
            SPEC_REVIEW_DECISIONS,
            SPEC_REVIEW_DECISION_TEMPLATE,
            "specification review decision",
        )
        require_allowed_or_template(
            self.next_action,
            SPEC_REVIEW_NEXT_ACTIONS,
            SPEC_REVIEW_NEXT_ACTION_TEMPLATE,
            "specification review next_action",
        )
        return self


class SpecificationReviewRecordTemplate(StrictModel):
    schema_version: str
    record_type: Literal["specification_review_record"]
    status: Literal["draft"]
    identity: SpecificationReviewIdentity
    sources: SpecificationReviewSources
    checks: list[SpecificationReviewCheck]
    observations: SpecificationReviewObservations
    unresolved_questions: list[str]
    human_gate: HumanGate
    decision: SpecificationReviewDecision

    @model_validator(mode="after")
    def checks_must_be_explicit(self) -> Self:
        if not self.checks:
            raise ValueError("checks must be explicit")
        return self


class ImplementationPolicyIdentity(StrictModel):
    project_id: str
    work_id: str
    lane: str
    policy_id: str
    created_at: str


class ImplementationPolicyScope(StrictModel):
    behavior_authority_ref: str
    requirement_ids: list[str]
    implementation_policy_refs: list[str]
    denied_context: list[str]

    @model_validator(mode="after")
    def scope_must_reference_behavior_authority(self) -> Self:
        if not self.behavior_authority_ref.strip():
            raise ValueError("scope.behavior_authority_ref must be explicit")
        require_non_empty_string_list(self.requirement_ids, "scope.requirement_ids")
        if not ids_start_with(self.requirement_ids, REQ_ID_PREFIX):
            raise ValueError("scope.requirement_ids must start with REQ-")
        require_non_empty_string_list(
            self.implementation_policy_refs,
            "scope.implementation_policy_refs",
        )
        return self


class ImplementationPolicyAuthorityBoundary(StrictModel):
    behavior_authority: Literal["approved_spec_ref_only"]
    policy_role: Literal["how_guidance_only"]
    must_not_redefine: list[str]

    @model_validator(mode="after")
    def behavior_redefinition_must_be_prohibited(self) -> Self:
        required = {"requirement_statement", "acceptance_criteria", "user_visible_behavior"}
        if not required <= set(self.must_not_redefine):
            missing = sorted(required - set(self.must_not_redefine))
            raise ValueError(f"authority_boundary.must_not_redefine must include {missing}")
        return self


class ImplementationPolicyRecordTemplate(StrictModel):
    schema_version: str
    record_type: Literal["implementation_policy_record"]
    status: Literal["draft"]
    identity: ImplementationPolicyIdentity
    scope: ImplementationPolicyScope
    authority_boundary: ImplementationPolicyAuthorityBoundary
    policy: dict[str, Any]
    verification: dict[str, Any]
    handoff: dict[str, Any]

    @model_validator(mode="before")
    @classmethod
    def must_not_redefine_behavior_authority(cls, data: object) -> object:
        if isinstance(data, dict):
            reject_behavior_redefinition_keys(data.get("policy"))
        return data


class WorkflowRunIdentity(StrictModel):
    project_id: str
    work_id: str
    goal_id: str
    created_at: str

    @model_validator(mode="after")
    def identity_must_be_explicit(self) -> Self:
        for field_name in ("project_id", "work_id", "created_at"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"identity.{field_name} must be explicit")
        return self


class WorkflowRunPhase(StrictModel):
    current: str
    next_action: str

    @model_validator(mode="after")
    def phase_must_use_known_states(self) -> Self:
        require_allowed_or_template(
            self.current,
            WORKFLOW_PHASES,
            WORKFLOW_PHASE_TEMPLATE,
            "workflow phase.current",
        )
        require_allowed_or_template(
            self.next_action,
            WORKFLOW_NEXT_ACTIONS,
            WORKFLOW_NEXT_ACTION_TEMPLATE,
            "workflow phase.next_action",
        )
        return self


class WorkflowRunRecordRefs(StrictModel):
    goal_ref: str
    approved_spec_ref: str
    spec_review_ref: str
    lane_map_ref: str
    work_contract_refs: list[str]
    build_result_refs: list[str]
    review_record_refs: list[str]
    integration_review_refs: list[str]
    inconsistency_register_ref: str
    rework_refs: list[str]
    convergence_check_ref: str
    final_handoff_ref: str


class WorkflowRunCommunicationRules(StrictModel):
    human_interface: Literal["main_lane_only"]
    subagent_to_human_direct: Literal["prohibited"]
    subagent_to_subagent_direct: Literal["prohibited"]
    state_authority: Literal["record_refs_not_conversation"]


class WorkflowRunGate(StrictModel):
    required: bool
    status: str
    evidence_ref: str

    @model_validator(mode="after")
    def gate_status_must_be_valid(self) -> Self:
        require_allowed_or_template(
            self.status,
            HUMAN_GATE_STATUSES,
            HUMAN_GATE_STATUS_TEMPLATE,
            "workflow human gate status",
        )
        return self


class WorkflowRunHumanGates(StrictModel):
    spec_approval: WorkflowRunGate
    final_merge: WorkflowRunGate


class WorkflowRunHandoff(StrictModel):
    next_action: str

    @model_validator(mode="after")
    def handoff_next_action_must_be_valid(self) -> Self:
        require_allowed_or_template(
            self.next_action,
            WORKFLOW_NEXT_ACTIONS,
            WORKFLOW_NEXT_ACTION_TEMPLATE,
            "workflow handoff.next_action",
        )
        return self


class WorkflowRunRecordTemplate(StrictModel):
    schema_version: str
    record_type: Literal["workflow_run_record"]
    status: Literal["draft"]
    identity: WorkflowRunIdentity
    phase: WorkflowRunPhase
    record_refs: WorkflowRunRecordRefs
    communication_rules: WorkflowRunCommunicationRules
    human_gates: WorkflowRunHumanGates
    open_questions: list[str]
    blocked_reasons: list[str]
    residual_risk: list[str]
    handoff: WorkflowRunHandoff

    @model_validator(mode="before")
    @classmethod
    def reject_runtime_state(cls, data: object) -> object:
        reject_runtime_state_keys(data)
        return data


class InconsistencyRegisterIdentity(StrictModel):
    project_id: str
    work_id: str
    register_id: str
    created_at: str


class InconsistencyRegisterScope(StrictModel):
    approved_spec_ref: str
    lane_map_ref: str
    source_refs: list[str]

    @model_validator(mode="after")
    def source_refs_must_be_explicit(self) -> Self:
        require_non_empty_string_list(self.source_refs, "scope.source_refs")
        return self


class InconsistencyClosure(StrictModel):
    resolved_by_refs: list[str]
    verification_ref: str
    residual_risk: list[str]


class InconsistencyItem(StrictModel):
    id: str
    type: str
    severity: str
    status: str
    summary: str
    requirement_ids: list[str]
    affected_lanes: list[str]
    evidence_refs: list[str]
    required_resolution: str
    owner_lane: str
    human_decision_required: bool
    rework_ref: str
    closure: InconsistencyClosure

    @model_validator(mode="after")
    def inconsistency_item_must_be_valid(self) -> Self:
        if not self.id.startswith(INC_ID_PREFIX):
            raise ValueError("inconsistency IDs must start with INC-")
        require_allowed_or_template(
            self.type,
            INCONSISTENCY_TYPES,
            INCONSISTENCY_TYPE_TEMPLATE,
            "inconsistency type",
        )
        require_allowed_or_template(
            self.severity,
            INCONSISTENCY_SEVERITIES,
            INCONSISTENCY_SEVERITY_TEMPLATE,
            "inconsistency severity",
        )
        require_allowed_or_template(
            self.status,
            INCONSISTENCY_STATUSES,
            INCONSISTENCY_STATUS_TEMPLATE,
            "inconsistency status",
        )
        if self.requirement_ids and not ids_start_with(self.requirement_ids, REQ_ID_PREFIX):
            raise ValueError("inconsistency requirement_ids must start with REQ-")
        actionable_high_item = self.status in {
            "open",
            "in_rework",
            "blocked",
        } and self.severity in {"critical", "high"}
        if (
            actionable_high_item
            and not self.owner_lane.strip()
            and not self.human_decision_required
        ):
            raise ValueError("open critical/high items require owner_lane or human decision path")
        return self


class InconsistencyRegisterHandoff(StrictModel):
    open_critical_or_high: bool
    next_action: str

    @model_validator(mode="after")
    def next_action_must_be_valid(self) -> Self:
        require_allowed_or_template(
            self.next_action,
            INCONSISTENCY_NEXT_ACTIONS,
            INCONSISTENCY_NEXT_ACTION_TEMPLATE,
            "inconsistency handoff.next_action",
        )
        return self


class InconsistencyRegisterTemplate(StrictModel):
    schema_version: str
    record_type: Literal["inconsistency_register"]
    status: Literal["draft"]
    identity: InconsistencyRegisterIdentity
    scope: InconsistencyRegisterScope
    items: list[InconsistencyItem]
    handoff: InconsistencyRegisterHandoff


class LaneMapSpecScope(StrictModel):
    approved_spec_ref: str
    spec_review_ref: str
    requirement_ids: list[str]

    @model_validator(mode="after")
    def spec_scope_must_be_explicit(self) -> Self:
        if not self.approved_spec_ref.strip():
            raise ValueError("spec_scope.approved_spec_ref must be explicit")
        if not self.spec_review_ref.strip():
            raise ValueError("spec_scope.spec_review_ref must be explicit")
        require_non_empty_string_list(self.requirement_ids, "spec_scope.requirement_ids")
        if not ids_start_with(self.requirement_ids, REQ_ID_PREFIX):
            raise ValueError("spec_scope.requirement_ids must start with REQ-")
        return self


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
    requirement_ids: list[str] | None = None
    implementation_policy_refs: list[str] | None = None

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

        if self.requirement_ids is not None:
            require_non_empty_string_list(self.requirement_ids, "lane.requirement_ids")
            if not ids_start_with(self.requirement_ids, REQ_ID_PREFIX):
                raise ValueError("lane.requirement_ids must start with REQ-")

        if self.implementation_policy_refs is not None:
            require_non_empty_string_list(
                self.implementation_policy_refs,
                "lane.implementation_policy_refs",
            )

        return self


class ParallelLaneMapTemplate(StrictModel):
    schema_version: str
    record_type: Literal["parallel_lane_map"]
    status: Literal["draft", "active", "review", "complete"]
    identity: LaneMapIdentity
    governance: LaneMapGovernance
    git_scope: LaneMapGitScope
    spec_scope: LaneMapSpecScope | None = None
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
        if self.spec_scope is not None:
            scoped_requirement_ids = set(self.spec_scope.requirement_ids)
            for lane in self.lanes:
                if lane.requirement_ids is None:
                    continue
                outside_scope = sorted(set(lane.requirement_ids) - scoped_requirement_ids)
                if outside_scope:
                    raise ValueError(f"lane requirement_ids outside spec_scope: {outside_scope}")
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
    execution: dict[str, Any]
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
        ("templates/specification-packet.yaml", SpecificationPacketTemplate),
        ("templates/specification-review-record.yaml", SpecificationReviewRecordTemplate),
        ("templates/implementation-policy-record.yaml", ImplementationPolicyRecordTemplate),
        ("templates/workflow-run-record.yaml", WorkflowRunRecordTemplate),
        ("templates/inconsistency-register.yaml", InconsistencyRegisterTemplate),
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


def test_specification_packet_rejects_implementation_policy_refs() -> None:
    data = load_yaml("templates/specification-packet.yaml")
    data["implementation_policy_refs"] = ["pyproject.toml"]

    with pytest.raises(ValidationError):
        SpecificationPacketTemplate.model_validate(data)


def test_specification_packet_rejects_operational_implementation_keys() -> None:
    data = load_yaml("templates/specification-packet.yaml")
    behavior_contract = cast(dict[str, Any], data["behavior_contract"])
    requirements = cast(list[dict[str, Any]], behavior_contract["requirements"])
    requirements[0]["library_choice"] = "Use a specific internal library."

    with pytest.raises(ValidationError):
        SpecificationPacketTemplate.model_validate(data)


def test_specification_review_rejects_invalid_decision() -> None:
    data = load_yaml("templates/specification-review-record.yaml")
    decision = cast(dict[str, Any], data["decision"])
    decision["result"] = "approved_without_human_review"

    with pytest.raises(ValidationError):
        SpecificationReviewRecordTemplate.model_validate(data)


def test_implementation_policy_requires_behavior_authority_ref() -> None:
    data = load_yaml("templates/implementation-policy-record.yaml")
    scope = cast(dict[str, Any], data["scope"])
    scope["behavior_authority_ref"] = ""

    with pytest.raises(ValidationError):
        ImplementationPolicyRecordTemplate.model_validate(data)


def test_implementation_policy_rejects_behavior_redefinition_in_policy() -> None:
    data = load_yaml("templates/implementation-policy-record.yaml")
    policy = cast(dict[str, Any], data["policy"])
    policy["requirements"] = ["Redefine behavior from inside HOW guidance."]

    with pytest.raises(ValidationError):
        ImplementationPolicyRecordTemplate.model_validate(data)


def test_workflow_run_rejects_runtime_state_fields() -> None:
    data = load_yaml("templates/workflow-run-record.yaml")
    data["worker_heartbeats"] = []

    with pytest.raises(ValidationError):
        WorkflowRunRecordTemplate.model_validate(data)


def test_inconsistency_register_rejects_invalid_inc_id() -> None:
    data = load_yaml("templates/inconsistency-register.yaml")
    items = cast(list[dict[str, Any]], data["items"])
    items[0]["id"] = "ISSUE-001"

    with pytest.raises(ValidationError):
        InconsistencyRegisterTemplate.model_validate(data)


def test_parallel_lane_map_rejects_lane_requirement_outside_spec_scope() -> None:
    data = load_yaml("templates/parallel-lane-map.yaml")
    data["spec_scope"] = {
        "approved_spec_ref": "artifact/<project-id>/output/specs/<spec-id>.md",
        "spec_review_ref": "artifact/<project-id>/evidence/spec-review-<review-id>.yaml",
        "requirement_ids": ["REQ-001"],
    }
    lanes = cast(list[dict[str, Any]], data["lanes"])
    lanes[0]["requirement_ids"] = ["REQ-999"]

    with pytest.raises(ValidationError):
        ParallelLaneMapTemplate.model_validate(data)

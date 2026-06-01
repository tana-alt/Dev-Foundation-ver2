"""Deterministic context routing for normalized earnings-review requests.

The router intentionally uses an approximate token counter instead of a provider
tokenizer.  The estimate serializes routed context as stable compact JSON and
rounds ``character_count / 4`` up to the next integer.  This is conservative
enough for pre-invocation budget gates and remains deterministic in tests.
"""

from __future__ import annotations

import json
from math import ceil
from typing import Any, Mapping

from pydantic import BaseModel, Field

from src.workflow_models import (
    AgentRole,
    ContextBudget,
    DocumentSection,
    NormalizedReviewRequest,
    SourceManifestEntry,
    SourceRef,
    WorkflowModel,
    validate_source_ref_registered_and_consistent,
)

APPROX_TOKEN_COUNTER_NAME = "approx_json_chars_div_4_v1"


ROLE_CONTEXT_KEYS: dict[AgentRole, tuple[str, ...]] = {
    AgentRole.EARNINGS_QUALITY: (
        "run_spec",
        "earnings_quality_metrics",
        "earnings_quality_sections",
        "source_index",
        "analysis_config",
    ),
    AgentRole.CASH_FLOW_RISK: (
        "run_spec",
        "cash_flow_risk_metrics",
        "cash_flow_risk_sections",
        "cash_conversion_inputs",
        "source_index",
        "analysis_config",
    ),
    AgentRole.MANAGEMENT_INTENT: (
        "run_spec",
        "financial_snapshot_minimal",
        "management_sections",
        "management_intent_sections",
        "strategy_sections",
        "mdna_sections",
        "risk_sections",
        "source_index",
        "analysis_config",
    ),
    AgentRole.GUIDANCE: (
        "run_spec",
        "guidance_metrics",
        "guidance_consensus_deltas",
        "consensus_deltas",
        "guidance_sections",
        "guidance_assumptions_sections",
        "prior_guidance_track_record",
        "management_intent_handoff",
        "source_index",
        "analysis_config",
    ),
    AgentRole.BULL: (
        "run_spec",
        "financial_snapshot_summary",
        "analysis_brief",
        "earnings_quality_finding",
        "cash_flow_risk_finding",
        "management_intent_finding",
        "guidance_finding",
        "positive_evidence_pool",
        "negative_evidence_pool",
        "disputed_points",
        "missing_data",
    ),
    AgentRole.BEAR: (
        "run_spec",
        "financial_snapshot_summary",
        "analysis_brief",
        "earnings_quality_finding",
        "cash_flow_risk_finding",
        "management_intent_finding",
        "guidance_finding",
        "bull_case_summary",
        "positive_evidence_pool",
        "negative_evidence_pool",
        "disputed_points",
        "missing_data",
    ),
    AgentRole.JUDGE: (
        "run_spec",
        "financial_snapshot_summary",
        "analysis_brief",
        "bull_case",
        "bear_case",
    ),
}


class ContextRouterError(ValueError):
    """Base error for deterministic context routing failures."""


class ContextSourceScopeError(ContextRouterError):
    """Raised when routed context references a source outside the manifest."""


class ContextBudgetExceeded(ContextRouterError):
    """Raised when routed context does not fit the request context budget."""

    def __init__(self, report: "ContextBudgetReport"):
        self.report = report
        failed_roles = ", ".join(failure.role.value for failure in report.failures)
        super().__init__(f"context budget exceeded for role(s): {failed_roles}")


class RoutedRoleContext(WorkflowModel):
    role: AgentRole
    context: dict[str, Any]
    context_keys: list[str]
    routed_source_ids: list[str]
    estimated_input_tokens: int = Field(ge=1)


class RoleBudgetEstimate(WorkflowModel):
    role: AgentRole
    context_keys: list[str]
    estimated_input_tokens: int = Field(ge=1)
    max_input_tokens: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    max_total_tokens: int = Field(gt=0)
    estimated_total_tokens: int = Field(gt=0)
    within_budget: bool
    failure_reasons: list[str] = Field(default_factory=list)


class ContextBudgetReport(WorkflowModel):
    token_counter: str
    estimates: list[RoleBudgetEstimate]
    failures: list[RoleBudgetEstimate]
    within_budget: bool


class RoutedContextBundle(WorkflowModel):
    request_id: str
    ticker: str
    fiscal_period: str
    by_role: dict[AgentRole, RoutedRoleContext]
    budget_report: ContextBudgetReport


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def approximate_token_count(value: Any) -> int:
    """Return the deterministic approximate input-token count used by the router."""

    stable_json = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return max(1, ceil(len(stable_json) / 4))


class ContextRouter:
    """Build source-scoped role contexts from normalized review input."""

    def route(self, request: NormalizedReviewRequest) -> RoutedContextBundle:
        role_contexts = self._build_role_contexts(request)
        budget_report = self._build_budget_report(role_contexts, request.context_budget)
        if not budget_report.within_budget:
            raise ContextBudgetExceeded(budget_report)

        return RoutedContextBundle(
            request_id=request.request_id,
            ticker=request.ticker,
            fiscal_period=request.fiscal_period,
            by_role=role_contexts,
            budget_report=budget_report,
        )

    def check_budget(self, request: NormalizedReviewRequest) -> ContextBudgetReport:
        """Return the deterministic budget report without invoking any provider."""

        role_contexts = self._build_role_contexts(request)
        return self._build_budget_report(role_contexts, request.context_budget)

    def _build_role_contexts(
        self,
        request: NormalizedReviewRequest,
    ) -> dict[AgentRole, RoutedRoleContext]:
        self._validate_source_scope(request)

        sections_by_topic = self._sections_by_topic(request.document_sections)
        metrics_json = request.financial_metrics.model_dump(mode="json", exclude_none=True)
        financial_source_ids = [
            source_ref.source_id for source_ref in request.financial_metrics.source_refs
        ]

        raw_contexts: dict[AgentRole, tuple[dict[str, Any], list[str]]] = {
            AgentRole.EARNINGS_QUALITY: (
                {
                    "run_spec": self._run_spec(request),
                    "earnings_quality_metrics": metrics_json,
                    "earnings_quality_sections": (
                        sections_by_topic["eps"]
                        + sections_by_topic["revenue"]
                        + sections_by_topic["segments"]
                        + sections_by_topic["other"]
                    ),
                    "analysis_config": self._analysis_config(),
                },
                [
                    *financial_source_ids,
                    *self._source_ids_for_topics(
                        request.document_sections,
                        {"eps", "revenue", "segments", "other"},
                    ),
                ],
            ),
            AgentRole.CASH_FLOW_RISK: (
                {
                    "run_spec": self._run_spec(request),
                    "cash_flow_risk_metrics": metrics_json,
                    "cash_flow_risk_sections": (
                        sections_by_topic["other"]
                        + sections_by_topic["risk"]
                        + sections_by_topic["guidance"]
                    ),
                    "cash_conversion_inputs": metrics_json,
                    "analysis_config": self._analysis_config(),
                },
                [
                    *financial_source_ids,
                    *self._source_ids_for_topics(
                        request.document_sections,
                        {"other", "risk", "guidance"},
                    ),
                ],
            ),
            AgentRole.MANAGEMENT_INTENT: (
                {
                    "run_spec": self._run_spec(request),
                    "financial_snapshot_minimal": self._minimal_snapshot(metrics_json),
                    "management_sections": (
                        sections_by_topic["guidance"] + sections_by_topic["segments"]
                    ),
                    "management_intent_sections": (
                        sections_by_topic["guidance"]
                        + sections_by_topic["segments"]
                        + sections_by_topic["other"]
                    ),
                    "strategy_sections": sections_by_topic["segments"] + sections_by_topic["other"],
                    "mdna_sections": sections_by_topic["other"],
                    "risk_sections": sections_by_topic["risk"],
                    "analysis_config": self._analysis_config(),
                },
                [
                    *financial_source_ids,
                    *self._source_ids_for_topics(
                        request.document_sections,
                        {"guidance", "segments", "other", "risk"},
                    ),
                ],
            ),
            AgentRole.GUIDANCE: (
                {
                    "run_spec": self._run_spec(request),
                    "guidance_metrics": metrics_json,
                    "guidance_consensus_deltas": metrics_json,
                    "consensus_deltas": metrics_json,
                    "guidance_sections": sections_by_topic["guidance"],
                    "guidance_assumptions_sections": (
                        sections_by_topic["guidance"] + sections_by_topic["risk"]
                    ),
                    "prior_guidance_track_record": [],
                    "management_intent_handoff": None,
                    "analysis_config": self._analysis_config(),
                },
                [
                    *financial_source_ids,
                    *self._source_ids_for_topics(request.document_sections, {"guidance", "risk"}),
                ],
            ),
            AgentRole.BULL: (
                {
                    "run_spec": self._run_spec(request),
                    "financial_snapshot_summary": self._minimal_snapshot(metrics_json),
                },
                [],
            ),
            AgentRole.BEAR: (
                {
                    "run_spec": self._run_spec(request),
                    "financial_snapshot_summary": self._minimal_snapshot(metrics_json),
                },
                [],
            ),
            AgentRole.JUDGE: (
                {
                    "run_spec": self._run_spec(request),
                    "financial_snapshot_summary": self._minimal_snapshot(metrics_json),
                },
                [],
            ),
        }

        return {
            role: self._finalize_role_context(
                role,
                raw_context,
                routed_source_ids,
                request.source_manifest,
            )
            for role, (raw_context, routed_source_ids) in raw_contexts.items()
        }

    def _finalize_role_context(
        self,
        role: AgentRole,
        raw_context: Mapping[str, Any],
        routed_source_ids: list[str],
        source_manifest: list[SourceManifestEntry],
    ) -> RoutedRoleContext:
        allowed_keys = ROLE_CONTEXT_KEYS[role]
        context = {
            key: raw_context[key]
            for key in allowed_keys
            if key in raw_context and raw_context[key] is not None
        }

        source_ids = self._dedupe_in_manifest_order(routed_source_ids, source_manifest)
        if source_ids and "source_index" in allowed_keys:
            context["source_index"] = self._source_index(source_ids, source_manifest)

        context_keys = sorted(context)
        return RoutedRoleContext(
            role=role,
            context=context,
            context_keys=context_keys,
            routed_source_ids=source_ids if "source_index" in context else [],
            estimated_input_tokens=approximate_token_count(context),
        )

    def _validate_source_scope(self, request: NormalizedReviewRequest) -> None:
        registered_ids = {source.source_id for source in request.source_manifest}
        if len(registered_ids) != len(request.source_manifest):
            raise ContextSourceScopeError("source_manifest.source_id values must be unique")

        for section in request.document_sections:
            self._validate_source_ref(
                section.source_ref,
                request.source_manifest,
                "document_sections",
            )

        for source_ref in request.financial_metrics.source_refs:
            self._validate_source_ref(
                source_ref,
                request.source_manifest,
                "financial_metrics.source_refs",
            )

    def _validate_source_ref(
        self,
        source_ref: SourceRef,
        source_manifest: list[SourceManifestEntry],
        context: str,
    ) -> None:
        try:
            validate_source_ref_registered_and_consistent(
                source_ref,
                source_manifest,
                context,
            )
        except ValueError as exc:
            raise ContextSourceScopeError(str(exc)) from exc

    def _source_index(
        self,
        source_ids: list[str],
        source_manifest: list[SourceManifestEntry],
    ) -> list[dict[str, Any]]:
        manifest_by_id = {source.source_id: source for source in source_manifest}
        source_index: list[dict[str, Any]] = []
        for source_id in source_ids:
            source = manifest_by_id.get(source_id)
            if source is None:
                raise ContextSourceScopeError(f"unregistered routed source_id: {source_id}")
            source_index.append(source.model_dump(mode="json", exclude_none=True))
        return source_index

    def _dedupe_in_manifest_order(
        self,
        source_ids: list[str],
        source_manifest: list[SourceManifestEntry],
    ) -> list[str]:
        requested = set(source_ids)
        manifest_ordered = [
            source.source_id for source in source_manifest if source.source_id in requested
        ]
        missing = sorted(requested.difference(manifest_ordered))
        if missing:
            raise ContextSourceScopeError(f"unregistered routed source_id: {missing[0]}")
        return manifest_ordered

    def _build_budget_report(
        self,
        role_contexts: Mapping[AgentRole, RoutedRoleContext],
        budget: ContextBudget,
    ) -> ContextBudgetReport:
        estimates: list[RoleBudgetEstimate] = []
        for role_context in role_contexts.values():
            estimated_total = role_context.estimated_input_tokens + budget.max_output_tokens
            failure_reasons: list[str] = []
            if role_context.estimated_input_tokens > budget.max_input_tokens:
                failure_reasons.append("estimated_input_tokens exceeds max_input_tokens")
            if estimated_total > budget.max_total_tokens:
                failure_reasons.append(
                    "estimated_input_tokens plus max_output_tokens exceeds max_total_tokens"
                )

            estimates.append(
                RoleBudgetEstimate(
                    role=role_context.role,
                    context_keys=role_context.context_keys,
                    estimated_input_tokens=role_context.estimated_input_tokens,
                    max_input_tokens=budget.max_input_tokens,
                    max_output_tokens=budget.max_output_tokens,
                    max_total_tokens=budget.max_total_tokens,
                    estimated_total_tokens=estimated_total,
                    within_budget=not failure_reasons,
                    failure_reasons=failure_reasons,
                )
            )

        failures = [estimate for estimate in estimates if not estimate.within_budget]
        return ContextBudgetReport(
            token_counter=APPROX_TOKEN_COUNTER_NAME,
            estimates=estimates,
            failures=failures,
            within_budget=not failures,
        )

    def _run_spec(self, request: NormalizedReviewRequest) -> dict[str, Any]:
        return {
            "schema_version": request.schema_version,
            "request_id": request.request_id,
            "ticker": request.ticker,
            "fiscal_period": request.fiscal_period,
            "purpose": request.purpose,
            "is_investment_advice": request.is_investment_advice,
        }

    def _analysis_config(self) -> dict[str, Any]:
        return {
            "max_retry": 1,
            "not_investment_advice": True,
        }

    def _minimal_snapshot(self, metrics_json: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: metrics_json.get(key)
            for key in (
                "ticker",
                "fiscal_period",
                "revenue",
                "revenue_surprise_pct",
                "eps",
                "eps_surprise_pct",
                "operating_margin_pct",
                "operating_cash_flow",
                "free_cash_flow",
                "capex",
                "guidance",
            )
            if key in metrics_json
        }

    def _sections_by_topic(
        self,
        sections: list[DocumentSection],
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {
            name: [] for name in ("eps", "revenue", "guidance", "segments", "risk", "other")
        }
        for section in sections:
            grouped[self._infer_topic(section)].append(
                section.model_dump(mode="json", exclude_none=True)
            )
        return grouped

    def _source_ids_for_topics(
        self,
        sections: list[DocumentSection],
        topics: set[str],
    ) -> list[str]:
        return [
            section.source_ref.source_id
            for section in sections
            if self._infer_topic(section) in topics
        ]

    def _infer_topic(self, section: DocumentSection) -> str:
        label = f"{section.section_id} {section.heading}".lower()
        if "eps" in label or "earnings" in label:
            return "eps"
        if "guidance" in label or "outlook" in label:
            return "guidance"
        if "segment" in label:
            return "segments"
        if "risk" in label:
            return "risk"
        if "revenue" in label or "sales" in label:
            return "revenue"
        return "other"

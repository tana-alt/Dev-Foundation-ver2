import pytest

from src.context_router import (
    APPROX_TOKEN_COUNTER_NAME,
    ROLE_CONTEXT_KEYS,
    ContextBudgetExceeded,
    ContextRouter,
    ContextSourceScopeError,
)
from src.workflow_models import (
    AgentRole,
    ContextBudget,
    DocumentSection,
    FinancialMetrics,
    NormalizedReviewRequest,
    SourceManifestEntry,
    SourceRef,
    SourceType,
)


def financial_ref(source_id: str, metric_name: str) -> SourceRef:
    return SourceRef(
        source_id=source_id,
        source_type=SourceType.FINANCIAL_API,
        metric_name=metric_name,
        reported_period="2025Q3",
    )


def document_ref(source_id: str, section_id: str) -> SourceRef:
    return SourceRef(
        source_id=source_id,
        source_type=SourceType.FILING,
        document_id="10q-2025q3",
        section_id=section_id,
        page=3,
        reported_period="2025Q3",
    )


def manifest_entry(source_id: str, section_id: str | None = None) -> SourceManifestEntry:
    if section_id is None:
        metric_name = source_id.rsplit(":", maxsplit=1)[-1]
        return SourceManifestEntry(
            source_id=source_id,
            source_type=SourceType.FINANCIAL_API,
            title=f"{metric_name} API metric",
            metric_name=metric_name,
            reported_period="2025Q3",
        )

    return SourceManifestEntry(
        source_id=source_id,
        source_type=SourceType.FILING,
        title=f"{section_id} filing section",
        document_id="10q-2025q3",
        section_id=section_id,
        page=3,
        reported_period="2025Q3",
    )


def section(section_id: str, heading: str, text: str) -> DocumentSection:
    return DocumentSection(
        section_id=section_id,
        source_ref=document_ref(f"filing:{section_id}", section_id),
        heading=heading,
        text=text,
    )


def normalized_request(*, section_text: str = "Short source text.") -> NormalizedReviewRequest:
    return NormalizedReviewRequest(
        schema_version="review_input.v1",
        request_id="req-context-router-1",
        ticker="NVDA",
        fiscal_period="2025Q3",
        financial_metrics=FinancialMetrics(
            ticker="NVDA",
            fiscal_period="2025Q3",
            revenue=3000,
            revenue_consensus=2900,
            eps=1.25,
            eps_consensus=1.10,
            operating_cash_flow=900,
            capex=-300,
            free_cash_flow=600,
            guidance="Revenue outlook remains constructive with elevated investment.",
            source_refs=[
                financial_ref("api:eps", "eps"),
                financial_ref("api:free_cash_flow", "free_cash_flow"),
            ],
        ),
        document_sections=[
            section("eps", "EPS and earnings quality", section_text),
            section("guidance", "Guidance outlook", "Management raised revenue guidance."),
            section("risk", "Risk factors", "Working capital and capex remain risk factors."),
            section("segments", "Segment performance", "Segment mix improved."),
        ],
        source_manifest=[
            manifest_entry("api:eps"),
            manifest_entry("api:free_cash_flow"),
            manifest_entry("filing:eps", "eps"),
            manifest_entry("filing:guidance", "guidance"),
            manifest_entry("filing:risk", "risk"),
            manifest_entry("filing:segments", "segments"),
        ],
        context_budget=ContextBudget(
            max_input_tokens=50_000,
            max_output_tokens=2_000,
            max_total_tokens=60_000,
        ),
        include_markdown=True,
        purpose="earnings_review_not_investment_advice",
        is_investment_advice=False,
        dry_run=True,
    )


def routed_source_ids(role_context) -> list[str]:
    return [entry["source_id"] for entry in role_context.context.get("source_index", [])]


def test_router_limits_each_role_to_allowed_context_keys_and_registered_sources():
    request = normalized_request()

    routed = ContextRouter().route(request)

    assert set(routed.by_role) == set(AgentRole)
    for role, role_context in routed.by_role.items():
        assert set(role_context.context) <= set(ROLE_CONTEXT_KEYS[role])
        assert role_context.context_keys == sorted(role_context.context)
        assert routed_source_ids(role_context) == role_context.routed_source_ids
        assert set(role_context.routed_source_ids) <= request.registered_source_ids

    assert "filing:eps" in routed.by_role[AgentRole.EARNINGS_QUALITY].routed_source_ids
    assert "filing:guidance" not in routed.by_role[AgentRole.EARNINGS_QUALITY].routed_source_ids
    assert "filing:risk" in routed.by_role[AgentRole.CASH_FLOW_RISK].routed_source_ids
    assert "filing:guidance" in routed.by_role[AgentRole.GUIDANCE].routed_source_ids
    assert "filing:risk" in routed.by_role[AgentRole.GUIDANCE].routed_source_ids
    assert "source_index" not in routed.by_role[AgentRole.BULL].context
    assert "source_index" not in routed.by_role[AgentRole.BEAR].context
    assert "source_index" not in routed.by_role[AgentRole.JUDGE].context


def test_router_rejects_routed_source_id_removed_from_manifest_after_validation():
    request = normalized_request()
    request.source_manifest[:] = [
        source for source in request.source_manifest if source.source_id != "filing:eps"
    ]

    with pytest.raises(ContextSourceScopeError, match="unregistered source_id.*filing:eps"):
        ContextRouter().route(request)


def test_router_rejects_duplicate_manifest_ids_after_request_validation():
    request = normalized_request()
    request.source_manifest[1].source_id = "api:eps"

    with pytest.raises(
        ContextSourceScopeError, match="source_manifest.source_id values must be unique"
    ):
        ContextRouter().route(request)


def test_router_rejects_manifest_source_ref_mismatch_after_request_validation():
    request = normalized_request()
    request.source_manifest[2].section_id = "different-eps"

    with pytest.raises(ContextSourceScopeError, match="source_manifest mismatch.*section_id"):
        ContextRouter().route(request)


def test_budget_report_uses_deterministic_approximate_token_count_and_flags_failures():
    request = normalized_request(section_text="Margin expansion supported EPS quality. " * 80)
    request.context_budget = ContextBudget(
        max_input_tokens=50,
        max_output_tokens=10,
        max_total_tokens=60,
    )

    report = ContextRouter().check_budget(request)

    assert report.token_counter == APPROX_TOKEN_COUNTER_NAME
    assert report.within_budget is False
    assert report.failures
    assert AgentRole.EARNINGS_QUALITY in {failure.role for failure in report.failures}
    assert all(failure.estimated_input_tokens > 50 for failure in report.failures)


def test_route_raises_budget_failure_before_returning_contexts():
    request = normalized_request(section_text="Cash conversion remained pressured. " * 80)
    request.context_budget = ContextBudget(
        max_input_tokens=50,
        max_output_tokens=10,
        max_total_tokens=60,
    )

    with pytest.raises(ContextBudgetExceeded) as exc_info:
        ContextRouter().route(request)

    assert exc_info.value.report.within_budget is False
    assert exc_info.value.report.failures

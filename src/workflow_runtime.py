"""Agent execution runtime for the earnings review workflow."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import BaseModel

from .llm import LLMProvider
from .workflow_agents import BearAgent, BullAgent, JudgeAgent
from .workflow_models import (
    AnalysisBrief,
    DebateResult,
    EvidenceItem,
    EvidencePolarity,
    FinancialMetrics,
    JudgeDecision,
    ReviewRequest,
)
from .workflow_validation import WorkflowValidationError, WorkflowValidationGate


class AgentRuntime:
    """Run independent specialist agents against a shared routed context."""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def run_parallel(self, agent_classes: tuple[type, ...], context: dict[str, Any]):
        with ThreadPoolExecutor(max_workers=len(agent_classes)) as executor:
            futures = [
                executor.submit(agent_class(self.llm).run, context) for agent_class in agent_classes
            ]
            return [future.result() for future in futures]


class DebateRunner:
    """Run Bull/Bear agents and validate their evidence selections."""

    def __init__(self, llm: LLMProvider, validator: WorkflowValidationGate):
        self.llm = llm
        self.validator = validator

    def run(
        self,
        request: ReviewRequest,
        metrics: FinancialMetrics,
        brief: AnalysisBrief,
    ) -> tuple[BaseModel, BaseModel, DebateResult]:
        context = {
            "run_spec": {"ticker": request.ticker, "fiscal_period": request.fiscal_period},
            "financial_snapshot_summary": metrics.model_dump(mode="json", exclude_none=True),
            "analysis_brief": brief,
            "earnings_quality_finding": brief.earnings_quality_finding,
            "cash_flow_risk_finding": brief.cash_flow_risk_finding,
            "management_intent_finding": brief.management_intent_finding,
            "guidance_finding": brief.guidance_finding,
            "positive_evidence_pool": brief.positive_evidence_pool,
            "negative_evidence_pool": brief.negative_evidence_pool,
            "valid_positive_evidence_ids": [
                item.evidence_id for item in brief.positive_evidence_pool
            ],
            "valid_negative_evidence_ids": [
                item.evidence_id for item in brief.negative_evidence_pool
            ],
            "disputed_points": brief.risk_evidence_pool,
            "missing_data": [],
        }
        positive_by_id = {item.evidence_id: item for item in brief.positive_evidence_pool}
        negative_by_id = {item.evidence_id: item for item in brief.negative_evidence_pool}

        bull_case, positive = self._run_case(
            BullAgent,
            context,
            "strongest_positive_evidence",
            positive_by_id,
            "bull_case",
            EvidencePolarity.POSITIVE,
        )
        bear_context = {
            **context,
            "bull_case_summary": {
                "thesis": self.validator.text_attr(bull_case, "thesis")
                or self.validator.text_attr(bull_case, "summary"),
                "weak_points": self.validator.list_attr(bull_case, "weak_points"),
                "finding_coverage": getattr(bull_case, "finding_coverage", {}),
            },
        }
        bear_case, negative = self._run_case(
            BearAgent,
            bear_context,
            "strongest_negative_evidence",
            negative_by_id,
            "bear_case",
            EvidencePolarity.NEGATIVE,
        )

        debate = DebateResult(
            bull_case=(self.validator.text_attr(bull_case, "thesis") or "Bull case was generated.")[
                :2000
            ],
            bear_case=(self.validator.text_attr(bear_case, "thesis") or "Bear case was generated.")[
                :2000
            ],
            risk_case="; ".join(item.summary for item in negative[:3])
            or "No unresolved risks were identified.",
            evaluation="Bull and Bear cases were generated from validated AnalysisBrief only.",
            strongest_positive_evidence=positive[:10],
            strongest_negative_evidence=negative[:10],
            unresolved_questions=self.validator.list_attr(bear_case, "unresolved_risks")[:8],
        )
        return bull_case, bear_case, debate

    def _run_case(
        self,
        agent_class: Any,
        context: dict[str, Any],
        evidence_field: str,
        evidence_by_id: dict[str, EvidenceItem],
        case_name: str,
        expected_polarity: EvidencePolarity,
    ) -> tuple[BaseModel, list[EvidenceItem]]:
        last_error: WorkflowValidationError | None = None
        for _ in range(2):
            run_context = context
            if last_error is not None:
                run_context = {
                    **context,
                    "evidence_validation_error": str(last_error),
                    "valid_evidence_ids": sorted(evidence_by_id),
                }
            case = agent_class(self.llm).run(run_context)
            self.validator.validate_finding_coverage(case, case_name)
            self.validator.validate_no_investment_advice_text(case, case_name)
            try:
                evidence = self.validator.validated_case_evidence(
                    case,
                    evidence_field,
                    evidence_by_id,
                    case_name,
                    expected_polarity,
                )
            except WorkflowValidationError as exc:
                last_error = exc
                continue
            return case.model_copy(update={evidence_field: evidence}), evidence
        assert last_error is not None
        raise last_error


class JudgeRunner:
    """Run the judge agent and normalize the structured verdict contract."""

    def __init__(self, llm: LLMProvider, validator: WorkflowValidationGate):
        self.llm = llm
        self.validator = validator

    def run(
        self,
        request: ReviewRequest,
        metrics: FinancialMetrics,
        brief: AnalysisBrief,
        bull_case: BaseModel,
        bear_case: BaseModel,
    ) -> JudgeDecision:
        decision = JudgeAgent(self.llm).run(
            {
                "run_spec": {"ticker": request.ticker, "fiscal_period": request.fiscal_period},
                "financial_snapshot_summary": metrics.model_dump(mode="json", exclude_none=True),
                "analysis_brief": brief,
                "bull_case": bull_case,
                "bear_case": bear_case,
            }
        )
        if not isinstance(decision, JudgeDecision):
            decision = JudgeDecision.model_validate(decision.model_dump())
        self.validator.validate_no_investment_advice_text(decision, "judge_decision")
        return decision

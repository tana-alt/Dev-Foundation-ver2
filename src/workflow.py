"""API-first earnings review workflow.

The API calls this module; the CLI should only be a thin client around the API.
The workflow itself is fixed and explicit:

Data ingestion/normalization -> financial agents -> presentation agents ->
evidence aggregation -> debate agents -> judge -> Markdown renderer.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from .llm import LLMProvider
from .workflow_agents import (
    BalanceSheetRiskAnalyst,
    BearAgent,
    BullAgent,
    CashFlowFcfAnalyst,
    EPSQualityAnalyst,
    GuidanceAnalyst,
    JudgeAgent,
    ManagementIntentAnalyst,
    ProfitabilityAnalyst,
)
from .workflow_models import (
    AgentResult,
    AgentRole,
    AgentTeam,
    AnalysisBrief,
    DebateResult,
    DocumentSection,
    EvidenceItem,
    EvidencePolarity,
    FinancialMetrics,
    ImpactArea,
    JudgeDecision,
    ReviewRequest,
    ReviewResponse,
    SourceRef,
    SourceType,
    StepState,
    StepStatus,
    VerdictLabel,
    WorkflowStep,
)


class WorkflowValidationError(ValueError):
    """Raised when a deterministic workflow gate fails."""


def _fetch_consensus(ticker: str, quarter: str):
    from .preprocessor import fetch_consensus

    return fetch_consensus(ticker, quarter)


def _fetch_filing_html(url: str) -> str:
    from .preprocessor import fetch_filing_html

    return fetch_filing_html(url)


def _segment_filing(html: str):
    from .preprocessor import segment_filing

    return segment_filing(html)


class MarkdownRenderer:
    """Deterministic Markdown rendering from validated structured results."""

    def render(
        self,
        *,
        request: ReviewRequest,
        brief: AnalysisBrief,
        debate: DebateResult,
        decision: JudgeDecision,
    ) -> str:
        lines = [
            f"# Earnings Review: {request.ticker} {request.fiscal_period}",
            "",
            "## Verdict",
            "",
            decision.verdict.value.title(),
            "",
            f"Confidence: {decision.confidence:.2f}",
            "",
            "## Summary",
            "",
            decision.summary,
            "",
            "## Positive Evidence",
            "",
        ]
        lines.extend(f"- {item.summary}" for item in decision.positive_evidence)
        lines.extend(["", "## Negative Evidence", ""])
        lines.extend(f"- {item.summary}" for item in decision.negative_evidence)
        lines.extend(
            [
                "",
                "## EPS Outlook",
                "",
                decision.eps_outlook,
                "",
                "## FCF Outlook",
                "",
                decision.fcf_outlook,
                "",
                "## Bull Case",
                "",
                debate.bull_case,
                "",
                "## Bear Case",
                "",
                debate.bear_case,
                "",
                "## Analyst Brief",
                "",
                brief.synthesis,
                "",
                "_This report is an earnings analysis artifact and is not investment advice._",
            ]
        )
        return "\n".join(lines).strip() + "\n"


class ReviewWorkflow:
    """Synchronous API workflow runner."""

    financial_agent_classes = (
        EPSQualityAnalyst,
        ProfitabilityAnalyst,
        CashFlowFcfAnalyst,
        BalanceSheetRiskAnalyst,
    )
    presentation_agent_classes = (ManagementIntentAnalyst, GuidanceAnalyst)

    def __init__(self, llm: LLMProvider, renderer: MarkdownRenderer | None = None):
        self.llm = llm
        self.renderer = renderer or MarkdownRenderer()

    def run(self, request: ReviewRequest) -> ReviewResponse:
        steps: list[StepStatus] = []

        metrics, sections = self._record_step(
            steps,
            WorkflowStep.DATA_INGESTION,
            lambda: self._ingest(request),
        )
        context = self._build_agent_context(request, metrics, sections)

        financial_findings = self._record_step(
            steps,
            WorkflowStep.FINANCIAL_AGENTS,
            lambda: self._run_parallel(self.financial_agent_classes, context),
        )
        presentation_findings = self._record_step(
            steps,
            WorkflowStep.PRESENTATION_AGENTS,
            lambda: self._run_parallel(self.presentation_agent_classes, context),
        )

        brief = self._record_step(
            steps,
            WorkflowStep.EVIDENCE_AGGREGATION,
            lambda: self._aggregate_evidence(
                request,
                metrics,
                sections,
                financial_findings,
                presentation_findings,
            ),
        )

        bull_case, bear_case, debate = self._record_step(
            steps,
            WorkflowStep.DEBATE,
            lambda: self._run_debate(request, metrics, brief),
        )

        decision = self._record_step(
            steps,
            WorkflowStep.JUDGE,
            lambda: self._run_judge(request, metrics, brief, bull_case, bear_case),
        )
        self._validate_judge_decision(decision, brief, debate)

        markdown = self._record_step(
            steps,
            WorkflowStep.MARKDOWN_RENDERER,
            lambda: self.renderer.render(
                request=request,
                brief=brief,
                debate=debate,
                decision=decision,
            )
            if request.include_markdown
            else "Markdown rendering was disabled for this request.",
        )

        return ReviewResponse(
            request_id=request.request_id,
            ticker=request.ticker,
            fiscal_period=request.fiscal_period,
            steps=steps,
            analysis_brief=brief,
            debate_result=debate,
            judge_decision=decision,
            markdown_report=markdown,
        )

    def _record_step(self, steps: list[StepStatus], step: WorkflowStep, fn):
        started_at = datetime.now(timezone.utc)
        try:
            result = fn()
        except Exception as exc:
            steps.append(
                StepStatus(
                    step=step,
                    state=StepState.FAILED,
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    error=str(exc),
                )
            )
            raise
        steps.append(
            StepStatus(
                step=step,
                state=StepState.COMPLETED,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        )
        return result

    def _ingest(self, request: ReviewRequest) -> tuple[FinancialMetrics, list[DocumentSection]]:
        metrics = self._normalize_metrics(
            request.financial_metrics or self._fetch_financial_metrics(request)
        )
        sections = list(request.document_sections)

        if not sections and request.filing_url is not None:
            html = _fetch_filing_html(str(request.filing_url))
            sections = _segment_filing(html)

        if not sections:
            raise WorkflowValidationError("document_sections or filing_url is required")

        return metrics, sections

    def _normalize_metrics(self, metrics: FinancialMetrics) -> FinancialMetrics:
        payload = metrics.model_dump(exclude_none=True)
        if "eps_surprise_pct" not in payload:
            surprise = self._calculate_surprise_pct(metrics.eps, metrics.eps_consensus)
            if surprise is not None:
                payload["eps_surprise_pct"] = surprise
        if "revenue_surprise_pct" not in payload:
            surprise = self._calculate_surprise_pct(metrics.revenue, metrics.revenue_consensus)
            if surprise is not None:
                payload["revenue_surprise_pct"] = surprise
        if "free_cash_flow" not in payload:
            if metrics.operating_cash_flow is not None and metrics.capex is not None:
                payload["free_cash_flow"] = metrics.operating_cash_flow - abs(metrics.capex)
        return FinancialMetrics.model_validate(payload)

    def _calculate_surprise_pct(
        self,
        actual: float | None,
        consensus: float | None,
    ) -> float | None:
        if actual is None or consensus in (None, 0):
            return None
        return ((actual - consensus) / abs(consensus)) * 100

    def _fetch_financial_metrics(self, request: ReviewRequest) -> FinancialMetrics:
        return _fetch_consensus(request.ticker, request.fiscal_period)

    def _build_agent_context(
        self,
        request: ReviewRequest,
        metrics: FinancialMetrics,
        sections: list[DocumentSection],
    ) -> dict[str, Any]:
        run_spec = {
            "ticker": request.ticker,
            "fiscal_period": request.fiscal_period,
            "purpose": request.purpose,
            "is_investment_advice": request.is_investment_advice,
        }
        source_index = [section.source_ref for section in sections] + metrics.source_refs
        by_topic = self._sections_by_topic(sections)
        metrics_json = metrics.model_dump(mode="json", exclude_none=True)
        minimal_snapshot = {
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
        }

        return {
            "run_spec": run_spec,
            "source_index": source_index,
            "analysis_config": {
                "max_retry": 1,
                "verdict_labels": [label.value for label in VerdictLabel],
                "not_investment_advice": True,
            },
            "financial_snapshot_summary": minimal_snapshot,
            "financial_snapshot_minimal": minimal_snapshot,
            "eps_metrics": metrics_json,
            "profitability_metrics": metrics_json,
            "revenue_metrics": metrics_json,
            "margin_metrics": metrics_json,
            "cash_flow_metrics": metrics_json,
            "fcf_metrics": metrics_json,
            "capex_metrics": metrics_json,
            "working_capital_metrics": metrics_json,
            "balance_sheet_metrics": metrics_json,
            "debt_liquidity_metrics": metrics_json,
            "consensus_deltas": metrics_json,
            "eps_sections": by_topic["eps"],
            "profitability_sections": by_topic["revenue"] + by_topic["segments"],
            "segment_sections": by_topic["segments"],
            "cash_flow_sections": by_topic["other"] + by_topic["risk"],
            "capex_sections": by_topic["guidance"] + by_topic["risk"],
            "balance_sheet_sections": by_topic["risk"] + by_topic["other"],
            "risk_sections": by_topic["risk"],
            "management_sections": by_topic["guidance"] + by_topic["segments"],
            "mdna_sections": by_topic["other"],
            "guidance_sections": by_topic["guidance"],
            "guidance_assumptions_sections": by_topic["guidance"] + by_topic["risk"],
        }

    def _sections_by_topic(
        self,
        sections: list[DocumentSection],
    ) -> dict[str, list[dict[str, Any]]]:
        grouped = {name: [] for name in ("eps", "revenue", "guidance", "segments", "risk", "other")}
        for section in sections:
            topic = self._infer_topic(section)
            grouped[topic].append(section.model_dump(mode="json"))
        return grouped

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

    def _run_parallel(self, agent_classes: tuple[type, ...], context: dict[str, Any]) -> list[BaseModel]:
        with ThreadPoolExecutor(max_workers=len(agent_classes)) as executor:
            futures = [executor.submit(agent_class(self.llm).run, context) for agent_class in agent_classes]
            return [future.result() for future in futures]

    def _aggregate_evidence(
        self,
        request: ReviewRequest,
        metrics: FinancialMetrics,
        sections: list[DocumentSection],
        financial_findings: list[BaseModel],
        presentation_findings: list[BaseModel],
    ) -> AnalysisBrief:
        allowed_source_ids = self._allowed_source_ids(metrics, sections)
        financial_results = [
            self._finding_to_agent_result(finding, AgentTeam.FINANCIAL)
            for finding in financial_findings
        ]
        presentation_results = [
            self._finding_to_agent_result(finding, AgentTeam.PRESENTATION)
            for finding in presentation_findings
        ]

        positive = self._dedupe_evidence(
            [
                *self._collect_evidence(financial_findings, "key_evidence", EvidencePolarity.POSITIVE),
                *self._collect_evidence(presentation_findings, "key_evidence", EvidencePolarity.POSITIVE),
            ]
        )
        negative = self._dedupe_evidence(
            [
                *self._collect_evidence(financial_findings, "counter_evidence", EvidencePolarity.NEGATIVE),
                *self._collect_evidence(presentation_findings, "counter_evidence", EvidencePolarity.NEGATIVE),
            ]
        )
        risks = [item for item in negative if EvidencePolarity.NEGATIVE == item.polarity]

        if not positive:
            raise WorkflowValidationError("positive evidence pool is empty after aggregation")
        if not negative:
            raise WorkflowValidationError("negative evidence pool is empty after aggregation")
        self._validate_evidence_sources([*positive, *negative], allowed_source_ids)

        synthesis = " ".join(
            self._text_attr(finding, "handoff_summary")
            or self._text_attr(finding, "summary")
            or self._text_attr(finding, "conclusion")
            for finding in [*financial_findings, *presentation_findings]
        ).strip()
        if not synthesis:
            synthesis = "Validated specialist findings were aggregated for debate."

        return AnalysisBrief(
            ticker=request.ticker,
            fiscal_period=request.fiscal_period,
            financial_agent_results=financial_results,
            presentation_agent_results=presentation_results,
            positive_evidence_pool=positive[:30],
            negative_evidence_pool=negative[:30],
            risk_evidence_pool=risks[:30],
            synthesis=synthesis[:2000],
        )

    def _run_debate(
        self,
        request: ReviewRequest,
        metrics: FinancialMetrics,
        brief: AnalysisBrief,
    ) -> tuple[BaseModel, BaseModel, DebateResult]:
        context = {
            "run_spec": {"ticker": request.ticker, "fiscal_period": request.fiscal_period},
            "financial_snapshot_summary": metrics.model_dump(mode="json", exclude_none=True),
            "analysis_brief": brief,
            "positive_evidence_pool": brief.positive_evidence_pool,
            "negative_evidence_pool": brief.negative_evidence_pool,
            "disputed_points": brief.risk_evidence_pool,
            "missing_data": [],
        }
        bull_case = BullAgent(self.llm).run(context)
        bear_context = {
            **context,
            "bull_case_summary": self._text_attr(bull_case, "thesis")
            or self._text_attr(bull_case, "summary"),
        }
        bear_case = BearAgent(self.llm).run(bear_context)

        allowed_positive_ids = {item.evidence_id for item in brief.positive_evidence_pool}
        allowed_negative_ids = {item.evidence_id for item in brief.negative_evidence_pool}
        positive = self._dedupe_evidence(
            [
                item
                for item in self._collect_evidence(
                    [bull_case],
                    "strongest_positive_evidence",
                    EvidencePolarity.POSITIVE,
                )
                if item.evidence_id in allowed_positive_ids
            ]
            or brief.positive_evidence_pool
        )
        negative = self._dedupe_evidence(
            [
                item
                for item in self._collect_evidence(
                    [bear_case],
                    "strongest_negative_evidence",
                    EvidencePolarity.NEGATIVE,
                )
                if item.evidence_id in allowed_negative_ids
            ]
            or brief.negative_evidence_pool
        )

        debate = DebateResult(
            bull_case=(self._text_attr(bull_case, "thesis") or "Bull case was generated.")[:2000],
            bear_case=(self._text_attr(bear_case, "thesis") or "Bear case was generated.")[:2000],
            risk_case="; ".join(item.summary for item in negative[:3]) or "No unresolved risks were identified.",
            evaluation="Bull and Bear cases were generated from validated AnalysisBrief only.",
            strongest_positive_evidence=positive[:10],
            strongest_negative_evidence=negative[:10],
            unresolved_questions=self._list_attr(bear_case, "unresolved_risks")[:8],
        )
        return bull_case, bear_case, debate

    def _run_judge(
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
            return JudgeDecision.model_validate(decision.model_dump())
        return decision

    def _validate_judge_decision(
        self,
        decision: JudgeDecision,
        brief: AnalysisBrief,
        debate: DebateResult,
    ) -> None:
        if not decision.positive_evidence:
            raise WorkflowValidationError("judge_decision.positive_evidence must not be empty")
        if not decision.negative_evidence:
            raise WorkflowValidationError("judge_decision.negative_evidence must not be empty")
        for item in decision.positive_evidence:
            if item.polarity != EvidencePolarity.POSITIVE:
                raise WorkflowValidationError("judge positive_evidence must have positive polarity")
        for item in decision.negative_evidence:
            if item.polarity not in {EvidencePolarity.NEGATIVE, EvidencePolarity.RISK}:
                raise WorkflowValidationError("judge negative_evidence must have negative or risk polarity")

        allowed_evidence_ids = {
            item.evidence_id
            for item in [*brief.positive_evidence_pool, *brief.negative_evidence_pool]
        }
        for item in [*decision.positive_evidence, *decision.negative_evidence]:
            if item.evidence_id not in allowed_evidence_ids:
                raise WorkflowValidationError(
                    f"judge evidence {item.evidence_id!r} was not present in validated evidence"
                )

    def _finding_to_agent_result(self, finding: BaseModel, team: AgentTeam) -> AgentResult:
        role_name = self._extract_role_name(finding)
        return AgentResult(
            agent_role=self._role_for_name(role_name),
            team=team,
            status=StepStatus(step=WorkflowStep.FINANCIAL_AGENTS if team == AgentTeam.FINANCIAL else WorkflowStep.PRESENTATION_AGENTS, state=StepState.COMPLETED),
            headline=(self._text_attr(finding, "summary") or self._text_attr(finding, "headline") or role_name)[:300],
            conclusion=(self._text_attr(finding, "handoff_summary") or self._text_attr(finding, "summary") or role_name)[:1200],
            key_evidence=self._collect_evidence([finding], "key_evidence", EvidencePolarity.POSITIVE)[:10],
            counter_evidence=self._collect_evidence([finding], "counter_evidence", EvidencePolarity.NEGATIVE)[:10],
            open_questions=self._list_attr(finding, "missing_data")[:8],
            confidence=float(getattr(finding, "confidence", 0.5)),
        )

    def _collect_evidence(
        self,
        findings: list[BaseModel],
        field_name: str,
        default_polarity: EvidencePolarity,
    ) -> list[EvidenceItem]:
        collected: list[EvidenceItem] = []
        for finding in findings:
            raw_items = getattr(finding, field_name, []) or []
            role_name = self._extract_role_name(finding)
            for index, raw in enumerate(raw_items, start=1):
                collected.append(
                    self._coerce_evidence(
                        raw,
                        default_polarity=default_polarity,
                        fallback_id=f"{self._slug(role_name)}:{field_name}:{index}",
                    )
                )
        return collected

    def _coerce_evidence(
        self,
        raw: Any,
        *,
        default_polarity: EvidencePolarity,
        fallback_id: str,
    ) -> EvidenceItem:
        if isinstance(raw, EvidenceItem):
            return raw

        data = raw.model_dump(mode="json") if isinstance(raw, BaseModel) else dict(raw)
        source_raw = data.get("source_ref") or data.get("source") or fallback_id
        if isinstance(source_raw, dict):
            source_ref = SourceRef.model_validate(source_raw)
        else:
            raise WorkflowValidationError(
                f"evidence {fallback_id!r} must include structured source_ref"
            )

        polarity = data.get("polarity") or default_polarity
        if hasattr(polarity, "value"):
            polarity = polarity.value

        return EvidenceItem(
            evidence_id=self._slug(str(data.get("evidence_id") or fallback_id))[:80],
            polarity=polarity,
            summary=str(data.get("summary") or data.get("claim") or "Evidence item")[:300],
            detail=str(data.get("detail") or data.get("summary") or data.get("claim") or "Evidence item")[:1200],
            impact_areas=self._impact_areas(data),
            source_ref=source_ref,
            metric_name=data.get("metric_name") or data.get("metric"),
            value=data.get("value"),
            unit=data.get("unit"),
            confidence=float(data.get("confidence", 0.5)),
        )

    def _impact_areas(self, data: dict[str, Any]) -> list[ImpactArea]:
        raw = data.get("impact_areas") or data.get("impact_area")
        values = raw if isinstance(raw, list) else [raw] if raw else [ImpactArea.OVERALL]
        result: list[ImpactArea] = []
        for value in values:
            try:
                result.append(value if isinstance(value, ImpactArea) else ImpactArea(str(value)))
            except ValueError:
                result.append(ImpactArea.OVERALL)
        return result

    def _dedupe_evidence(self, items: list[EvidenceItem]) -> list[EvidenceItem]:
        seen: set[str] = set()
        result: list[EvidenceItem] = []
        for item in items:
            key = item.evidence_id
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _allowed_source_ids(
        self,
        metrics: FinancialMetrics,
        sections: list[DocumentSection],
    ) -> set[tuple[str, str, str | None, str | None, str | None]]:
        return {
            self._source_signature(source)
            for source in [
                *metrics.source_refs,
                *(section.source_ref for section in sections),
            ]
        }

    def _validate_evidence_sources(
        self,
        items: list[EvidenceItem],
        allowed_source_ids: set[tuple[str, str, str | None, str | None, str | None]],
    ) -> None:
        for item in items:
            if self._source_signature(item.source_ref) not in allowed_source_ids:
                raise WorkflowValidationError(
                    f"evidence {item.evidence_id!r} references unknown source "
                    f"{item.source_ref.source_id!r}"
                )

    def _source_signature(
        self,
        source: SourceRef,
    ) -> tuple[str, str, str | None, str | None, str | None]:
        return (
            source.source_id,
            source.source_type.value,
            source.document_id,
            source.section_id,
            source.metric_name,
        )

    def _extract_role_name(self, model: BaseModel) -> str:
        for field_name in ("agent_name", "agent_role", "role"):
            if hasattr(model, field_name):
                value = getattr(model, field_name)
                return str(getattr(value, "value", value))
        return type(model).__name__

    def _role_for_name(self, role_name: str) -> AgentRole:
        normalized = role_name.lower()
        mapping = {
            "epsqualityanalyst": AgentRole.EPS_ANALYST,
            "eps_analyst": AgentRole.EPS_ANALYST,
            "profitabilityanalyst": AgentRole.PNL_ANALYST,
            "pnl_analyst": AgentRole.PNL_ANALYST,
            "cashflowfcfanalyst": AgentRole.CFS_ANALYST,
            "cfs_analyst": AgentRole.CFS_ANALYST,
            "balancesheetriskanalyst": AgentRole.BS_ANALYST,
            "bs_analyst": AgentRole.BS_ANALYST,
            "managementintentanalyst": AgentRole.MANAGEMENT_EVAL,
            "management_eval": AgentRole.MANAGEMENT_EVAL,
            "guidanceanalyst": AgentRole.GUIDANCE,
            "guidance": AgentRole.GUIDANCE,
        }
        return mapping.get(normalized, AgentRole.EVAL)

    def _text_attr(self, model: BaseModel, field_name: str) -> str:
        value = getattr(model, field_name, "")
        return str(value).strip() if value is not None else ""

    def _list_attr(self, model: BaseModel, field_name: str) -> list[str]:
        value = getattr(model, field_name, []) or []
        return [str(item) for item in value]

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9_.:-]+", ":", value.strip())
        return slug.strip(":") or "evidence"

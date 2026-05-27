"""API-first earnings review workflow.

The API calls this module; the CLI should only be a thin client around the API.
The workflow itself is fixed and explicit:

Data ingestion/normalization -> financial agents -> presentation agents ->
evidence aggregation -> debate agents -> judge -> Markdown renderer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .llm import LLMProvider
from .workflow_agents import (
    CashFlowRiskAnalyst,
    EarningsQualityAnalyst,
    GuidanceAnalyst,
    ManagementIntentAnalyst,
)
from .workflow_models import (
    AnalysisBrief,
    DebateResult,
    DocumentSection,
    EvidenceItem,
    FinancialMetrics,
    JudgeDecision,
    ReviewRequest,
    ReviewResponse,
    SourceRef,
    StepState,
    StepStatus,
    VerdictLabel,
    WorkflowStep,
)
from .workflow_runtime import AgentRuntime, DebateRunner, JudgeRunner
from .workflow_validation import WorkflowValidationError, WorkflowValidationGate


def _fetch_consensus(ticker: str, quarter: str):
    from .preprocessor import fetch_consensus

    return fetch_consensus(ticker, quarter)


def _fetch_filing_html(url: str) -> str:
    from .preprocessor import fetch_filing_html

    return fetch_filing_html(url)


def _segment_filing(html: str, url: str | None = None):
    from .preprocessor import segment_filing

    return segment_filing(html, url=url)


def _document_files_to_sections(document_files):
    from .preprocessor import document_files_to_sections

    return document_files_to_sections(document_files)


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
            "## Agent Analysis",
            "",
            *self._agent_analysis_lines(brief),
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
                f"Reason: {self._eps_outlook_reason(brief, decision)}",
                "",
                "## FCF Outlook",
                "",
                decision.fcf_outlook,
                "",
                f"Reason: {self._fcf_outlook_reason(brief, decision)}",
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
                "## Sources",
                "",
                *self._source_lines(brief),
                "",
                "_This report is an earnings analysis artifact and is not investment advice._",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _agent_analysis_lines(self, brief: AnalysisBrief) -> list[str]:
        findings = [
            brief.earnings_quality_finding,
            brief.cash_flow_risk_finding,
            brief.management_intent_finding,
            brief.guidance_finding,
        ]
        lines: list[str] = []
        for finding in findings:
            lines.append(
                f"- **{finding.agent_name}** ({finding.stance}, "
                f"confidence {finding.confidence:.2f}): {finding.handoff_summary}"
            )
        return lines

    def _eps_outlook_reason(self, brief: AnalysisBrief, decision: JudgeDecision) -> str:
        if decision.eps_outlook_reason:
            return decision.eps_outlook_reason
        parts = [
            brief.earnings_quality_finding.handoff_summary,
            brief.management_intent_finding.handoff_summary,
            brief.guidance_finding.handoff_summary,
        ]
        return self._compact_reason(parts, fallback=decision.rationale)

    def _fcf_outlook_reason(self, brief: AnalysisBrief, decision: JudgeDecision) -> str:
        if decision.fcf_outlook_reason:
            return decision.fcf_outlook_reason
        parts = [
            brief.cash_flow_risk_finding.handoff_summary,
            brief.management_intent_finding.handoff_summary,
            brief.guidance_finding.handoff_summary,
        ]
        return self._compact_reason(parts, fallback=decision.rationale)

    def _compact_reason(self, parts: list[str], *, fallback: str) -> str:
        text = " ".join(part.strip() for part in parts if part and part.strip()).strip()
        if not text:
            text = fallback
        return text[:1200]

    def _source_lines(self, brief: AnalysisBrief) -> list[str]:
        findings = [
            brief.earnings_quality_finding,
            brief.cash_flow_risk_finding,
            brief.management_intent_finding,
            brief.guidance_finding,
        ]
        lines: list[str] = []
        for finding in findings:
            lines.append(f"### {finding.agent_name}")
            refs = self._unique_source_refs([*finding.key_evidence, *finding.counter_evidence])
            if not refs:
                lines.append("- No source references emitted.")
                continue
            for ref in refs:
                title = ref.title or ref.source_id
                url = str(ref.url) if ref.url else "no URL in source_ref"
                locator = ref.metric_name or ref.section_id or ref.document_id or "source"
                lines.append(f"- `{ref.source_id}` ({locator}): {title} — {url}")
        return lines

    def _unique_source_refs(self, items: list[EvidenceItem]) -> list[SourceRef]:
        seen: set[
            tuple[str, str, str | None, str | None, str | None, int | None, str | None, str | None]
        ] = set()
        refs: list[SourceRef] = []
        for item in items:
            ref = item.source_ref
            key = (
                ref.source_id,
                ref.source_type.value,
                ref.document_id,
                ref.section_id,
                ref.metric_name,
                ref.page,
                ref.title,
                str(ref.url) if ref.url else None,
            )
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
        return refs


class ReviewWorkflow:
    """Synchronous API workflow runner."""

    financial_agent_classes = (
        EarningsQualityAnalyst,
        CashFlowRiskAnalyst,
    )
    presentation_agent_classes = (ManagementIntentAnalyst, GuidanceAnalyst)

    def __init__(
        self,
        llm: LLMProvider,
        renderer: MarkdownRenderer | None = None,
        validator: WorkflowValidationGate | None = None,
        agent_runtime: AgentRuntime | None = None,
        debate_runner: DebateRunner | None = None,
        judge_runner: JudgeRunner | None = None,
    ):
        self.llm = llm
        self.renderer = renderer or MarkdownRenderer()
        self.validator = validator or WorkflowValidationGate()
        self.agent_runtime = agent_runtime or AgentRuntime(llm)
        self.debate_runner = debate_runner or DebateRunner(llm, self.validator)
        self.judge_runner = judge_runner or JudgeRunner(llm, self.validator)

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
            lambda: self.agent_runtime.run_parallel(self.financial_agent_classes, context),
        )
        self.validator.validate_no_investment_advice_text(financial_findings, "financial_findings")
        presentation_findings = self._record_step(
            steps,
            WorkflowStep.PRESENTATION_AGENTS,
            lambda: self.agent_runtime.run_parallel(self.presentation_agent_classes, context),
        )
        self.validator.validate_no_investment_advice_text(
            presentation_findings, "presentation_findings"
        )

        brief = self._record_step(
            steps,
            WorkflowStep.EVIDENCE_AGGREGATION,
            lambda: self.validator.aggregate_evidence(
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
            lambda: self.debate_runner.run(request, metrics, brief),
        )

        decision = self._record_step(
            steps,
            WorkflowStep.JUDGE,
            lambda: self.judge_runner.run(request, metrics, brief, bull_case, bear_case),
        )
        decision = self.validator.validate_judge_decision(decision, brief)

        markdown = self._record_step(
            steps,
            WorkflowStep.MARKDOWN_RENDERER,
            lambda: (
                self.renderer.render(
                    request=request,
                    brief=brief,
                    debate=debate,
                    decision=decision,
                )
                if request.include_markdown
                else "Markdown rendering was disabled for this request."
            ),
        )
        self.validator.validate_no_investment_advice_text(markdown, "markdown_report")

        return ReviewResponse(
            request_id=request.request_id,
            ticker=request.ticker,
            fiscal_period=request.fiscal_period,
            steps=steps,
            analysis_brief=brief,
            bull_case=bull_case,
            bear_case=bear_case,
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
                    error=self._step_error_message(exc),
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

    def _step_error_message(self, exc: Exception) -> str:
        message = str(exc)
        if len(message) <= 1000:
            return message
        return message[:997] + "..."

    def _ingest(self, request: ReviewRequest) -> tuple[FinancialMetrics, list[DocumentSection]]:
        metrics = self._normalize_metrics(
            request.financial_metrics or self._fetch_financial_metrics(request)
        )
        sections = list(request.document_sections)
        if request.document_files:
            sections.extend(_document_files_to_sections(request.document_files))

        if not sections and request.filing_url is not None:
            filing_url = str(request.filing_url)
            html = _fetch_filing_html(filing_url)
            sections = _segment_filing(html, url=filing_url)

        if not sections:
            raise WorkflowValidationError(
                "document_sections, document_files, or filing_url is required"
            )

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
        if actual is None or consensus is None or consensus == 0:
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
            "earnings_quality_metrics": metrics_json,
            "cash_flow_risk_metrics": metrics_json,
            "cash_conversion_inputs": metrics_json,
            "guidance_metrics": metrics_json,
            "guidance_consensus_deltas": metrics_json,
            "consensus_deltas": metrics_json,
            "earnings_quality_sections": (
                by_topic["eps"] + by_topic["revenue"] + by_topic["segments"] + by_topic["other"]
            ),
            "cash_flow_risk_sections": by_topic["other"] + by_topic["risk"] + by_topic["guidance"],
            "risk_sections": by_topic["risk"],
            "management_sections": by_topic["guidance"] + by_topic["segments"],
            "management_intent_sections": by_topic["guidance"]
            + by_topic["segments"]
            + by_topic["other"],
            "strategy_sections": by_topic["segments"] + by_topic["other"],
            "mdna_sections": by_topic["other"],
            "guidance_sections": by_topic["guidance"],
            "guidance_assumptions_sections": by_topic["guidance"] + by_topic["risk"],
            "prior_guidance_track_record": [],
            "management_intent_handoff": None,
        }

    def _sections_by_topic(
        self,
        sections: list[DocumentSection],
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {
            name: [] for name in ("eps", "revenue", "guidance", "segments", "risk", "other")
        }
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

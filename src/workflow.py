"""API-first earnings review workflow.

The API calls this module; the CLI should only be a thin client around the API.
The workflow itself is fixed and explicit:

Data ingestion/normalization -> financial agents -> presentation agents ->
evidence aggregation -> debate agents -> judge -> Markdown renderer.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Literal

from .llm import LLMProvider
from .report_quality_evidence_matrix import evidence_matrix_lines
from .report_quality_guidance import (
    GuidanceAcquisitionError,
    GuidanceFact,
    GuidanceStatus,
    classify_guidance_sources,
)
from .report_quality_missing_data import apply_confidence_caps, missing_data_lines
from .report_quality_numeric_grounding import (
    apply_numeric_grounding_caveats_to_decision,
    validate_numeric_grounding,
)
from .report_quality_source_inventory import source_inventory_lines
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
    GuidanceFinding,
    JudgeDecision,
    MetricStoreEntry,
    MetricStorePeriodRole,
    PresentationMetricHint,
    ReviewRequest,
    ReviewResponse,
    SourceRef,
    SourceType,
    StepState,
    StepStatus,
    VerdictLabel,
    WorkflowStep,
)
from .workflow_runtime import AgentRuntime, DebateRunner, JudgeRunner
from .workflow_validation import WorkflowValidationError, WorkflowValidationGate

PresentationMetricHintStatus = Literal["parsed", "ambiguous", "rejected", "promoted"]


def _fetch_consensus(ticker: str, quarter: str, **kwargs):
    from .preprocessor import fetch_consensus

    return fetch_consensus(ticker, quarter, **kwargs)


def _fetch_consensus_for_request(request: ReviewRequest):
    return _fetch_consensus(
        request.ticker,
        request.fiscal_period,
        target_earnings_date=request.target_earnings_date,
        target_period_end_date=request.target_period_end_date,
        prior_fiscal_period=request.prior_fiscal_period,
        financial_data_as_of=request.financial_data_as_of,
    )


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
        metrics: FinancialMetrics | None = None,
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
            "## Evidence Matrix",
            "",
            *evidence_matrix_lines([*decision.positive_evidence, *decision.negative_evidence]),
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
                "## Source Inventory",
                "",
                *source_inventory_lines(brief, decision),
                "",
                "## Metric Store",
                "",
                *self._metric_store_lines(metrics),
                "",
                "## Presentation Metric Hints",
                "",
                *self._presentation_metric_hint_lines(metrics),
                "",
                "## Missing Data Caveats",
                "",
                *missing_data_lines(brief, decision, metrics=metrics),
                "",
                "## Sources",
                "",
                *self._source_lines(brief),
                "",
                "_This report is an earnings analysis artifact and is not investment advice._",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _metric_store_lines(self, metrics: FinancialMetrics | None) -> list[str]:
        if metrics is None or not metrics.metric_store:
            return ["- No canonical metric_store entries are available."]
        lines = [
            "| metric | value | unit | fiscal_period | period_role | source | source_ref |",
            "|---|---:|---|---|---|---|---|",
        ]
        for entry in metrics.metric_store:
            lines.append(
                "| {metric} | {value} | {unit} | {period} | {role} | {source} | `{source_ref}` |".format(
                    metric=self._escape_table(entry.metric_name),
                    value=self._escape_table(self._format_metric_value(entry.value)),
                    unit=self._escape_table(entry.unit),
                    period=self._escape_table(entry.fiscal_period),
                    role=self._escape_table(entry.period_role),
                    source=self._escape_table(f"{entry.source_name} ({entry.source_type.value})"),
                    source_ref=self._escape_table(entry.source_ref.source_id),
                )
            )
        return lines

    def _presentation_metric_hint_lines(self, metrics: FinancialMetrics | None) -> list[str]:
        if metrics is None:
            return ["- No presentation metric hints are available."]
        visible_hints = [
            hint for hint in metrics.presentation_metric_hints if hint.hint_status != "rejected"
        ]
        if not visible_hints:
            return ["- No presentation metric hints are available."]
        lines = [
            "- Non-canonical PDF/table extraction candidates; `ambiguous` rows are not promoted or used as facts.",
            "",
            "| metric | raw_text | raw_value | value | unit | fiscal_period | period_role | status | source | source_ref |",
            "|---|---|---:|---:|---|---|---|---|---|---|",
        ]
        for hint in visible_hints:
            lines.append(
                "| {metric} | {raw_text} | {raw_value} | {value} | {unit} | {period} | {role} | {status} | {source} | `{source_ref}` |".format(
                    metric=self._escape_table(hint.metric_name),
                    raw_text=self._escape_table(hint.raw_text),
                    raw_value=self._escape_table(hint.raw_value or ""),
                    value=self._escape_table(
                        "" if hint.value is None else self._format_metric_value(hint.value)
                    ),
                    unit=self._escape_table(hint.unit or ""),
                    period=self._escape_table(hint.fiscal_period or ""),
                    role=self._escape_table(hint.period_role or ""),
                    status=self._escape_table(hint.hint_status),
                    source=self._escape_table(f"{hint.source_name} ({hint.source_type.value})"),
                    source_ref=self._escape_table(hint.source_ref.source_id),
                )
            )
        return lines

    def _escape_table(self, value: object) -> str:
        return str(value).replace("\n", " ").replace("|", "\\|")

    def _format_metric_value(self, value: object) -> str:
        if isinstance(value, float):
            return f"{value:g}"
        return str(value)

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
                location = self._source_location(ref)
                locator = ref.metric_name or ref.section_id or ref.document_id or "source"
                lines.append(f"- `{ref.source_id}` ({locator}): {title} — {location}")
        return lines

    def _source_location(self, ref: SourceRef) -> str:
        if ref.url:
            return str(ref.url)
        if ref.source_type is SourceType.FILING:
            return "SEC filing URL not supplied"
        if ref.source_type in {SourceType.FINANCIAL_API, SourceType.DERIVED_METRIC}:
            return ref.title or ref.source_id
        if ref.section_id:
            return ref.section_id
        if ref.document_id:
            return ref.document_id
        if ref.page is not None:
            return f"page {ref.page}"
        return ref.source_id

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
        self.validator.reset_warnings()

        metrics, sections, guidance_fact = self._record_step(
            steps,
            WorkflowStep.DATA_INGESTION,
            lambda: self._ingest(request),
        )
        context = self._build_agent_context(request, metrics, sections, guidance_fact)
        self._enforce_context_budget(context, guidance_fact)

        financial_findings = self._record_step(
            steps,
            WorkflowStep.FINANCIAL_AGENTS,
            lambda: self.agent_runtime.run_parallel(self.financial_agent_classes, context),
        )
        self.validator.validate_no_investment_advice_text(financial_findings, "financial_findings")
        presentation_findings = self._record_step(
            steps,
            WorkflowStep.PRESENTATION_AGENTS,
            lambda: self._run_presentation_agents(context, guidance_fact),
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
        decision = apply_confidence_caps(decision, brief, metrics)
        decision, numeric_grounding_warnings = apply_numeric_grounding_caveats_to_decision(decision)
        self.validator.warnings.extend(numeric_grounding_warnings)
        validate_numeric_grounding([*decision.positive_evidence, *decision.negative_evidence])

        markdown = self._record_step(
            steps,
            WorkflowStep.MARKDOWN_RENDERER,
            lambda: (
                self.renderer.render(
                    request=request,
                    brief=brief,
                    debate=debate,
                    decision=decision,
                    metrics=metrics,
                )
                if request.include_markdown
                else "Markdown rendering was disabled for this request."
            ),
        )
        self.validator.validate_no_investment_advice_text(markdown, "markdown_report")
        warnings = self.validator.warnings.copy()
        markdown = self._append_warnings(markdown, warnings)

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
            warnings=warnings,
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

    def _append_warnings(self, markdown: str, warnings: list[str]) -> str:
        if not warnings:
            return markdown
        lines = [
            markdown.rstrip(),
            "",
            "## Warnings",
            "",
            *[f"- {warning}" for warning in warnings],
            "",
            (
                "Potential investment-advice wording was detected and should be treated "
                "as invalid for investment decisions. This report remains an earnings "
                "analysis artifact and is not investment advice."
            ),
            "",
        ]
        return "\n".join(lines)

    def inspect_input(
        self,
        request: ReviewRequest,
        *,
        strict_guidance: bool = False,
    ) -> dict[str, Any]:
        metrics, sections, guidance_fact = self._ingest(
            request,
            strict_guidance=strict_guidance,
        )
        context = self._build_agent_context(request, metrics, sections, guidance_fact)
        context_budget = self._context_budget_report(context, guidance_fact)
        return {
            "normalized_input_summary": {
                "request_id": request.request_id,
                "ticker": request.ticker,
                "fiscal_period": request.fiscal_period,
                "target_earnings_date": (
                    request.target_earnings_date.isoformat()
                    if request.target_earnings_date
                    else None
                ),
                "target_period_end_date": (
                    request.target_period_end_date.isoformat()
                    if request.target_period_end_date
                    else None
                ),
                "prior_fiscal_period": request.prior_fiscal_period,
                "document_file_count": len(request.document_files),
                "document_section_count": len(sections),
                "guidance_status": guidance_fact.status.value,
                "strict_guidance": strict_guidance,
            },
            "normalized_metrics": metrics.model_dump(mode="json", exclude_none=True),
            "source_manifest": self._source_manifest(request, metrics, sections),
            "temporal_input_summary": self._temporal_input_summary(request, metrics),
            "metric_snapshots": metrics.temporal_snapshots,
            "temporal_source_manifest": self._temporal_source_manifest(metrics, sections),
            "temporal_validation": self._temporal_validation(metrics),
            "document_sections_preview": self._document_sections_preview(sections),
            "guidance_audit": guidance_fact.model_dump(mode="json", exclude_none=True),
            "routing_report": context["routing_report"],
            "context_budget": context_budget,
        }

    def _ingest(
        self,
        request: ReviewRequest,
        *,
        strict_guidance: bool | None = None,
    ) -> tuple[FinancialMetrics, list[DocumentSection], GuidanceFact]:
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

        guidance_fact = classify_guidance_sources(metrics, sections)
        metrics = self._attach_presentation_metric_hints(request, metrics, sections, guidance_fact)
        require_strict_guidance = (
            strict_guidance if strict_guidance is not None else self._strict_guidance_enabled()
        )
        if require_strict_guidance:
            self._validate_strict_guidance(guidance_fact, metrics)

        return metrics, sections, guidance_fact

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
        normalized = FinancialMetrics.model_validate(payload)
        if not normalized.metric_store:
            normalized = self._attach_flat_metric_store(normalized)
        return normalized

    def _attach_flat_metric_store(self, metrics: FinancialMetrics) -> FinancialMetrics:
        entries: list[MetricStoreEntry] = []
        source_name = self._metric_store_source_name(metrics)
        as_of_date = metrics.earnings_date or metrics.data_cutoff_date
        specs: list[tuple[str, float | None, MetricStorePeriodRole]] = [
            ("eps", metrics.eps, "reported_period_actuals"),
            ("eps_consensus", metrics.eps_consensus, "consensus_for_reported_period"),
            ("revenue", metrics.revenue, "reported_period_actuals"),
            ("revenue_consensus", metrics.revenue_consensus, "consensus_for_reported_period"),
            ("operating_margin_pct", metrics.operating_margin_pct, "reported_period_actuals"),
            ("operating_cash_flow", metrics.operating_cash_flow, "reported_period_actuals"),
            ("free_cash_flow", metrics.free_cash_flow, "reported_period_actuals"),
            ("capex", metrics.capex, "reported_period_actuals"),
        ]
        for metric_name, value, period_role in specs:
            if value is None:
                continue
            entries.append(
                MetricStoreEntry(
                    metric_name=metric_name,
                    value=value,
                    unit=self._metric_unit(metric_name, metrics.currency),
                    source_type=SourceType.FINANCIAL_API,
                    source_name=source_name,
                    fiscal_period=metrics.fiscal_period,
                    period_role=period_role,
                    source_ref=SourceRef(
                        source_id=(
                            f"financial_api:{metrics.ticker}:{metrics.fiscal_period}:{metric_name}"
                        ),
                        source_type=SourceType.FINANCIAL_API,
                        metric_name=metric_name,
                        title=source_name,
                        fiscal_period=metrics.fiscal_period,
                        period_role=period_role,
                        as_of_date=as_of_date,
                        data_cutoff_date=metrics.data_cutoff_date,
                    ),
                )
            )
        if not entries:
            return metrics
        return self._replace_metrics_store(metrics, [*metrics.metric_store, *entries])

    def _metric_store_source_name(self, metrics: FinancialMetrics) -> str:
        if metrics.source_provider == "yfinance":
            return "Yahoo Finance via yfinance"
        if metrics.source_provider == "sec":
            return "SEC filing-derived metrics"
        if metrics.source_provider == "manual":
            return "Manual financial metrics input"
        return "Financial metrics input"

    def _metric_unit(self, metric_name: str, currency: str) -> str:
        if metric_name.startswith("eps"):
            return f"{currency}/share"
        if metric_name.endswith("_pct"):
            return "%"
        return currency

    def _attach_presentation_metric_hints(
        self,
        request: ReviewRequest,
        metrics: FinancialMetrics,
        sections: list[DocumentSection],
        guidance_fact: GuidanceFact,
    ) -> FinancialMetrics:
        hints = self._guidance_metric_hints(request, sections, guidance_fact)
        if not hints:
            return metrics
        return self._replace_presentation_metric_hints(
            metrics,
            [*metrics.presentation_metric_hints, *hints],
        )

    def _replace_metrics_store(
        self,
        metrics: FinancialMetrics,
        entries: list[MetricStoreEntry],
    ) -> FinancialMetrics:
        deduped_entries: list[MetricStoreEntry] = []
        seen_entries: set[tuple[str, str, str, str]] = set()
        for entry in entries:
            key = (
                entry.metric_name,
                entry.fiscal_period,
                entry.period_role,
                entry.source_ref.source_id,
            )
            if key in seen_entries:
                continue
            seen_entries.add(key)
            deduped_entries.append(entry)
        source_refs = self._dedupe_source_refs(
            [*metrics.source_refs, *(entry.source_ref for entry in deduped_entries)]
        )
        payload = metrics.model_dump(mode="python")
        payload["metric_store"] = deduped_entries
        payload["source_refs"] = source_refs
        return FinancialMetrics.model_validate(payload)

    def _replace_presentation_metric_hints(
        self,
        metrics: FinancialMetrics,
        hints: list[PresentationMetricHint],
    ) -> FinancialMetrics:
        deduped_hints: list[PresentationMetricHint] = []
        seen_hints: set[tuple[str, str, str | None, str | None, str]] = set()
        for hint in hints:
            key = (
                hint.metric_name,
                hint.raw_text,
                hint.fiscal_period,
                hint.period_role,
                hint.source_ref.source_id,
            )
            if key in seen_hints:
                continue
            seen_hints.add(key)
            deduped_hints.append(hint)
        payload = metrics.model_dump(mode="python")
        payload["presentation_metric_hints"] = deduped_hints
        return FinancialMetrics.model_validate(payload)

    def _dedupe_source_refs(self, source_refs) -> list[SourceRef]:
        result: list[SourceRef] = []
        seen: set[tuple[str, str, str | None, str | None]] = set()
        for source_ref in source_refs:
            key = (
                source_ref.source_id,
                source_ref.source_type.value,
                source_ref.metric_name,
                source_ref.period_role,
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(source_ref)
        return result

    def _guidance_metric_hints(
        self,
        request: ReviewRequest,
        sections: list[DocumentSection],
        guidance_fact: GuidanceFact,
    ) -> list[PresentationMetricHint]:
        candidate_ids = set(guidance_fact.candidate_section_ids)
        candidate_source_ids = {source.source_id for source in guidance_fact.source_refs}
        if not candidate_ids and not candidate_source_ids:
            return []
        hints: list[PresentationMetricHint] = []
        currency = request.financial_metrics.currency if request.financial_metrics else "USD"
        for section in sections:
            if (
                section.section_id not in candidate_ids
                and section.source_ref.section_id not in candidate_ids
                and section.source_ref.source_id not in candidate_source_ids
            ):
                continue
            fiscal_period = self._guided_fiscal_period(section.text, section.heading)
            hints.extend(
                self._guidance_hints_from_section(
                    section,
                    fiscal_period=fiscal_period,
                    currency=currency,
                )
            )
        return hints

    def _guided_fiscal_period(self, text: str, heading: str) -> str | None:
        candidates = [text]
        if self._text_has_guidance_signal(heading):
            candidates.append(heading)
        patterns = (
            re.compile(r"\bQ([1-4])\s*FY\s*(20\d{2})\b", re.IGNORECASE),
            re.compile(r"\bFY\s*(20\d{2})\s*Q([1-4])\b", re.IGNORECASE),
            re.compile(r"\b(20\d{2})\s*Q([1-4])\b", re.IGNORECASE),
        )
        for candidate in candidates:
            for pattern in patterns:
                match = pattern.search(candidate)
                if not match:
                    continue
                groups = match.groups()
                if len(groups[0]) == 1:
                    quarter, year = groups[0], groups[1]
                else:
                    year, quarter = groups[0], groups[1]
                return f"{year}Q{quarter}"
        return None

    def _guidance_hints_from_section(
        self,
        section: DocumentSection,
        *,
        fiscal_period: str | None,
        currency: str,
    ) -> list[PresentationMetricHint]:
        if not self._text_has_guidance_signal(f"{section.heading}\n{section.text}"):
            return []
        metric_patterns = [
            ("revenue_guidance", r"revenue"),
            ("eps_guidance", r"(?:diluted\s+)?eps"),
            ("free_cash_flow_guidance", r"free\s+cash\s+flow"),
            ("capex_guidance", r"capex"),
        ]
        number = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
        scale = r"billions?|bn|millions?|m"
        section_header_scale = self._guidance_unit_context(section.heading)
        patterns = [
            (
                "context_parenthetical",
                r"\b{label}\b\s*\(\s*\$?\s*in\s+(?P<scale>{scale})\s*\)\s*"
                r"[:\-]?\s*\$?\s*(?P<value>{number})(?!\s*%)",
                True,
            ),
            (
                "context_inline",
                r"\b{label}\b\s+in\s+(?P<scale>{scale})\s*[:\-]?\s*\$?\s*"
                r"(?P<value>{number})(?!\s*%)",
                True,
            ),
            (
                "explicit_currency_or_scale",
                r"\b{label}\b[^.\n]{{0,160}}?"
                r"(?:\$\s*(?P<value>{number})\s*(?P<scale>{scale})?|"
                r"(?P<scaled_value>{number})\s*(?P<scaled_scale>{scale}))"
                r"(?!\s*%)",
                False,
            ),
            (
                "header_unit_context",
                r"\b(?:outlook\s+)?{label}\b\s*[:\-]?\s*\$?\s*(?P<value>{number})(?!\s*%)",
                False,
            ),
        ]
        source_name = (
            section.source_ref.title
            or section.heading
            or section.source_ref.document_id
            or section.source_ref.source_id
        )
        hints: list[PresentationMetricHint] = []
        seen_metric_names: set[str] = set()
        for metric_name, label in metric_patterns:
            metric_header_scale = section_header_scale or self._guidance_unit_context(
                self._guidance_text_before_label(section.text, label)
            )
            for extraction_method, pattern_template, context_scale_pattern in patterns:
                pattern = re.compile(
                    pattern_template.format(label=label, number=number, scale=scale),
                    re.IGNORECASE,
                )
                match = pattern.search(section.text)
                if not match:
                    continue
                groups = match.groupdict()
                raw_value = groups.get("value") or groups.get("scaled_value")
                if raw_value is None:
                    continue
                matched_scale = (
                    groups.get("scale")
                    or groups.get("scaled_scale")
                    or (metric_header_scale if extraction_method == "header_unit_context" else None)
                )
                explicit_currency = "$" in match.group(0) or context_scale_pattern
                unit = self._guidance_hint_unit(
                    metric_name,
                    matched_scale,
                    currency,
                    explicit_currency=explicit_currency,
                )
                raw_text = match.group(0).strip()
                status = self._guidance_hint_status(
                    metric_name,
                    raw_text=raw_text,
                    unit=unit,
                    fiscal_period=fiscal_period,
                    section_heading=section.heading,
                    context_window=self._guidance_match_context(
                        section.text,
                        match.start(),
                        match.end(),
                    ),
                )
                hints.append(
                    self._presentation_metric_hint(
                        section=section,
                        metric_name=metric_name,
                        raw_text=raw_text,
                        raw_value=raw_value,
                        value=self._parse_guidance_number(raw_value),
                        unit=unit,
                        fiscal_period=fiscal_period,
                        period_role="guided_period" if fiscal_period else None,
                        source_name=source_name,
                        extraction_method=f"guidance_hint_regex:{extraction_method}",
                        hint_status=status,
                        confidence=self._guidance_hint_confidence(status),
                    )
                )
                seen_metric_names.add(metric_name)
                break

        for metric_name, label in metric_patterns:
            if metric_name in seen_metric_names:
                continue
            percent_pattern = re.compile(
                rf"\b(?:outlook\s+)?{label}\b[^.\n]{{0,120}}?"
                rf"(?P<value>{number})\s*%",
                re.IGNORECASE,
            )
            match = percent_pattern.search(section.text)
            if not match:
                continue
            raw_value = f"{match.group('value')}%"
            hints.append(
                self._presentation_metric_hint(
                    section=section,
                    metric_name=metric_name,
                    raw_text=match.group(0).strip(),
                    raw_value=raw_value,
                    value=self._parse_guidance_number(match.group("value")),
                    unit="%",
                    fiscal_period=fiscal_period,
                    period_role="guided_period" if fiscal_period else None,
                    source_name=source_name,
                    extraction_method="guidance_hint_regex:percent_rejection",
                    hint_status="rejected",
                    confidence=0.1,
                )
            )
        return hints

    def _presentation_metric_hint(
        self,
        *,
        section: DocumentSection,
        metric_name: str,
        raw_text: str,
        raw_value: str,
        value: float,
        unit: str | None,
        fiscal_period: str | None,
        period_role: MetricStorePeriodRole | None,
        source_name: str,
        extraction_method: str,
        hint_status: PresentationMetricHintStatus,
        confidence: float,
    ) -> PresentationMetricHint:
        source_ref_update: dict[str, Any] = {
            "metric_name": metric_name,
            "fiscal_period": fiscal_period,
            "period_role": period_role,
        }
        source_ref = section.source_ref.model_copy(update=source_ref_update)
        return PresentationMetricHint(
            metric_name=metric_name,
            raw_text=raw_text,
            raw_value=raw_value,
            value=value,
            unit=unit,
            fiscal_period=fiscal_period,
            period_role=period_role,
            source_type=section.source_ref.source_type,
            source_name=source_name,
            source_ref=source_ref,
            extraction_method=extraction_method,
            hint_status=hint_status,
            confidence=confidence,
        )

    def _parse_guidance_number(self, value: str) -> float:
        return float(value.replace(",", ""))

    def _guidance_unit_context(self, text: str) -> str | None:
        match = re.search(
            r"(?:\(\s*\$?\s*in\s+|\bin\s+)(billions?|bn|millions?|m)\b",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        return match.group(1)

    def _guidance_text_before_label(self, text: str, label: str) -> str:
        match = re.search(rf"\b(?:outlook\s+)?{label}\b", text, re.IGNORECASE)
        if not match:
            return text[:500]
        return text[max(0, match.start() - 500) : match.start()]

    def _guidance_match_context(self, text: str, start: int, end: int) -> str:
        return text[max(0, start - 160) : min(len(text), end + 160)]

    def _guidance_hint_unit(
        self,
        metric_name: str,
        scale: str | None,
        currency: str,
        *,
        explicit_currency: bool,
    ) -> str | None:
        if metric_name == "eps_guidance":
            return f"{currency}/share" if explicit_currency else None
        if scale:
            normalized = self._normalize_guidance_scale(scale)
            return f"{currency} {normalized}"
        if explicit_currency:
            return currency
        return None

    def _normalize_guidance_scale(self, scale: str) -> str:
        return {
            "bn": "billion",
            "billion": "billion",
            "billions": "billion",
            "m": "million",
            "million": "million",
            "millions": "million",
        }.get(scale.lower(), scale.lower())

    def _guidance_hint_status(
        self,
        metric_name: str,
        *,
        raw_text: str,
        unit: str | None,
        fiscal_period: str | None,
        section_heading: str | None,
        context_window: str,
    ) -> PresentationMetricHintStatus:
        lowered = raw_text.lower()
        lowered_context = context_window.lower()
        combined = f"{lowered}\n{lowered_context}"
        if self._guidance_hint_is_definition(metric_name, combined):
            return "rejected"
        if unit == "%" or re.search(r"\b(grew|growth|increased|decreased|declined)\b", lowered):
            return "rejected"
        if "segment" in lowered:
            return "rejected"
        if re.search(r"\b(was|were|reported|delivered|generated|ended|achieved)\b", lowered):
            return "rejected"
        if self._guidance_hint_has_historical_context(lowered_context):
            return "ambiguous"
        if unit is None and metric_name != "eps_guidance":
            return "ambiguous"
        if not self._guidance_hint_has_forward_scope(
            raw_text=raw_text,
            context_window=context_window,
            section_heading=section_heading,
            fiscal_period=fiscal_period,
        ):
            return "ambiguous"
        return "parsed"

    def _guidance_hint_is_definition(self, metric_name: str, text: str) -> bool:
        if metric_name == "revenue_guidance" and re.search(
            r"\b(arr|annual\s+recurring\s+revenue)\b",
            text,
        ):
            return True
        return bool(
            re.search(
                r"\b(refers?\s+to|defined\s+as|definition|means|represents|calculated\s+as)\b",
                text,
            )
        )

    def _guidance_hint_has_historical_context(self, text: str) -> bool:
        historical_period = re.search(
            r"\b(q[1-4](?:\s*(?:fy)?\s*\d{2,4})?|reported\s+quarter|"
            r"current\s+quarter|prior\s+quarter|last\s+year|year[-\s]over[-\s]year|"
            r"y/y|yoy|ytd|year-to-date)\b",
            text,
        )
        historical_action = re.search(
            r"\b(was|were|reported|delivered|generated|ended|achieved|exceeded|beat|"
            r"came\s+in|grew|growth|increased|decreased|declined)\b",
            text,
        )
        return bool(historical_period and historical_action)

    def _guidance_hint_has_forward_scope(
        self,
        *,
        raw_text: str,
        context_window: str,
        section_heading: str | None,
        fiscal_period: str | None,
    ) -> bool:
        if fiscal_period:
            return True
        heading = section_heading or ""
        if re.search(r"\b(outlook|guidance|forecast)\b", heading, re.IGNORECASE):
            return True
        return bool(
            re.search(
                r"\b(outlook|guidance|forecast|expects?|expected|projected|projects?|"
                r"anticipates?|assumes?|next\s+quarter|next\s+fiscal|full\s+year|"
                r"fiscal\s+20\d{2}|fy\s*20\d{2}|q[1-4]\s*fy\s*20\d{2})\b",
                f"{raw_text}\n{context_window}",
                re.IGNORECASE,
            )
        )

    def _guidance_hint_confidence(self, status: PresentationMetricHintStatus) -> float:
        if status == "parsed":
            return 0.75
        if status == "ambiguous":
            return 0.45
        if status == "promoted":
            return 0.9
        return 0.1

    def _text_has_guidance_signal(self, text: str) -> bool:
        return bool(
            re.search(
                r"\b(outlook|guidance|forecast|expected|expects|approximately|next\s+quarter|full\s+year)\b",
                text,
                re.IGNORECASE,
            )
        )

    def _calculate_surprise_pct(
        self,
        actual: float | None,
        consensus: float | None,
    ) -> float | None:
        if actual is None or consensus is None or consensus == 0:
            return None
        return ((actual - consensus) / abs(consensus)) * 100

    def _fetch_financial_metrics(self, request: ReviewRequest) -> FinancialMetrics:
        return _fetch_consensus_for_request(request)

    def _build_agent_context(
        self,
        request: ReviewRequest,
        metrics: FinancialMetrics,
        sections: list[DocumentSection],
        guidance_fact: GuidanceFact | None = None,
    ) -> dict[str, Any]:
        guidance_fact = guidance_fact or classify_guidance_sources(metrics, sections)
        run_spec = {
            "ticker": request.ticker,
            "fiscal_period": request.fiscal_period,
            "target_earnings_date": (
                request.target_earnings_date.isoformat() if request.target_earnings_date else None
            ),
            "target_period_end_date": (
                request.target_period_end_date.isoformat()
                if request.target_period_end_date
                else None
            ),
            "prior_fiscal_period": request.prior_fiscal_period,
            "purpose": request.purpose,
            "is_investment_advice": request.is_investment_advice,
        }
        source_index = self._dedupe_source_refs(
            [
                *(section.source_ref for section in sections),
                *metrics.source_refs,
                *(entry.source_ref for entry in metrics.metric_store),
                *(
                    hint.source_ref
                    for hint in metrics.presentation_metric_hints
                    if hint.hint_status != "rejected"
                ),
            ]
        )
        by_topic = self._sections_by_topic(sections, guidance_fact)
        section_contexts = self._section_contexts_by_key(by_topic, guidance_fact)
        routing_report = self._routing_report(section_contexts, guidance_fact)
        presentation_metric_hints = self._presentation_metric_hints_context(metrics)
        metrics_json = metrics.model_dump(
            mode="json",
            exclude_none=True,
            exclude={"temporal_snapshots", "presentation_metric_hints"},
        )
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

        temporal_metrics = self._temporal_metrics_context(metrics)
        metrics_for_agents = {
            **metrics_json,
            **temporal_metrics,
        }
        return {
            "run_spec": run_spec,
            "source_index": source_index,
            "guidance_fact": guidance_fact.model_dump(mode="json", exclude_none=True),
            "routing_report": routing_report,
            "analysis_config": {
                "max_retry": 1,
                "verdict_labels": [label.value for label in VerdictLabel],
                "not_investment_advice": True,
            },
            "financial_snapshot_summary": minimal_snapshot,
            "financial_snapshot_minimal": minimal_snapshot,
            "presentation_metric_hints": presentation_metric_hints,
            "earnings_quality_metrics": metrics_for_agents,
            "cash_flow_risk_metrics": metrics_for_agents,
            "cash_conversion_inputs": metrics_for_agents,
            "guidance_metrics": metrics_for_agents,
            "guidance_consensus_deltas": metrics_for_agents,
            "consensus_deltas": metrics_for_agents,
            **section_contexts,
            "prior_guidance_track_record": [],
            "management_intent_handoff": None,
        }

    def _section_contexts_by_key(
        self,
        by_topic: dict[str, list[dict[str, Any]]],
        guidance_fact: GuidanceFact,
    ) -> dict[str, list[dict[str, Any]]]:
        guidance_sections = []
        if guidance_fact.status is not GuidanceStatus.NOT_FOUND:
            guidance_sections = self._tagged_sections(
                (by_topic["guidance"], ("guidance",)),
                (by_topic["risk"], ("guidance_assumption", "risk")),
            )
        return {
            "earnings_quality_sections": self._tagged_sections(
                (by_topic["eps"], ("eps",)),
                (by_topic["revenue"], ("revenue",)),
                (by_topic["segments"], ("segments",)),
                (by_topic["other"], ("other",)),
            ),
            "cash_flow_risk_sections": self._tagged_sections(
                (by_topic["other"], ("other",)),
                (by_topic["risk"], ("risk",)),
                (by_topic["guidance"], ("guidance",)),
            ),
            "risk_sections": self._tagged_sections((by_topic["risk"], ("risk",))),
            "management_sections": self._tagged_sections(
                (by_topic["guidance"], ("guidance", "management")),
                (by_topic["segments"], ("segments", "management", "strategy")),
                (by_topic["other"], ("other", "strategy", "mdna")),
                (by_topic["risk"], ("risk", "management_counter_context")),
            ),
            "guidance_sections": guidance_sections,
        }

    def _tagged_sections(
        self,
        *section_groups: tuple[list[dict[str, Any]], tuple[str, ...]],
    ) -> list[dict[str, Any]]:
        sections_by_id: dict[str, dict[str, Any]] = {}
        ordered_ids: list[str] = []
        for sections, tags in section_groups:
            for section in sections:
                section_id = self._section_context_id(section)
                if section_id not in sections_by_id:
                    tagged = dict(section)
                    tagged["routing_tags"] = []
                    tagged["merged_section_ids"] = [tagged.get("section_id")]
                    sections_by_id[section_id] = tagged
                    ordered_ids.append(section_id)
                else:
                    self._merge_same_page_section(sections_by_id[section_id], section)
                routing_tags = sections_by_id[section_id]["routing_tags"]
                for tag in (*tags, *self._section_keyword_tags(section)):
                    if tag not in routing_tags:
                        routing_tags.append(tag)

        result = []
        for section_id in ordered_ids:
            section = sections_by_id[section_id]
            tags = section["routing_tags"]
            section["routing_context"] = f"Routed for: {', '.join(tags)}."
            result.append(section)
        return result

    def _section_context_id(self, section: dict[str, Any]) -> str:
        raw_source_ref = section.get("source_ref")
        source_ref: dict[str, Any] = raw_source_ref if isinstance(raw_source_ref, dict) else {}
        document_id = source_ref.get("document_id")
        page = source_ref.get("page")
        if document_id and page is not None:
            return f"{document_id}:page:{page}"
        return str(
            section.get("section_id")
            or source_ref.get("section_id")
            or source_ref.get("source_id")
            or source_ref.get("document_id")
        )

    def _merge_same_page_section(
        self,
        existing: dict[str, Any],
        section: dict[str, Any],
    ) -> None:
        merged_section_ids = existing.setdefault("merged_section_ids", [existing.get("section_id")])
        section_id = section.get("section_id")
        if section_id and section_id not in merged_section_ids:
            merged_section_ids.append(section_id)
        existing_text = str(existing.get("text") or "")
        new_text = str(section.get("text") or "")
        if new_text and new_text not in existing_text:
            existing["text"] = (
                f"{existing_text}\n\n[continued same source page]\n\n{new_text}"
                if existing_text
                else new_text
            )

    def _section_keyword_tags(self, section: dict[str, Any]) -> tuple[str, ...]:
        haystack = " ".join(
            str(section.get(key) or "") for key in ("section_id", "heading", "text")
        ).lower()
        tags: list[str] = []
        keyword_specs = (
            ("guidance", ("guidance", "outlook", "forecast")),
            ("risk", ("risk", "uncertainty", "forward-looking", "safe harbor")),
            ("segments", ("segment", "geography", "product line")),
            ("revenue", ("revenue", "sales", "billings")),
            ("eps", ("eps", "earnings per share")),
            ("cash_flow", ("cash flow", "free cash flow", "capex", "capital expenditure")),
            ("strategy", ("strategy", "strategic", "investment", "priority", "roadmap")),
            ("mdna", ("md&a", "management discussion", "operating expense")),
        )
        for tag, keywords in keyword_specs:
            if any(keyword in haystack for keyword in keywords):
                tags.append(tag)
        return tuple(tags)

    def _presentation_metric_hints_context(self, metrics: FinancialMetrics) -> list[dict[str, Any]]:
        return [
            hint.model_dump(mode="json", exclude_none=True)
            for hint in metrics.presentation_metric_hints
            if hint.hint_status != "rejected"
        ]

    def _temporal_metrics_context(self, metrics: FinancialMetrics) -> dict[str, Any]:
        snapshots = metrics.temporal_snapshots or {}
        reported = self._canonical_snapshot(
            snapshots.get("reported_period_actuals"),
            "reported_period_actuals",
        ) or self._bucket_from_metric_store(
            metrics,
            "reported_period_actuals",
            fallback_metrics={
                "eps": metrics.eps,
                "revenue": metrics.revenue,
                "operating_cash_flow": metrics.operating_cash_flow,
                "free_cash_flow": metrics.free_cash_flow,
                "capex": metrics.capex,
            },
        )
        consensus = self._canonical_snapshot(
            snapshots.get("consensus_for_reported_period")
            or snapshots.get("pre_earnings_consensus"),
            "consensus_for_reported_period",
        ) or self._bucket_from_metric_store(
            metrics,
            "consensus_for_reported_period",
            fallback_metrics={
                "eps_consensus": metrics.eps_consensus,
                "revenue_consensus": metrics.revenue_consensus,
            },
        )
        guided = self._canonical_snapshot(
            snapshots.get("guided_period"),
            "guided_period",
        ) or self._bucket_from_metric_store(
            metrics,
            "guided_period",
        )
        guided_consensus = self._canonical_snapshot(
            snapshots.get("consensus_for_guided_period"),
            "consensus_for_guided_period",
        ) or self._bucket_from_metric_store(metrics, "consensus_for_guided_period")
        prior_sequential = self._canonical_snapshot(
            snapshots.get("prior_sequential_period_actuals"),
            "prior_sequential_period_actuals",
        ) or self._bucket_from_metric_store(
            metrics,
            "prior_sequential_period_actuals",
        )
        prior_year = self._canonical_snapshot(
            snapshots.get("prior_year_period"),
            "prior_year_period",
        ) or self._bucket_from_metric_store(
            metrics,
            "prior_year_period",
        )
        canonical_temporal_buckets = {
            "reported_period_actuals": reported,
            "consensus_for_reported_period": consensus,
            "guided_period": guided,
            "consensus_for_guided_period": guided_consensus,
            "prior_sequential_period_actuals": prior_sequential,
            "prior_year_period": prior_year,
        }
        return {
            "canonical_temporal_buckets": canonical_temporal_buckets,
            "reported_period_actuals": reported,
            "consensus_for_reported_period": consensus,
            "guided_period": guided,
            "consensus_for_guided_period": guided_consensus,
            "prior_sequential_period_actuals": prior_sequential,
            "prior_year_period": prior_year,
            "disallowed_latest_snapshot": {
                "present": False,
                "reason": "latest_snapshot is not routed as evidence",
            },
        }

    def _canonical_snapshot(self, snapshot: Any, period_role: str) -> dict[str, Any] | None:
        if not isinstance(snapshot, dict):
            return None
        allowed_keys = {
            "ticker",
            "fiscal_period",
            "period_end_date",
            "earnings_date",
            "as_of_date",
            "source_provider",
            "source_row_date",
            "source_table_column_date",
            "selection_method",
            "metrics",
            "warnings",
        }
        canonical = {key: value for key, value in snapshot.items() if key in allowed_keys}
        canonical["bucket"] = period_role
        canonical["period_role"] = period_role
        return canonical

    def _bucket_from_metric_store(
        self,
        metrics: FinancialMetrics,
        period_role: str,
        *,
        fallback_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        entries = [entry for entry in metrics.metric_store if entry.period_role == period_role]
        metric_values = {
            entry.metric_name: entry.value
            for entry in entries
            if entry.fiscal_period == metrics.fiscal_period
            or period_role
            in {
                "guided_period",
                "consensus_for_guided_period",
                "prior_sequential_period_actuals",
                "prior_year_period",
            }
        }
        if fallback_metrics:
            for key, value in fallback_metrics.items():
                if value is not None and key not in metric_values:
                    metric_values[key] = value
        if not metric_values:
            return None
        fiscal_period = metrics.fiscal_period
        if entries and period_role in {
            "guided_period",
            "consensus_for_guided_period",
            "prior_sequential_period_actuals",
            "prior_year_period",
        }:
            fiscal_period = entries[0].fiscal_period
        return {
            "bucket": period_role,
            "ticker": metrics.ticker,
            "fiscal_period": fiscal_period,
            "period_role": period_role,
            "period_end_date": metrics.period_end_date.isoformat()
            if metrics.period_end_date and period_role == "reported_period_actuals"
            else None,
            "earnings_date": metrics.earnings_date.isoformat()
            if metrics.earnings_date and period_role == "reported_period_actuals"
            else None,
            "source_provider": metrics.source_provider,
            "metrics": metric_values,
            "source_refs": [
                entry.source_ref.model_dump(mode="json", exclude_none=True) for entry in entries
            ],
            "warnings": metrics.warnings,
        }

    def _run_presentation_agents(
        self,
        context: dict[str, Any],
        guidance_fact: GuidanceFact,
    ):
        if guidance_fact.status is GuidanceStatus.NOT_FOUND:
            findings = self.agent_runtime.run_parallel((ManagementIntentAnalyst,), context)
            return [*findings, self._missing_guidance_finding(guidance_fact)]
        return self.agent_runtime.run_parallel(self.presentation_agent_classes, context)

    def _missing_guidance_finding(self, guidance_fact: GuidanceFact) -> GuidanceFinding:
        return GuidanceFinding(
            stance="unclear",
            summary="No source-backed guidance or outlook section was identified.",
            key_evidence=[],
            counter_evidence=[],
            confidence=0.2,
            missing_data=[
                "Guidance or outlook was not found in routed source sections; no GuidanceAnalyst LLM call was made."
            ],
            handoff_summary=(
                "Guidance analysis is unavailable because deterministic input inspection did not "
                "identify source-backed guidance, outlook, or no-guidance disclosure."
            ),
            guidance_status=guidance_fact.status.value,
        )

    def _sections_by_topic(
        self,
        sections: list[DocumentSection],
        guidance_fact: GuidanceFact | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {
            name: [] for name in ("eps", "revenue", "guidance", "segments", "risk", "other")
        }
        guidance_section_ids = set(guidance_fact.candidate_section_ids if guidance_fact else [])
        guidance_source_ids = (
            {source.source_id for source in guidance_fact.source_refs} if guidance_fact else set()
        )
        for section in sections:
            if (
                section.section_id in guidance_section_ids
                or section.source_ref.section_id in guidance_section_ids
                or section.source_ref.source_id in guidance_source_ids
            ):
                topic = "guidance"
            else:
                topic = self._infer_topic(section)
            grouped[topic].append(section.model_dump(mode="json"))
        return grouped

    def _infer_topic(self, section: DocumentSection) -> str:
        label = f"{section.section_id} {section.heading}\n{section.text}".lower()
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

    def _routing_report(
        self,
        section_contexts: dict[str, list[dict[str, Any]]],
        guidance_fact: GuidanceFact,
    ) -> list[dict[str, Any]]:
        guidance_sections = section_contexts["guidance_sections"]
        guidance_reason = "not_found"
        if guidance_sections:
            guidance_reason = (
                "guidance_fact"
                if guidance_fact.candidate_section_ids or guidance_fact.source_refs
                else "heading_heuristic"
            )
        return [
            self._agent_routing_report(
                "EarningsQualityAnalyst",
                section_contexts["earnings_quality_sections"],
                "topic_heuristic",
            ),
            self._agent_routing_report(
                "CashFlowRiskAnalyst",
                section_contexts["cash_flow_risk_sections"],
                "topic_heuristic",
            ),
            self._agent_routing_report(
                "ManagementIntentAnalyst",
                section_contexts["management_sections"],
                "topic_heuristic",
            ),
            self._agent_routing_report(
                "GuidanceAnalyst",
                guidance_sections,
                guidance_reason,
                empty_context_reason=(
                    "guidance_status_not_found" if not guidance_sections else None
                ),
            ),
        ]

    def _agent_routing_report(
        self,
        agent_name: str,
        sections: list[dict[str, Any]],
        routing_reason: str,
        *,
        empty_context_reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "agent_name": agent_name,
            "routed_section_ids": [section["section_id"] for section in sections],
            "routed_section_contexts": [
                {
                    "section_id": section["section_id"],
                    "page": section.get("source_ref", {}).get("page")
                    if isinstance(section.get("source_ref"), dict)
                    else None,
                    "routing_tags": section.get("routing_tags", []),
                    "routing_context": section.get("routing_context"),
                    "merged_section_ids": section.get("merged_section_ids", []),
                }
                for section in sections
            ],
            "routed_source_refs": [section["source_ref"] for section in sections],
            "routing_reason": routing_reason,
            "empty_context_reason": empty_context_reason,
        }

    def _source_manifest(
        self,
        request: ReviewRequest,
        metrics: FinancialMetrics,
        sections: list[DocumentSection],
    ) -> dict[str, Any]:
        return {
            "input_refs": {
                "filing_url": str(request.filing_url) if request.filing_url else None,
                "presentation_url": (
                    str(request.presentation_url) if request.presentation_url else None
                ),
                "transcript_url": str(request.transcript_url) if request.transcript_url else None,
                "document_files": [
                    document_file.model_dump(mode="json")
                    for document_file in request.document_files
                ],
            },
            "financial_source_refs": [
                source_ref.model_dump(mode="json", exclude_none=True)
                for source_ref in metrics.source_refs
            ],
            "document_source_refs": [
                section.source_ref.model_dump(mode="json", exclude_none=True)
                for section in sections
            ],
        }

    def _temporal_input_summary(
        self,
        request: ReviewRequest,
        metrics: FinancialMetrics,
    ) -> dict[str, Any]:
        return {
            "ticker": request.ticker,
            "fiscal_period": request.fiscal_period,
            "target_earnings_date": (
                request.target_earnings_date.isoformat() if request.target_earnings_date else None
            ),
            "target_period_end_date": (
                request.target_period_end_date.isoformat()
                if request.target_period_end_date
                else None
            ),
            "prior_fiscal_period": request.prior_fiscal_period,
            "financial_data_as_of": (
                request.financial_data_as_of.isoformat() if request.financial_data_as_of else None
            ),
            "selected_yfinance_row_date": (
                metrics.source_row_date.isoformat() if metrics.source_row_date else None
            ),
            "selected_yfinance_table_column_date": (
                metrics.source_table_column_date.isoformat()
                if metrics.source_table_column_date
                else None
            ),
            "provider_warnings": metrics.warnings,
        }

    def _temporal_source_manifest(
        self,
        metrics: FinancialMetrics,
        sections: list[DocumentSection],
    ) -> dict[str, Any]:
        return {
            "financial_source_refs": [
                source_ref.model_dump(mode="json", exclude_none=True)
                for source_ref in metrics.source_refs
            ],
            "document_source_refs": [
                section.source_ref.model_dump(mode="json", exclude_none=True)
                for section in sections
            ],
            "metric_snapshot_buckets": sorted(metrics.temporal_snapshots.keys()),
        }

    def _temporal_validation(self, metrics: FinancialMetrics) -> dict[str, Any]:
        return {
            "status": "passed_with_warnings" if metrics.warnings else "passed",
            "warnings": metrics.warnings,
            "latest_snapshot_routed_as_evidence": False,
        }

    def _document_sections_preview(
        self,
        sections: list[DocumentSection],
    ) -> list[dict[str, Any]]:
        return [
            {
                "section_id": section.section_id,
                "source_ref": section.source_ref.model_dump(mode="json", exclude_none=True),
                "heading": section.heading,
                "start_page": section.start_page,
                "end_page": section.end_page,
                "char_count": len(section.text),
                "text_preview": section.text[:500],
            }
            for section in sections
        ]

    def _context_budget_report(
        self,
        context: dict[str, Any],
        guidance_fact: GuidanceFact,
    ) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        max_input_tokens = 30_000
        agent_classes = [
            *self.financial_agent_classes,
            ManagementIntentAnalyst,
            GuidanceAnalyst,
        ]
        for agent_class in agent_classes:
            selected = {
                key: context[key]
                for key in agent_class.spec.context_keys
                if key in context and context[key] is not None
            }
            estimated_input_tokens = max(1, len(_json_for_budget(selected)) // 4)
            largest_context_keys = [
                {"key": key, "estimated_tokens": estimated_tokens}
                for key, estimated_tokens in sorted(
                    (
                        (key, max(1, len(_json_for_budget(value)) // 4))
                        for key, value in selected.items()
                    ),
                    key=lambda item: item[1],
                    reverse=True,
                )[:5]
            ]
            skipped_reason = None
            if agent_class is GuidanceAnalyst and guidance_fact.status is GuidanceStatus.NOT_FOUND:
                skipped_reason = "guidance_status_not_found"
            status = "skipped" if skipped_reason else "passed"
            if not skipped_reason and estimated_input_tokens > max_input_tokens:
                status = "failed"
            reports.append(
                {
                    "agent_name": agent_class.spec.public_role,
                    "estimated_input_tokens": estimated_input_tokens,
                    "max_input_tokens": max_input_tokens,
                    "estimated_output_tokens": agent_class.spec.max_tokens,
                    "max_output_tokens": agent_class.spec.max_tokens,
                    "status": status,
                    "largest_context_keys": largest_context_keys,
                    "remediation": (
                        "Reduce routed document text or split source sections."
                        if status == "failed"
                        else None
                    ),
                    "skipped_reason": skipped_reason,
                }
            )
        return reports

    def _enforce_context_budget(
        self,
        context: dict[str, Any],
        guidance_fact: GuidanceFact,
    ) -> None:
        failed = [
            report
            for report in self._context_budget_report(context, guidance_fact)
            if report["status"] == "failed"
        ]
        if not failed:
            return
        failed_agents = ", ".join(report["agent_name"] for report in failed)
        raise WorkflowValidationError(f"context budget failed for: {failed_agents}")

    def _strict_guidance_enabled(self) -> bool:
        return os.getenv("EARNINGS_DEBATE_STRICT_GUIDANCE", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }

    def _validate_strict_guidance(
        self,
        guidance_fact: GuidanceFact,
        metrics: FinancialMetrics,
    ) -> None:
        if (
            guidance_fact.status in {GuidanceStatus.FOUND, GuidanceStatus.NOT_DISCLOSED}
            and guidance_fact.source_refs
        ):
            return
        if guidance_fact.status is GuidanceStatus.FOUND and metrics.guidance:
            return
        raise GuidanceAcquisitionError(
            "Strict guidance inspection requires source-backed guidance or a source-backed no-guidance disclosure."
        )


def _json_for_budget(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_json_default)


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)

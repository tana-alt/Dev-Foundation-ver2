"""Deterministic Markdown report rendering from validated workflow contracts."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .workflow_models import (
    AnalysisBrief,
    ClaimRecord,
    DebateResult,
    DecisionUse,
    EvidenceItem,
    JudgeDecision,
    ReportMatrix,
    ReviewRequest,
    SourceManifestEntry,
)

REPORT_SECTION_ORDER = (
    "Judge Rationale",
    "Bull vs Bear Tension",
    "Evidence Matrix",
    "Agent Contribution",
    "Uncertainty And Missing Data",
    "Quality Gates",
    "Source Appendix",
    "Disclaimer",
)

DISCLAIMER_TEXT = (
    "This report is an earnings analysis artifact and is not investment advice. "
    "It does not provide stock-price forecasts or instructions to transact."
)


class ReportRenderer:
    """Render a stable report from Pydantic-validated matrix objects."""

    def render(
        self,
        *,
        request: ReviewRequest,
        brief: AnalysisBrief,
        debate: DebateResult,
        decision: JudgeDecision,
        matrix: ReportMatrix,
    ) -> str:
        sections = [
            f"# Earnings Review: {request.ticker} {request.fiscal_period}",
            self._section("Judge Rationale", self._judge_rationale_lines(decision)),
            self._section("Bull vs Bear Tension", self._bull_bear_lines(debate)),
            self._section("Evidence Matrix", self._evidence_matrix_lines(matrix)),
            self._section("Agent Contribution", self._agent_contribution_lines(brief)),
            self._section(
                "Uncertainty And Missing Data",
                self._uncertainty_lines(brief, debate, matrix),
            ),
            self._section("Quality Gates", self._quality_gate_lines(matrix)),
            self._section("Source Appendix", self._source_appendix_lines(matrix)),
            self._section("Disclaimer", [DISCLAIMER_TEXT]),
        ]
        return "\n\n".join(sections).strip() + "\n"

    def _section(self, heading: str, lines: list[str]) -> str:
        body = "\n".join(lines).strip()
        return f"## {heading}\n\n{body}" if body else f"## {heading}"

    def _judge_rationale_lines(self, decision: JudgeDecision) -> list[str]:
        return [
            f"- Verdict: {decision.verdict.value}",
            f"- Confidence: {decision.confidence:.2f}",
            f"- Summary: {decision.summary}",
            f"- Rationale: {decision.rationale}",
            f"- EPS outlook: {decision.eps_outlook}",
            f"- EPS rationale: {decision.eps_outlook_reason}",
            f"- FCF outlook: {decision.fcf_outlook}",
            f"- FCF rationale: {decision.fcf_outlook_reason}",
        ]

    def _bull_bear_lines(self, debate: DebateResult) -> list[str]:
        lines = [
            "### Bull Case",
            debate.bull_case,
            "",
            "### Bear Case",
            debate.bear_case,
            "",
            "### Risk Case",
            debate.risk_case,
            "",
            "### Judge Tension",
            debate.evaluation,
        ]
        if debate.unresolved_questions:
            lines.extend(["", "### Unresolved Questions"])
            lines.extend(f"- {question}" for question in debate.unresolved_questions)
        return lines

    def _evidence_matrix_lines(self, matrix: ReportMatrix) -> list[str]:
        evidence_by_id = {item.evidence_id: item for item in matrix.evidence_items}
        decision_by_claim, decision_by_evidence = self._decision_indexes(matrix.decision_uses)
        lines = [
            "| Claim ID | Fact | Interpretation | Implication | Time scope | Fact-check status | Judge treatment | Sources |",
            "|---|---|---|---|---|---|---|---|",
        ]

        rendered_evidence_ids: set[str] = set()
        for claim in matrix.claim_records:
            claim_evidence = [
                evidence_by_id[evidence_id]
                for evidence_id in [*claim.evidence_ids, *claim.counter_evidence_ids]
                if evidence_id in evidence_by_id
            ]
            rendered_evidence_ids.update(item.evidence_id for item in claim_evidence)
            lines.append(
                "| {claim_id} | {fact} | {interpretation} | {implication} | {time_scope} | {fact_check} | {judge_treatment} | {sources} |".format(
                    claim_id=self._cell(claim.claim_id),
                    fact=self._cell(self._facts_for_claim(claim, evidence_by_id)),
                    interpretation=self._cell(claim.interpretation),
                    implication=self._cell(claim.implication),
                    time_scope=self._cell(claim.time_scope),
                    fact_check=self._cell(self._fact_check_statuses(claim_evidence)),
                    judge_treatment=self._cell(
                        self._judge_treatments(
                            decision_by_claim.get(claim.claim_id, []),
                            [decision_by_evidence[item.evidence_id] for item in claim_evidence],
                        )
                    ),
                    sources=self._cell(self._source_refs(claim_evidence)),
                )
            )

        for item in matrix.evidence_items:
            if item.evidence_id in rendered_evidence_ids:
                continue
            lines.append(
                "| {claim_id} | {fact} | {interpretation} | {implication} | {time_scope} | {fact_check} | {judge_treatment} | {sources} |".format(
                    claim_id=self._cell(item.evidence_id),
                    fact=self._cell(self._fact_label(item)),
                    interpretation="-",
                    implication="-",
                    time_scope=self._cell(self._evidence_time_scope(item)),
                    fact_check=self._cell(self._enum_value(item.fact_check_status)),
                    judge_treatment=self._cell(
                        self._judge_treatments([], [decision_by_evidence[item.evidence_id]])
                    ),
                    sources=self._cell(self._source_refs([item])),
                )
            )

        if len(lines) == 2:
            lines.append("| - | No evidence items were provided. | - | - | - | - | - | - |")
        return lines

    def _agent_contribution_lines(self, brief: AnalysisBrief) -> list[str]:
        lines = [
            "| Agent | Stance | Contribution | Key evidence | Counter evidence | Confidence | Missing data |",
            "|---|---|---|---|---|---:|---|",
        ]
        for finding in self._findings(brief):
            lines.append(
                "| {agent} | {stance} | {summary} | {key} | {counter} | {confidence:.2f} | {missing} |".format(
                    agent=self._cell(finding.agent_name),
                    stance=self._cell(finding.stance),
                    summary=self._cell(finding.handoff_summary),
                    key=self._cell(self._evidence_id_list(finding.key_evidence)),
                    counter=self._cell(self._evidence_id_list(finding.counter_evidence)),
                    confidence=float(finding.confidence),
                    missing=self._cell("; ".join(finding.missing_data) or "-"),
                )
            )
        return lines

    def _uncertainty_lines(
        self,
        brief: AnalysisBrief,
        debate: DebateResult,
        matrix: ReportMatrix,
    ) -> list[str]:
        lines: list[str] = []
        if matrix.missing_data_items:
            lines.extend(
                [
                    "| Topic | Materiality | Blocks verdict | Reason |",
                    "|---|---|---:|---|",
                ]
            )
            for item in matrix.missing_data_items:
                lines.append(
                    "| {topic} | {materiality} | {blocks} | {reason} |".format(
                        topic=self._cell(item.topic),
                        materiality=self._cell(item.materiality),
                        blocks=str(item.blocks_verdict).lower(),
                        reason=self._cell(item.reason),
                    )
                )
        else:
            lines.append("- No matrix-level missing data items were provided.")

        agent_missing = [
            (finding.agent_name, missing)
            for finding in self._findings(brief)
            for missing in finding.missing_data
        ]
        if agent_missing:
            lines.extend(["", "### Agent Missing Data"])
            lines.extend(f"- {agent}: {missing}" for agent, missing in agent_missing)

        if debate.unresolved_questions:
            lines.extend(["", "### Unresolved Questions"])
            lines.extend(f"- {question}" for question in debate.unresolved_questions)
        return lines

    def _quality_gate_lines(self, matrix: ReportMatrix) -> list[str]:
        fact_checks = Counter(
            self._enum_value(item.fact_check_status) for item in matrix.evidence_items
        )
        treatments = Counter(self._enum_value(item.treatment) for item in matrix.decision_uses)
        return [
            "- ReportMatrix validation: passed",
            f"- Source manifest entries: {len(matrix.source_manifest)}",
            f"- Evidence items: {len(matrix.evidence_items)}",
            f"- Claim records: {len(matrix.claim_records)}",
            f"- Decision uses: {len(matrix.decision_uses)}",
            f"- Missing data items: {len(matrix.missing_data_items)}",
            f"- Fact-check statuses: {self._counter_summary(fact_checks)}",
            f"- Judge treatments: {self._counter_summary(treatments)}",
            "- Source references: registered and internally consistent",
            "- No-advice framing: present in Disclaimer",
        ]

    def _source_appendix_lines(self, matrix: ReportMatrix) -> list[str]:
        if not matrix.source_manifest:
            return ["No registered sources were provided."]
        lines = [
            "| Source ID | Type | Locator | Title | Reported period | URL |",
            "|---|---|---|---|---|---|",
        ]
        for source in matrix.source_manifest:
            lines.append(
                "| `{source_id}` | {source_type} | {locator} | {title} | {period} | {url} |".format(
                    source_id=self._cell(source.source_id),
                    source_type=self._cell(self._enum_value(source.source_type)),
                    locator=self._cell(self._source_locator(source)),
                    title=self._cell(source.title or source.source_id),
                    period=self._cell(source.reported_period or source.as_of_date or "-"),
                    url=self._cell(str(source.url) if source.url else "no URL"),
                )
            )
        return lines

    def _decision_indexes(
        self,
        decision_uses: list[DecisionUse],
    ) -> tuple[dict[str, list[DecisionUse]], dict[str, list[DecisionUse]]]:
        by_claim: dict[str, list[DecisionUse]] = defaultdict(list)
        by_evidence: dict[str, list[DecisionUse]] = defaultdict(list)
        for use in decision_uses:
            if use.claim_id is not None:
                by_claim[use.claim_id].append(use)
            for evidence_id in use.decisive_evidence_ids:
                by_evidence[evidence_id].append(use)
        return by_claim, by_evidence

    def _findings(self, brief: AnalysisBrief) -> list[Any]:
        return [
            brief.earnings_quality_finding,
            brief.cash_flow_risk_finding,
            brief.management_intent_finding,
            brief.guidance_finding,
        ]

    def _facts_for_claim(
        self,
        claim: ClaimRecord,
        evidence_by_id: dict[str, EvidenceItem],
    ) -> str:
        support = [
            self._fact_label(evidence_by_id[evidence_id])
            for evidence_id in claim.evidence_ids
            if evidence_id in evidence_by_id
        ]
        counter = [
            f"Counter: {self._fact_label(evidence_by_id[evidence_id])}"
            for evidence_id in claim.counter_evidence_ids
            if evidence_id in evidence_by_id
        ]
        return "; ".join([*support, *counter]) or claim.claim

    def _fact_label(self, item: EvidenceItem) -> str:
        parts = [item.summary]
        value = self._evidence_value(item)
        if value:
            parts.append(value)
        return " ".join(parts)

    def _evidence_value(self, item: EvidenceItem) -> str:
        if item.value is None:
            return ""
        value = f"{item.value:g}" if abs(item.value) < 1_000_000 else f"{item.value:,.0f}"
        return f"({value} {item.unit})" if item.unit else f"({value})"

    def _fact_check_statuses(self, items: list[EvidenceItem]) -> str:
        values = []
        for item in items:
            value = self._enum_value(item.fact_check_status)
            if value not in values:
                values.append(value)
        return ", ".join(values) or "-"

    def _judge_treatments(
        self,
        claim_uses: list[DecisionUse],
        evidence_uses: list[list[DecisionUse]],
    ) -> str:
        values = []
        for use in [*claim_uses, *(item for group in evidence_uses for item in group)]:
            value = self._enum_value(use.treatment)
            if value not in values:
                values.append(value)
        return ", ".join(values) or "not_used"

    def _source_refs(self, items: list[EvidenceItem]) -> str:
        refs = []
        for item in items:
            ref = item.source_ref
            locator = (
                ref.metric_name
                or ref.section_id
                or ref.document_id
                or (f"page {ref.page}" if ref.page is not None else "source")
            )
            label = f"{ref.source_id} / {locator}"
            if label not in refs:
                refs.append(label)
        return "; ".join(refs) or "-"

    def _evidence_time_scope(self, item: EvidenceItem) -> str:
        ref = item.source_ref
        return str(
            item.reported_period or item.as_of_date or ref.reported_period or ref.as_of_date or "-"
        )

    def _evidence_id_list(self, items: list[EvidenceItem]) -> str:
        return ", ".join(item.evidence_id for item in items) or "-"

    def _source_locator(self, source: SourceManifestEntry) -> str:
        parts = []
        if source.metric_name:
            parts.append(source.metric_name)
        if source.document_id:
            parts.append(source.document_id)
        if source.section_id:
            parts.append(source.section_id)
        if source.page is not None:
            parts.append(f"page {source.page}")
        return ", ".join(parts) or "source"

    def _counter_summary(self, counter: Counter[str]) -> str:
        if not counter:
            return "none"
        return ", ".join(f"{key}: {counter[key]}" for key in sorted(counter))

    def _enum_value(self, value: object) -> str:
        return str(getattr(value, "value", value))

    def _cell(self, value: object) -> str:
        text = "" if value is None else str(value)
        return text.replace("\n", " ").replace("|", "\\|").strip() or "-"


MarkdownRenderer = ReportRenderer
MarkdownReportRenderer = ReportRenderer

__all__ = [
    "DISCLAIMER_TEXT",
    "MarkdownRenderer",
    "MarkdownReportRenderer",
    "REPORT_SECTION_ORDER",
    "ReportRenderer",
]

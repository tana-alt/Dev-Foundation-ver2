"""Deterministic validation and evidence aggregation for the review workflow."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from typing import Any, TypeVar

from pydantic import BaseModel

from .workflow_models import (
    REQUIRED_FINDING_COVERAGE_KEYS,
    AgentResult,
    AgentRole,
    AgentTeam,
    AnalysisBrief,
    CashFlowRiskFinding,
    DocumentSection,
    EarningsQualityFinding,
    EvidenceItem,
    EvidencePolarity,
    FinancialMetrics,
    GuidanceFinding,
    ImpactArea,
    JudgeDecision,
    ManagementIntentFinding,
    ReviewRequest,
    SourceRef,
    StepState,
    StepStatus,
    WorkflowStep,
)

ModelT = TypeVar("ModelT", bound=BaseModel)
LineRangeSignature = tuple[int, int] | None
SourceSignature = tuple[
    str,
    str,
    str | None,
    str | None,
    str | None,
    int | None,
    str | None,
    str | None,
    str | None,
    date | None,
    int | None,
    int | None,
    LineRangeSignature,
]


class WorkflowValidationError(ValueError):
    """Raised when a deterministic workflow gate fails."""


INVESTMENT_ADVICE_PATTERNS = (
    re.compile(r"\b(buy|sell|hold)\s+(the\s+)?(stock|shares)\b", re.IGNORECASE),
    re.compile(r"\b(buy|sell|hold)\s+[A-Z]{1,6}\b", re.IGNORECASE),
    re.compile(r"\b(stock|shares)\s+(is|are)\s+a\s+(buy|sell|hold)\b", re.IGNORECASE),
    re.compile(
        r"\brecommend(s|ed|ing)?\s+(buying|selling|holding|to\s+(buy|sell|hold))\b",
        re.IGNORECASE,
    ),
    re.compile(r"\byou\s+should\s+(buy|sell|hold)\b", re.IGNORECASE),
    re.compile(
        r"\b(initiate|open|take|add\s+to|establish|build)\s+"
        r"(a\s+)?(long|short)\s+position\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(go|going)\s+(long|short)\b", re.IGNORECASE),
    re.compile(r"\b(long|short)\s+(the\s+)?(stock|shares)\b", re.IGNORECASE),
    re.compile(r"\b(long|short)\s+(?-i:[A-Z]{1,6})\b", re.IGNORECASE),
    re.compile(r"\b(price target|target price)\b", re.IGNORECASE),
    re.compile(r"目標株価"),
    re.compile(r"売買推奨|投資推奨|買い推奨|売り推奨|購入を推奨"),
    re.compile(r"買うべき|売るべき|保有すべき"),
)


class WorkflowValidationGate:
    """Owns deterministic workflow gates that do not require LLM calls."""

    def aggregate_evidence(
        self,
        request: ReviewRequest,
        metrics: FinancialMetrics,
        sections: list[DocumentSection],
        financial_findings: list[BaseModel],
        presentation_findings: list[BaseModel],
    ) -> AnalysisBrief:
        canonical_sources = self.canonical_source_refs(metrics, sections)
        allowed_source_ids = set(canonical_sources)
        (
            earnings_quality_finding,
            cash_flow_risk_finding,
            management_intent_finding,
            guidance_finding,
        ) = self.specialist_findings(financial_findings, presentation_findings)
        financial_results = [
            self.finding_to_agent_result(finding, AgentTeam.FINANCIAL)
            for finding in financial_findings
        ]
        presentation_results = [
            self.finding_to_agent_result(finding, AgentTeam.PRESENTATION)
            for finding in presentation_findings
        ]

        positive = self.dedupe_evidence(
            [
                *self.collect_evidence(
                    financial_findings, "key_evidence", EvidencePolarity.POSITIVE
                ),
                *self.collect_evidence(
                    presentation_findings, "key_evidence", EvidencePolarity.POSITIVE
                ),
            ]
        )
        negative = self.dedupe_evidence(
            [
                *self.collect_evidence(
                    financial_findings, "counter_evidence", EvidencePolarity.NEGATIVE
                ),
                *self.collect_evidence(
                    presentation_findings, "counter_evidence", EvidencePolarity.NEGATIVE
                ),
            ]
        )
        if not positive:
            raise WorkflowValidationError("positive evidence pool is empty after aggregation")
        if not negative:
            raise WorkflowValidationError("negative evidence pool is empty after aggregation")
        self.validate_evidence_sources([*positive, *negative], allowed_source_ids)
        positive = self.canonicalize_evidence_sources(positive, canonical_sources)
        negative = self.canonicalize_evidence_sources(negative, canonical_sources)
        risks = [item for item in negative if EvidencePolarity.NEGATIVE == item.polarity]

        synthesis = " ".join(
            self.text_attr(finding, "handoff_summary")
            or self.text_attr(finding, "summary")
            or self.text_attr(finding, "conclusion")
            for finding in [*financial_findings, *presentation_findings]
        ).strip()
        if not synthesis:
            synthesis = "Validated specialist findings were aggregated for debate."

        return AnalysisBrief(
            ticker=request.ticker,
            fiscal_period=request.fiscal_period,
            earnings_quality_finding=earnings_quality_finding,
            cash_flow_risk_finding=cash_flow_risk_finding,
            management_intent_finding=management_intent_finding,
            guidance_finding=guidance_finding,
            financial_agent_results=financial_results,
            presentation_agent_results=presentation_results,
            positive_evidence_pool=positive[:30],
            negative_evidence_pool=negative[:30],
            risk_evidence_pool=risks[:30],
            synthesis=synthesis[:2000],
        )

    def validate_judge_decision(
        self,
        decision: JudgeDecision,
        brief: AnalysisBrief,
    ) -> JudgeDecision:
        if not decision.positive_evidence:
            raise WorkflowValidationError("judge_decision.positive_evidence must not be empty")
        if not decision.negative_evidence:
            raise WorkflowValidationError("judge_decision.negative_evidence must not be empty")
        for item in decision.positive_evidence:
            if item.polarity != EvidencePolarity.POSITIVE:
                raise WorkflowValidationError("judge positive_evidence must have positive polarity")
        for item in decision.negative_evidence:
            if item.polarity not in {EvidencePolarity.NEGATIVE, EvidencePolarity.RISK}:
                raise WorkflowValidationError(
                    "judge negative_evidence must have negative or risk polarity"
                )

        positive_by_id = {item.evidence_id: item for item in brief.positive_evidence_pool}
        negative_by_id = {item.evidence_id: item for item in brief.negative_evidence_pool}
        positive = self.validated_evidence_items(
            decision.positive_evidence,
            positive_by_id,
            "judge_decision.positive_evidence",
        )
        negative = self.validated_evidence_items(
            decision.negative_evidence,
            negative_by_id,
            "judge_decision.negative_evidence",
        )
        return decision.model_copy(
            update={
                "positive_evidence": positive,
                "negative_evidence": negative,
            }
        )

    def finding_to_agent_result(self, finding: BaseModel, team: AgentTeam) -> AgentResult:
        role_name = self.extract_role_name(finding)
        return AgentResult(
            agent_role=self.role_for_name(role_name),
            team=team,
            status=StepStatus(
                step=WorkflowStep.FINANCIAL_AGENTS
                if team == AgentTeam.FINANCIAL
                else WorkflowStep.PRESENTATION_AGENTS,
                state=StepState.COMPLETED,
            ),
            headline=(
                self.text_attr(finding, "summary")
                or self.text_attr(finding, "headline")
                or role_name
            )[:300],
            conclusion=(
                self.text_attr(finding, "handoff_summary")
                or self.text_attr(finding, "summary")
                or role_name
            )[:1200],
            key_evidence=self.collect_evidence(
                [finding], "key_evidence", EvidencePolarity.POSITIVE
            )[:10],
            counter_evidence=self.collect_evidence(
                [finding], "counter_evidence", EvidencePolarity.NEGATIVE
            )[:10],
            open_questions=self.list_attr(finding, "missing_data")[:8],
            confidence=float(getattr(finding, "confidence", 0.5)),
        )

    def specialist_findings(
        self,
        financial_findings: list[BaseModel],
        presentation_findings: list[BaseModel],
    ) -> tuple[
        EarningsQualityFinding,
        CashFlowRiskFinding,
        ManagementIntentFinding,
        GuidanceFinding,
    ]:
        findings = [*financial_findings, *presentation_findings]
        by_role = {self.extract_role_name(finding): finding for finding in findings}

        return (
            self.require_finding(
                by_role,
                "EarningsQualityAnalyst",
                EarningsQualityFinding,
            ),
            self.require_finding(
                by_role,
                "CashFlowRiskAnalyst",
                CashFlowRiskFinding,
            ),
            self.require_finding(
                by_role,
                "ManagementIntentAnalyst",
                ManagementIntentFinding,
            ),
            self.require_finding(
                by_role,
                "GuidanceAnalyst",
                GuidanceFinding,
            ),
        )

    def require_finding(
        self,
        by_role: dict[str, BaseModel],
        role_name: str,
        model_type: type[ModelT],
    ) -> ModelT:
        finding = by_role.get(role_name)
        if finding is None:
            raise WorkflowValidationError(f"{role_name} finding is required")
        if isinstance(finding, model_type):
            return finding
        return model_type.model_validate(finding.model_dump(mode="json"))

    def validate_finding_coverage(self, case: BaseModel, field_name: str) -> None:
        coverage = getattr(case, "finding_coverage", None)
        if coverage is None:
            raise WorkflowValidationError(f"{field_name}.finding_coverage is required")
        keys = set(coverage)
        if keys != REQUIRED_FINDING_COVERAGE_KEYS:
            raise WorkflowValidationError(
                f"{field_name}.finding_coverage must cover "
                f"{', '.join(sorted(REQUIRED_FINDING_COVERAGE_KEYS))}"
            )

    def validated_case_evidence(
        self,
        case: BaseModel,
        evidence_field: str,
        allowed_by_id: dict[str, EvidenceItem],
        case_name: str,
        default_polarity: EvidencePolarity,
    ) -> list[EvidenceItem]:
        items = self.collect_evidence([case], evidence_field, default_polarity)
        if not items:
            raise WorkflowValidationError(f"{case_name}.{evidence_field} must not be empty")

        validated: list[EvidenceItem] = []
        for item in items:
            canonical = allowed_by_id.get(item.evidence_id)
            self.validate_evidence_item_against_canonical(
                item,
                canonical,
                f"{case_name}.{evidence_field}",
            )
            assert canonical is not None
            validated.append(canonical)

        return self.dedupe_evidence(validated)

    def validated_evidence_items(
        self,
        items: list[EvidenceItem],
        allowed_by_id: dict[str, EvidenceItem],
        field_name: str,
    ) -> list[EvidenceItem]:
        validated: list[EvidenceItem] = []
        for item in items:
            canonical = allowed_by_id.get(item.evidence_id)
            self.validate_evidence_item_against_canonical(item, canonical, field_name)
            assert canonical is not None
            validated.append(canonical)
        return self.dedupe_evidence(validated)

    def validate_evidence_item_against_canonical(
        self,
        item: EvidenceItem,
        canonical: EvidenceItem | None,
        field_name: str,
    ) -> None:
        if canonical is None:
            raise WorkflowValidationError(
                f"{field_name} evidence {item.evidence_id!r} "
                "was not present in validated AnalysisBrief evidence"
            )
        if self.source_signature(item.source_ref) != self.source_signature(canonical.source_ref):
            raise WorkflowValidationError(
                f"{field_name} evidence {item.evidence_id!r} changed the validated source_ref"
            )

    def validate_no_investment_advice_text(self, value: Any, field_name: str) -> None:
        for path, text in self.iter_text_values(value, field_name):
            for pattern in INVESTMENT_ADVICE_PATTERNS:
                if pattern.search(text):
                    raise WorkflowValidationError(
                        f"{path} contains investment-advice language: {pattern.pattern}"
                    )

    def iter_text_values(self, value: Any, path: str):
        if isinstance(value, BaseModel):
            yield from self.iter_text_values(value.model_dump(mode="json"), path)
            return
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in {"agent_name", "purpose", "is_investment_advice"}:
                    continue
                yield from self.iter_text_values(nested, f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, nested in enumerate(value):
                yield from self.iter_text_values(nested, f"{path}[{index}]")
            return
        if isinstance(value, str):
            yield path, value

    def collect_evidence(
        self,
        findings: list[BaseModel],
        field_name: str,
        default_polarity: EvidencePolarity,
    ) -> list[EvidenceItem]:
        collected: list[EvidenceItem] = []
        for finding in findings:
            raw_items = getattr(finding, field_name, []) or []
            role_name = self.extract_role_name(finding)
            for index, raw in enumerate(raw_items, start=1):
                collected.append(
                    self.coerce_evidence(
                        raw,
                        default_polarity=default_polarity,
                        fallback_id=f"{self.slug(role_name)}:{field_name}:{index}",
                    )
                )
        return collected

    def coerce_evidence(
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
            evidence_id=self.slug(str(data.get("evidence_id") or fallback_id))[:80],
            polarity=polarity,
            summary=str(data.get("summary") or data.get("claim") or "Evidence item")[:300],
            detail=str(
                data.get("detail") or data.get("summary") or data.get("claim") or "Evidence item"
            )[:1200],
            impact_areas=self.impact_areas(data),
            source_ref=source_ref,
            metric_name=data.get("metric_name") or data.get("metric"),
            value=data.get("value"),
            unit=data.get("unit"),
            confidence=float(data.get("confidence", 0.5)),
        )

    def impact_areas(self, data: dict[str, Any]) -> list[ImpactArea]:
        raw = data.get("impact_areas") or data.get("impact_area")
        values = raw if isinstance(raw, list) else [raw] if raw else [ImpactArea.OVERALL]
        result: list[ImpactArea] = []
        for value in values:
            try:
                result.append(value if isinstance(value, ImpactArea) else ImpactArea(str(value)))
            except ValueError:
                result.append(ImpactArea.OVERALL)
        return result

    def dedupe_evidence(self, items: list[EvidenceItem]) -> list[EvidenceItem]:
        seen: set[str] = set()
        result: list[EvidenceItem] = []
        for item in items:
            key = item.evidence_id
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def canonical_source_refs(
        self,
        metrics: FinancialMetrics,
        sections: list[DocumentSection],
    ) -> dict[SourceSignature, SourceRef]:
        return {
            self.source_signature(source): source
            for source in [
                *metrics.source_refs,
                *(section.source_ref for section in sections),
            ]
        }

    def canonicalize_evidence_sources(
        self,
        items: list[EvidenceItem],
        canonical_sources: dict[SourceSignature, SourceRef],
    ) -> list[EvidenceItem]:
        canonicalized: list[EvidenceItem] = []
        for item in items:
            matched_signature = self.matching_source_signature(
                item.source_ref,
                canonical_sources,
            )
            if matched_signature is None:
                raise WorkflowValidationError(
                    f"evidence {item.evidence_id!r} references unknown source "
                    f"{item.source_ref.source_id!r}"
                )
            canonicalized.append(
                item.model_copy(update={"source_ref": canonical_sources[matched_signature]})
            )
        return canonicalized

    def validate_evidence_sources(
        self,
        items: list[EvidenceItem],
        allowed_source_ids: set[SourceSignature],
    ) -> None:
        allowed_source_names = {source_id for source_id, *_ in allowed_source_ids}
        for item in items:
            if self.matching_source_signature(item.source_ref, allowed_source_ids) is not None:
                continue
            if item.source_ref.source_id in allowed_source_names:
                raise WorkflowValidationError(
                    f"evidence {item.evidence_id!r} references source "
                    f"{item.source_ref.source_id!r} with mismatched locator"
                )
            else:
                raise WorkflowValidationError(
                    f"evidence {item.evidence_id!r} references unknown source "
                    f"{item.source_ref.source_id!r}"
                )

    def source_signature(self, source: SourceRef) -> SourceSignature:
        line_range = None
        if source.line_range is not None:
            line_range = (source.line_range.start, source.line_range.end)
        return (
            source.source_id,
            source.source_type.value,
            source.document_id,
            source.section_id,
            source.metric_name,
            source.page,
            source.title,
            str(source.url) if source.url is not None else None,
            source.reported_period,
            source.as_of_date,
            source.line_start,
            source.line_end,
            line_range,
        )

    def matching_source_signature(
        self,
        source: SourceRef,
        allowed_source_ids: Iterable[SourceSignature],
    ) -> SourceSignature | None:
        signature = self.source_signature(source)
        allowed_signatures = set(allowed_source_ids)
        if signature in allowed_signatures:
            return signature
        for candidate in allowed_signatures:
            if self.source_signatures_are_compatible(signature, candidate):
                return candidate
        return None

    def source_signatures_are_compatible(
        self,
        emitted: SourceSignature,
        canonical: SourceSignature,
    ) -> bool:
        if emitted[:7] != canonical[:7]:
            return False
        for emitted_value, canonical_value in zip(emitted[7:], canonical[7:], strict=True):
            if emitted_value is None or canonical_value is None:
                continue
            if emitted_value != canonical_value:
                return False
        return True

    def extract_role_name(self, model: BaseModel) -> str:
        for field_name in ("agent_name", "agent_role", "role"):
            if hasattr(model, field_name):
                value = getattr(model, field_name)
                return str(getattr(value, "value", value))
        return type(model).__name__

    def role_for_name(self, role_name: str) -> AgentRole:
        normalized = role_name.lower()
        mapping = {
            "earningsqualityanalyst": AgentRole.EARNINGS_QUALITY,
            "epsqualityanalyst": AgentRole.EARNINGS_QUALITY,
            "eps_analyst": AgentRole.EARNINGS_QUALITY,
            "profitabilityanalyst": AgentRole.EARNINGS_QUALITY,
            "pnl_analyst": AgentRole.EARNINGS_QUALITY,
            "cashflowriskanalyst": AgentRole.CASH_FLOW_RISK,
            "cashflowfcfanalyst": AgentRole.CASH_FLOW_RISK,
            "cfs_analyst": AgentRole.CASH_FLOW_RISK,
            "balancesheetriskanalyst": AgentRole.CASH_FLOW_RISK,
            "bs_analyst": AgentRole.CASH_FLOW_RISK,
            "managementintentanalyst": AgentRole.MANAGEMENT_INTENT,
            "management_eval": AgentRole.MANAGEMENT_INTENT,
            "guidanceanalyst": AgentRole.GUIDANCE,
            "guidance": AgentRole.GUIDANCE,
        }
        return mapping.get(normalized, AgentRole.JUDGE)

    def text_attr(self, model: BaseModel, field_name: str) -> str:
        value = getattr(model, field_name, "")
        return str(value).strip() if value is not None else ""

    def list_attr(self, model: BaseModel, field_name: str) -> list[str]:
        value = getattr(model, field_name, []) or []
        return [str(item) for item in value]

    def slug(self, value: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9_.:-]+", ":", value.strip())
        return slug.strip(":") or "evidence"


__all__ = [
    "INVESTMENT_ADVICE_PATTERNS",
    "WorkflowValidationError",
    "WorkflowValidationGate",
]

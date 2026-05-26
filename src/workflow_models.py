"""API-first workflow contracts for earnings review.

These models define the boundary between workflow stages:
Data ingestion -> Financial Agents -> Presentation Agents ->
Evidence Aggregation -> Debate -> Judge -> MarkdownRenderer.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    AliasChoices,
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


NonEmptyText = Annotated[str, Field(min_length=1)]


class WorkflowModel(BaseModel):
    """Strict base for API contracts passed between workflow stages."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class VerdictLabel(str, Enum):
    GOOD = "good"
    NEUTRAL = "neutral"
    BAD = "bad"


class SourceType(str, Enum):
    FINANCIAL_API = "financial_api"
    DERIVED_METRIC = "derived_metric"
    EARNINGS_PRESENTATION = "earnings_presentation"
    FILING = "filing"
    EARNINGS_CALL = "earnings_call"
    PRESS_RELEASE = "press_release"
    MANUAL_UPLOAD = "manual_upload"


class EvidencePolarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    RISK = "risk"


class ImpactArea(str, Enum):
    EPS = "eps"
    FCF = "fcf"
    GUIDANCE = "guidance"
    BALANCE_SHEET = "balance_sheet"
    OVERALL = "overall"


class WorkflowStep(str, Enum):
    DATA_INGESTION = "data_ingestion"
    FINANCIAL_AGENTS = "financial_agents"
    PRESENTATION_AGENTS = "presentation_agents"
    EVIDENCE_AGGREGATION = "evidence_aggregation"
    DEBATE = "debate"
    JUDGE = "judge"
    MARKDOWN_RENDERER = "markdown_renderer"


class StepState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentRole(str, Enum):
    EPS_ANALYST = "eps_analyst"
    PNL_ANALYST = "pnl_analyst"
    CFS_ANALYST = "cfs_analyst"
    BS_ANALYST = "bs_analyst"
    MANAGEMENT_EVAL = "management_eval"
    GUIDANCE = "guidance"
    BULL = "bull"
    BEAR = "bear"
    RISK = "risk"
    EVAL = "eval"
    JUDGE = "judge"


class AgentTeam(str, Enum):
    FINANCIAL = "financial"
    PRESENTATION = "presentation"
    DEBATE = "debate"
    JUDGE = "judge"


class SourceRef(WorkflowModel):
    """Traceable reference for source-backed claims.

    Financial sources must identify the metric. Document-like sources must
    identify a document location, URL, or page so downstream validators can
    reject untraceable evidence.
    """

    source_id: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9_.:-]+$",
        description="Stable ID used to trace evidence back to source material.",
    )
    source_type: SourceType
    title: str | None = Field(default=None, max_length=300)
    url: AnyUrl | None = None
    document_id: str | None = Field(default=None, max_length=120)
    section_id: str | None = Field(default=None, max_length=120)
    page: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    metric_name: str | None = Field(default=None, max_length=120)
    as_of_date: date | None = None

    @model_validator(mode="after")
    def validate_locator(self) -> SourceRef:
        if self.line_end is not None:
            if self.line_start is None:
                raise ValueError("line_end requires line_start")
            if self.line_end < self.line_start:
                raise ValueError("line_end must be greater than or equal to line_start")

        if self.source_type in {SourceType.FINANCIAL_API, SourceType.DERIVED_METRIC}:
            if not self.metric_name:
                raise ValueError("financial source_ref requires metric_name")
            return self

        has_document_locator = any(
            [self.document_id, self.section_id, self.page is not None, self.url]
        )
        if not has_document_locator:
            raise ValueError("document source_ref requires document_id, section_id, page, or url")
        return self


class DocumentSection(WorkflowModel):
    section_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    source_ref: SourceRef
    heading: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=12000)
    start_page: int | None = Field(default=None, ge=1)
    end_page: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_pages(self) -> DocumentSection:
        if self.end_page is not None:
            if self.start_page is None:
                raise ValueError("end_page requires start_page")
            if self.end_page < self.start_page:
                raise ValueError("end_page must be greater than or equal to start_page")
        return self


class FinancialMetrics(WorkflowModel):
    ticker: str = Field(min_length=1, max_length=15)
    fiscal_period: str = Field(pattern=r"^\d{4}Q[1-4]$")
    period_end_date: date | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)

    revenue: float | None = None
    revenue_consensus: float | None = None
    revenue_surprise_pct: float | None = None

    eps: float | None = None
    eps_consensus: float | None = None
    eps_surprise_pct: float | None = None

    operating_margin_pct: float | None = None
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None
    capex: float | None = None

    guidance: str | None = Field(default=None, max_length=2000)
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=20)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = str(value).upper().strip()
        if not re.fullmatch(r"[A-Z0-9.\-]{1,15}", normalized):
            raise ValueError("ticker must contain only letters, numbers, dots, or hyphens")
        return normalized

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = str(value).upper().strip()
        if not re.fullmatch(r"[A-Z]{3}", normalized):
            raise ValueError("currency must be a 3-letter ISO code")
        return normalized


class ReviewRequest(WorkflowModel):
    request_id: str | None = Field(default=None, max_length=80)
    ticker: str = Field(min_length=1, max_length=15)
    fiscal_period: str = Field(
        validation_alias=AliasChoices("fiscal_period", "quarter"),
        pattern=r"^\d{4}Q[1-4]$",
    )
    filing_url: AnyUrl | None = None
    presentation_url: AnyUrl | None = None
    transcript_url: AnyUrl | None = None
    financial_metrics: FinancialMetrics | None = None
    document_sections: list[DocumentSection] = Field(default_factory=list, max_length=200)
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=100)
    include_markdown: bool = True
    purpose: Literal["earnings_review_not_investment_advice"] = (
        "earnings_review_not_investment_advice"
    )
    is_investment_advice: Literal[False] = False

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = str(value).upper().strip()
        if not re.fullmatch(r"[A-Z0-9.\-]{1,15}", normalized):
            raise ValueError("ticker must contain only letters, numbers, dots, or hyphens")
        return normalized

    @model_validator(mode="after")
    def validate_embedded_metrics(self) -> ReviewRequest:
        if self.financial_metrics is None:
            return self
        if self.financial_metrics.ticker != self.ticker:
            raise ValueError("financial_metrics.ticker must match request ticker")
        if self.financial_metrics.fiscal_period != self.fiscal_period:
            raise ValueError("financial_metrics.fiscal_period must match request fiscal_period")
        return self


class EvidenceItem(WorkflowModel):
    evidence_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    polarity: EvidencePolarity
    summary: str = Field(min_length=1, max_length=300)
    detail: str = Field(min_length=1, max_length=1200)
    impact_areas: list[ImpactArea] = Field(default_factory=lambda: [ImpactArea.OVERALL])
    source_ref: SourceRef
    metric_name: str | None = Field(default=None, max_length=120)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class StepStatus(WorkflowModel):
    step: WorkflowStep
    state: StepState
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = Field(default=None, max_length=500)
    error: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_state_details(self) -> StepStatus:
        if self.state == StepState.FAILED and not self.error:
            raise ValueError("failed step requires error")
        if self.finished_at is not None and self.started_at is not None:
            if self.finished_at < self.started_at:
                raise ValueError("finished_at must be greater than or equal to started_at")
        return self


class AgentResult(WorkflowModel):
    agent_role: AgentRole
    team: AgentTeam
    status: StepStatus
    headline: str = Field(min_length=1, max_length=300)
    conclusion: str = Field(min_length=1, max_length=1200)
    key_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=10)
    counter_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=10)
    open_questions: list[NonEmptyText] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentFinding(WorkflowModel):
    agent_name: str = Field(min_length=1, max_length=80)
    stance: Literal["positive", "negative", "mixed", "neutral", "unclear"]
    summary: str = Field(min_length=1, max_length=1200)
    key_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    counter_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_data: list[NonEmptyText] = Field(default_factory=list, max_length=8)
    handoff_summary: str = Field(min_length=1, max_length=2000)


class EPSQualityFinding(AgentFinding):
    agent_name: Literal["EPSQualityAnalyst"] = "EPSQualityAnalyst"


class ProfitabilityFinding(AgentFinding):
    agent_name: Literal["ProfitabilityAnalyst"] = "ProfitabilityAnalyst"


class CashFlowFcfFinding(AgentFinding):
    agent_name: Literal["CashFlowFcfAnalyst"] = "CashFlowFcfAnalyst"


class BalanceSheetRiskFinding(AgentFinding):
    agent_name: Literal["BalanceSheetRiskAnalyst"] = "BalanceSheetRiskAnalyst"


class ManagementIntentFinding(AgentFinding):
    agent_name: Literal["ManagementIntentAnalyst"] = "ManagementIntentAnalyst"


class GuidanceFinding(AgentFinding):
    agent_name: Literal["GuidanceAnalyst"] = "GuidanceAnalyst"


class AnalysisBrief(WorkflowModel):
    ticker: str = Field(min_length=1, max_length=15)
    fiscal_period: str = Field(pattern=r"^\d{4}Q[1-4]$")
    financial_agent_results: list[AgentResult] = Field(default_factory=list, max_length=8)
    presentation_agent_results: list[AgentResult] = Field(default_factory=list, max_length=8)
    positive_evidence_pool: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    negative_evidence_pool: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    risk_evidence_pool: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    synthesis: str = Field(min_length=1, max_length=2000)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = str(value).upper().strip()
        if not re.fullmatch(r"[A-Z0-9.\-]{1,15}", normalized):
            raise ValueError("ticker must contain only letters, numbers, dots, or hyphens")
        return normalized


class DebateResult(WorkflowModel):
    bull_case: str = Field(min_length=1, max_length=2000)
    bear_case: str = Field(min_length=1, max_length=2000)
    risk_case: str = Field(min_length=1, max_length=2000)
    evaluation: str = Field(min_length=1, max_length=2000)
    strongest_positive_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=10)
    strongest_negative_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=10)
    unresolved_questions: list[NonEmptyText] = Field(default_factory=list, max_length=8)


class BullCase(WorkflowModel):
    agent_name: Literal["bull_agent"] = "bull_agent"
    thesis: str = Field(min_length=1, max_length=2000)
    stance_strength: Literal["strong", "moderate", "weak"]
    strongest_positive_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    eps_bull_argument: str = Field(min_length=1, max_length=1200)
    fcf_bull_argument: str = Field(min_length=1, max_length=1200)
    conditions_needed: list[NonEmptyText] = Field(min_length=1, max_length=8)
    weak_points: list[NonEmptyText] = Field(min_length=1, max_length=8)
    disputed_points_to_watch: list[NonEmptyText] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_data: list[NonEmptyText] = Field(default_factory=list, max_length=8)


class BearCase(WorkflowModel):
    agent_name: Literal["bear_agent"] = "bear_agent"
    thesis: str = Field(min_length=1, max_length=2000)
    stance_strength: Literal["strong", "moderate", "weak"]
    strongest_negative_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    eps_bear_argument: str = Field(min_length=1, max_length=1200)
    fcf_bear_argument: str = Field(min_length=1, max_length=1200)
    failure_modes: list[NonEmptyText] = Field(min_length=1, max_length=8)
    counter_to_bull_case: list[NonEmptyText] = Field(min_length=1, max_length=8)
    unresolved_risks: list[NonEmptyText] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_data: list[NonEmptyText] = Field(default_factory=list, max_length=8)


class JudgeDecision(WorkflowModel):
    verdict: VerdictLabel
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1, max_length=1200)
    rationale: str = Field(min_length=1, max_length=2000)
    positive_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    negative_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    eps_outlook: str = Field(min_length=1, max_length=1200)
    fcf_outlook: str = Field(min_length=1, max_length=1200)
    purpose: Literal["earnings_review_not_investment_advice"] = (
        "earnings_review_not_investment_advice"
    )
    is_investment_advice: Literal[False] = False


class ReviewResponse(WorkflowModel):
    request_id: str | None = Field(default=None, max_length=80)
    ticker: str = Field(min_length=1, max_length=15)
    fiscal_period: str = Field(pattern=r"^\d{4}Q[1-4]$")
    steps: list[StepStatus] = Field(min_length=1, max_length=20)
    analysis_brief: AnalysisBrief
    debate_result: DebateResult
    judge_decision: JudgeDecision
    markdown_report: str = Field(min_length=1, max_length=20000)
    purpose: Literal["earnings_review_not_investment_advice"] = (
        "earnings_review_not_investment_advice"
    )
    is_investment_advice: Literal[False] = False
    disclaimer: str = Field(
        default="This report is an earnings analysis artifact and is not investment advice.",
        min_length=1,
        max_length=500,
    )

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = str(value).upper().strip()
        if not re.fullmatch(r"[A-Z0-9.\-]{1,15}", normalized):
            raise ValueError("ticker must contain only letters, numbers, dots, or hyphens")
        return normalized

    @model_validator(mode="after")
    def validate_nested_periods(self) -> ReviewResponse:
        if self.analysis_brief.ticker != self.ticker:
            raise ValueError("analysis_brief.ticker must match response ticker")
        if self.analysis_brief.fiscal_period != self.fiscal_period:
            raise ValueError("analysis_brief.fiscal_period must match response fiscal_period")
        return self

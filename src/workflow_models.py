"""API-first workflow contracts for earnings review.

These models define the boundary between workflow stages:
Data ingestion -> Financial Agents -> Presentation Agents ->
Evidence Aggregation -> Debate -> Judge -> MarkdownRenderer.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal, get_args

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
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


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


MetricStorePeriodRole = Literal[
    "reported_period_actuals",
    "consensus_for_reported_period",
    "guided_period",
    "consensus_for_guided_period",
    "prior_sequential_period_actuals",
    "prior_year_period",
]
CANONICAL_METRIC_STORE_PERIOD_ROLES = set(get_args(MetricStorePeriodRole))

TemporalPeriodRole = Literal[
    "reported_period_actuals",
    "consensus_for_reported_period",
    "guided_period",
    "consensus_for_guided_period",
    "prior_sequential_period_actuals",
    "prior_year_period",
    # Legacy temporal-snapshot/document roles retained for compatibility.
    "prior_period_actuals",
    "pre_earnings_consensus",
    "post_earnings_guidance",
    "latest_snapshot",
    "target_period_document",
]

SourceProvider = Literal["yfinance", "sec", "manual", "derived"]

SelectionMethod = Literal[
    "earnings_date_exact",
    "earnings_date_window",
    "period_end_exact",
    "provider_column_date_window",
    "latest_at_or_before_cutoff",
    "manual",
]


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
    EARNINGS_QUALITY = "earnings_quality"
    CASH_FLOW_RISK = "cash_flow_risk"
    MANAGEMENT_INTENT = "management_intent"
    GUIDANCE = "guidance"
    BULL = "bull"
    BEAR = "bear"
    JUDGE = "judge"

    EPS_ANALYST = "earnings_quality"
    PNL_ANALYST = "earnings_quality"
    CFS_ANALYST = "cash_flow_risk"
    BS_ANALYST = "cash_flow_risk"
    MANAGEMENT_EVAL = "management_intent"
    RISK = "bear"
    EVAL = "judge"


class AgentTeam(str, Enum):
    FINANCIAL = "financial"
    PRESENTATION = "presentation"
    DEBATE = "debate"
    JUDGE = "judge"


LEGACY_AGENT_ROLE_VALUES = {
    "eps_analyst": AgentRole.EARNINGS_QUALITY,
    "pnl_analyst": AgentRole.EARNINGS_QUALITY,
    "cfs_analyst": AgentRole.CASH_FLOW_RISK,
    "bs_analyst": AgentRole.CASH_FLOW_RISK,
    "management_eval": AgentRole.MANAGEMENT_INTENT,
    "risk": AgentRole.BEAR,
    "eval": AgentRole.JUDGE,
}


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
    fiscal_period: str | None = Field(default=None, pattern=r"^\d{4}Q[1-4]$")
    period_role: TemporalPeriodRole | None = None
    published_date: date | None = None
    data_cutoff_date: date | None = None

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
    fiscal_period: str | None = Field(default=None, pattern=r"^\d{4}Q[1-4]$")
    published_date: date | None = None
    period_role: TemporalPeriodRole | None = None

    @model_validator(mode="after")
    def validate_pages(self) -> DocumentSection:
        if self.end_page is not None:
            if self.start_page is None:
                raise ValueError("end_page requires start_page")
            if self.end_page < self.start_page:
                raise ValueError("end_page must be greater than or equal to start_page")
        return self


class DocumentFile(WorkflowModel):
    path: str = Field(min_length=1, max_length=500)
    source_type: SourceType = SourceType.MANUAL_UPLOAD
    document_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    title: str = Field(min_length=1, max_length=300)
    fiscal_period: str | None = Field(default=None, pattern=r"^\d{4}Q[1-4]$")
    published_date: date | None = None
    period_role: Literal["target_period_document"] | None = None


class RawMetricBase(WorkflowModel):
    raw_key: str = Field(min_length=1, max_length=200)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    period: str | None = Field(default=None, max_length=40)
    source: str = Field(min_length=1, max_length=40)
    axis: str | None = Field(default=None, max_length=200)
    member: str | None = Field(default=None, max_length=200)
    scope: Literal["consolidated", "segment", "dimensional"] = "consolidated"


class NormalizedMetric(RawMetricBase):
    canonical_key: Literal[
        "revenue",
        "eps_basic",
        "eps_diluted",
        "operating_income",
        "operating_margin",
        "operating_cash_flow",
        "capex",
        "free_cash_flow",
    ]


class UnmappedMetric(RawMetricBase):
    reason: str | None = Field(default=None, max_length=200)


class MetricStoreEntry(WorkflowModel):
    metric_name: str = Field(min_length=1, max_length=120)
    value: float | NonEmptyText
    unit: str = Field(min_length=1, max_length=40)
    source_type: SourceType
    source_name: str = Field(min_length=1, max_length=200)
    fiscal_period: str = Field(pattern=r"^\d{4}Q[1-4]$")
    period_role: MetricStorePeriodRole
    source_ref: SourceRef

    @model_validator(mode="after")
    def validate_source_ref_alignment(self) -> MetricStoreEntry:
        if self.source_ref.source_type != self.source_type:
            raise ValueError("source_ref.source_type must match source_type")
        if not self.source_ref.metric_name:
            raise ValueError("source_ref.metric_name is required for metric_store")
        if not self.source_ref.fiscal_period:
            raise ValueError("source_ref.fiscal_period is required for metric_store")
        if not self.source_ref.period_role:
            raise ValueError("source_ref.period_role is required for metric_store")
        if self.source_ref.metric_name != self.metric_name:
            raise ValueError("source_ref.metric_name must match metric_name")
        if self.source_ref.fiscal_period != self.fiscal_period:
            raise ValueError("source_ref.fiscal_period must match fiscal_period")
        if self.source_ref.period_role != self.period_role:
            raise ValueError("source_ref.period_role must match period_role")
        return self


class PresentationMetricHint(WorkflowModel):
    metric_name: str = Field(min_length=1, max_length=120)
    raw_text: str = Field(min_length=1, max_length=500)
    raw_value: str | None = Field(default=None, max_length=80)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    fiscal_period: str | None = Field(default=None, pattern=r"^\d{4}Q[1-4]$")
    period_role: MetricStorePeriodRole | None = None
    source_type: SourceType
    source_name: str = Field(min_length=1, max_length=200)
    source_ref: SourceRef
    extraction_method: str = Field(min_length=1, max_length=80)
    hint_status: Literal["parsed", "ambiguous", "rejected", "promoted"]
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_source_ref_alignment(self) -> PresentationMetricHint:
        if self.source_ref.source_type != self.source_type:
            raise ValueError("source_ref.source_type must match source_type")
        if (
            self.source_ref.period_role is not None
            and self.source_ref.period_role not in CANONICAL_METRIC_STORE_PERIOD_ROLES
        ):
            raise ValueError(
                "source_ref.period_role must be canonical for presentation_metric_hints"
            )
        if self.source_ref.metric_name and self.source_ref.metric_name != self.metric_name:
            raise ValueError("source_ref.metric_name must match metric_name when present")
        if self.source_ref.fiscal_period is not None and self.fiscal_period is None:
            raise ValueError("source_ref.fiscal_period requires fiscal_period")
        if self.source_ref.period_role is not None and self.period_role is None:
            raise ValueError("source_ref.period_role requires period_role")
        if (
            self.fiscal_period is not None
            and self.source_ref.fiscal_period is not None
            and self.source_ref.fiscal_period != self.fiscal_period
        ):
            raise ValueError("source_ref.fiscal_period must match fiscal_period when present")
        if (
            self.period_role is not None
            and self.source_ref.period_role is not None
            and self.source_ref.period_role != self.period_role
        ):
            raise ValueError("source_ref.period_role must match period_role when present")
        return self


class FinancialMetrics(WorkflowModel):
    ticker: str = Field(min_length=1, max_length=15)
    fiscal_period: str = Field(pattern=r"^\d{4}Q[1-4]$")
    period_end_date: date | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    period_role: TemporalPeriodRole = "reported_period_actuals"
    earnings_date: date | None = None
    source_provider: SourceProvider | None = None
    source_row_date: date | None = None
    source_table_column_date: date | None = None
    data_cutoff_date: date | None = None
    selection_method: SelectionMethod | None = None

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
    metric_store: list[MetricStoreEntry] = Field(default_factory=list, max_length=100)
    presentation_metric_hints: list[PresentationMetricHint] = Field(
        default_factory=list,
        max_length=200,
    )
    segment_metrics: list[NormalizedMetric] = Field(default_factory=list, max_length=500)
    unmapped_metrics: list[UnmappedMetric] = Field(default_factory=list, max_length=500)
    temporal_snapshots: dict[str, dict] = Field(default_factory=dict, max_length=10)
    warnings: list[str] = Field(default_factory=list, max_length=50)

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
    target_earnings_date: date | None = None
    target_period_end_date: date | None = None
    prior_fiscal_period: str | None = Field(default=None, pattern=r"^\d{4}Q[1-4]$")
    financial_data_as_of: date | None = None
    document_period_policy: Literal["target_only"] = "target_only"
    financial_period_policy: Literal["target_plus_prior"] = "target_plus_prior"
    filing_url: AnyUrl | None = None
    presentation_url: AnyUrl | None = None
    transcript_url: AnyUrl | None = None
    financial_metrics: FinancialMetrics | None = None
    document_files: list[DocumentFile] = Field(default_factory=list, max_length=20)
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
    def validate_temporal_contract(self) -> ReviewRequest:
        if self.prior_fiscal_period is not None:
            expected_prior = self._prior_sequential_period(self.fiscal_period)
            if self.prior_fiscal_period != expected_prior:
                raise ValueError(
                    "prior_fiscal_period must be the immediately preceding fiscal quarter"
                )

        if self.financial_metrics is None:
            if self.target_earnings_date is None:
                raise ValueError(
                    "target_earnings_date is required when financial_metrics is absent"
                )
        else:
            if self.financial_metrics.ticker != self.ticker:
                raise ValueError("financial_metrics.ticker must match request ticker")
            if self.financial_metrics.fiscal_period != self.fiscal_period:
                raise ValueError("financial_metrics.fiscal_period must match request fiscal_period")
            if self.financial_metrics.period_role != "reported_period_actuals":
                raise ValueError("financial_metrics.period_role must be reported_period_actuals")
            for source_ref in self.financial_metrics.source_refs:
                if source_ref.period_role == "latest_snapshot":
                    raise ValueError("financial_metrics source_refs cannot be latest_snapshot")
                if source_ref.period_role in {
                    "pre_earnings_consensus",
                    "post_earnings_guidance",
                    "prior_period_actuals",
                }:
                    raise ValueError(
                        "financial_metrics source_refs cannot use legacy temporal period_role"
                    )
            if self._contains_latest_snapshot(self.financial_metrics.temporal_snapshots):
                raise ValueError(
                    "financial_metrics temporal_snapshots cannot include latest_snapshot"
                )
            self._validate_supplied_metric_dates()
            self._validate_metric_store_period_roles()

        if self.document_period_policy == "target_only":
            for document_file in self.document_files:
                if self.target_earnings_date is not None and document_file.fiscal_period is None:
                    raise ValueError(
                        "document_files fiscal_period is required with target_earnings_date"
                    )
                if (
                    document_file.fiscal_period is not None
                    and document_file.fiscal_period != self.fiscal_period
                ):
                    raise ValueError(
                        "document_files fiscal_period must match request fiscal_period"
                    )
                if self.target_earnings_date is not None and document_file.period_role is None:
                    raise ValueError(
                        "document_files period_role is required with target_earnings_date"
                    )
                if (
                    document_file.period_role is not None
                    and document_file.period_role != "target_period_document"
                ):
                    raise ValueError("document_files period_role must be target_period_document")
                if (
                    document_file.published_date is not None
                    and self.target_earnings_date is not None
                    and document_file.published_date > self.target_earnings_date
                ):
                    raise ValueError(
                        "document_files published_date cannot be after target_earnings_date"
                    )
            for section in self.document_sections:
                self._validate_target_section_source(section)
        if (
            self.financial_data_as_of is not None
            and self.target_earnings_date is not None
            and self.financial_data_as_of < self.target_earnings_date
        ):
            raise ValueError("financial_data_as_of cannot be before target_earnings_date")
        return self

    def _contains_latest_snapshot(self, value) -> bool:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key == "latest_snapshot" or nested == "latest_snapshot":
                    return True
                if self._contains_latest_snapshot(nested):
                    return True
        elif isinstance(value, list):
            return any(self._contains_latest_snapshot(item) for item in value)
        return value == "latest_snapshot"

    def _validate_supplied_metric_dates(self) -> None:
        if self.financial_metrics is None:
            return
        metrics = self.financial_metrics
        if self.target_earnings_date is None and (
            metrics.earnings_date is not None or metrics.source_row_date is not None
        ):
            raise ValueError(
                "target_earnings_date is required when financial_metrics include provider row dates"
            )
        if self.target_period_end_date is None and (
            metrics.period_end_date is not None or metrics.source_table_column_date is not None
        ):
            raise ValueError(
                "target_period_end_date is required when financial_metrics include provider table dates"
            )
        if (
            self.target_earnings_date is not None
            and metrics.earnings_date is not None
            and metrics.earnings_date != self.target_earnings_date
        ):
            raise ValueError("financial_metrics.earnings_date must match target_earnings_date")
        if (
            self.target_earnings_date is not None
            and metrics.source_row_date is not None
            and metrics.source_row_date != self.target_earnings_date
        ):
            raise ValueError("financial_metrics.source_row_date must match target_earnings_date")
        if (
            self.target_period_end_date is not None
            and metrics.period_end_date is not None
            and metrics.period_end_date != self.target_period_end_date
        ):
            raise ValueError("financial_metrics.period_end_date must match target_period_end_date")
        if (
            self.target_period_end_date is not None
            and metrics.source_table_column_date is not None
            and abs((metrics.source_table_column_date - self.target_period_end_date).days) > 7
        ):
            raise ValueError(
                "financial_metrics.source_table_column_date must match target_period_end_date window"
            )
        if (
            self.financial_data_as_of is not None
            and metrics.data_cutoff_date is not None
            and self.target_earnings_date is not None
            and metrics.data_cutoff_date < self.target_earnings_date
        ):
            raise ValueError("financial_metrics.data_cutoff_date cannot precede target earnings")

    def _validate_target_section_source(self, section: DocumentSection) -> None:
        fiscal_period = section.fiscal_period or section.source_ref.fiscal_period
        period_role = section.period_role or section.source_ref.period_role
        if fiscal_period is not None and fiscal_period != self.fiscal_period:
            raise ValueError("document_sections fiscal_period must match request fiscal_period")
        if period_role is not None and period_role != "target_period_document":
            raise ValueError("document_sections period_role must be target_period_document")
        if self.target_earnings_date is not None and fiscal_period is None:
            raise ValueError(
                "document_sections fiscal_period is required with target_earnings_date"
            )
        published_date = section.published_date or section.source_ref.published_date
        if (
            published_date is not None
            and self.target_earnings_date is not None
            and published_date > self.target_earnings_date
        ):
            raise ValueError(
                "document_sections published_date cannot be after target_earnings_date"
            )

    def _validate_metric_store_period_roles(self) -> None:
        if self.financial_metrics is None:
            return
        for entry in self.financial_metrics.metric_store:
            if entry.period_role == "prior_year_period":
                expected = self._prior_year_period(self.fiscal_period)
                if entry.fiscal_period != expected:
                    raise ValueError(
                        "prior_year_period metric_store entries must use the same quarter in the prior fiscal year"
                    )
            if entry.period_role == "prior_sequential_period_actuals":
                expected = self._prior_sequential_period(self.fiscal_period)
                if entry.fiscal_period != expected:
                    raise ValueError(
                        "prior_sequential_period_actuals metric_store entries must use the immediately preceding fiscal quarter"
                    )

    def _prior_year_period(self, fiscal_period: str) -> str:
        year = int(fiscal_period[:4]) - 1
        quarter = fiscal_period[-2:]
        return f"{year}{quarter}"

    def _prior_sequential_period(self, fiscal_period: str) -> str:
        year = int(fiscal_period[:4])
        quarter = int(fiscal_period[-1])
        if quarter == 1:
            return f"{year - 1}Q4"
        return f"{year}Q{quarter - 1}"


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

    @field_validator("agent_role", mode="before")
    @classmethod
    def normalize_legacy_agent_role(cls, value: AgentRole | str) -> AgentRole | str:
        if isinstance(value, str):
            return LEGACY_AGENT_ROLE_VALUES.get(value, value)
        return value


class AgentFinding(WorkflowModel):
    agent_name: str = Field(min_length=1, max_length=80)
    stance: Literal["positive", "negative", "mixed", "neutral", "unclear"]
    summary: str = Field(min_length=1, max_length=1200)
    key_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    counter_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_data: list[NonEmptyText] = Field(default_factory=list, max_length=8)
    handoff_summary: str = Field(min_length=1, max_length=2000)


class EarningsQualityFinding(AgentFinding):
    agent_name: Literal[
        "EarningsQualityAnalyst",
        "EPSQualityAnalyst",
        "ProfitabilityAnalyst",
    ] = "EarningsQualityAnalyst"


class CashFlowRiskFinding(AgentFinding):
    agent_name: Literal[
        "CashFlowRiskAnalyst",
        "CashFlowFcfAnalyst",
        "BalanceSheetRiskAnalyst",
    ] = "CashFlowRiskAnalyst"


class ManagementIntentFinding(AgentFinding):
    agent_name: Literal["ManagementIntentAnalyst"] = "ManagementIntentAnalyst"


class GuidanceFinding(AgentFinding):
    agent_name: Literal["GuidanceAnalyst"] = "GuidanceAnalyst"
    key_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=10)
    counter_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=10)
    guidance_status: Literal["found", "not_disclosed", "ambiguous", "not_found"] | None = None


class EPSQualityFinding(EarningsQualityFinding):
    agent_name: Literal["EarningsQualityAnalyst", "EPSQualityAnalyst"] = "EarningsQualityAnalyst"


class ProfitabilityFinding(EarningsQualityFinding):
    agent_name: Literal["EarningsQualityAnalyst", "ProfitabilityAnalyst"] = "EarningsQualityAnalyst"


class CashFlowFcfFinding(CashFlowRiskFinding):
    agent_name: Literal["CashFlowRiskAnalyst", "CashFlowFcfAnalyst"] = "CashFlowRiskAnalyst"


class BalanceSheetRiskFinding(CashFlowRiskFinding):
    agent_name: Literal["CashFlowRiskAnalyst", "BalanceSheetRiskAnalyst"] = "CashFlowRiskAnalyst"


class FindingCoverage(str, Enum):
    SUPPORTING = "supporting"
    OPPOSING = "opposing"
    NOT_MATERIAL = "not_material"
    MISSING = "missing"


FindingCoverageKey = Literal[
    "earnings_quality",
    "cash_flow_risk",
    "management_intent",
    "guidance",
]
FindingCoverageMap = dict[FindingCoverageKey, FindingCoverage]
REQUIRED_FINDING_COVERAGE_KEYS = frozenset(
    {"earnings_quality", "cash_flow_risk", "management_intent", "guidance"}
)


def validate_finding_coverage_keys(coverage: FindingCoverageMap) -> FindingCoverageMap:
    keys = set(coverage)
    missing = REQUIRED_FINDING_COVERAGE_KEYS - keys
    extra = keys - REQUIRED_FINDING_COVERAGE_KEYS
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing keys: {', '.join(sorted(missing))}")
        if extra:
            details.append(f"unexpected keys: {', '.join(sorted(extra))}")
        message = "finding_coverage must include exactly the four specialist keys"
        raise ValueError(f"{message}; {'; '.join(details)}")
    return coverage


class AnalysisBrief(WorkflowModel):
    ticker: str = Field(min_length=1, max_length=15)
    fiscal_period: str = Field(pattern=r"^\d{4}Q[1-4]$")
    earnings_quality_finding: EarningsQualityFinding
    cash_flow_risk_finding: CashFlowRiskFinding
    management_intent_finding: ManagementIntentFinding
    guidance_finding: GuidanceFinding
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
    finding_coverage: FindingCoverageMap = Field(min_length=4, max_length=4)
    disputed_points_to_watch: list[NonEmptyText] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_data: list[NonEmptyText] = Field(default_factory=list, max_length=8)

    @field_validator("finding_coverage")
    @classmethod
    def validate_finding_coverage(cls, value: FindingCoverageMap) -> FindingCoverageMap:
        return validate_finding_coverage_keys(value)


class BearCase(WorkflowModel):
    agent_name: Literal["bear_agent"] = "bear_agent"
    thesis: str = Field(min_length=1, max_length=2000)
    stance_strength: Literal["strong", "moderate", "weak"]
    strongest_negative_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    eps_bear_argument: str = Field(min_length=1, max_length=1200)
    fcf_bear_argument: str = Field(min_length=1, max_length=1200)
    failure_modes: list[NonEmptyText] = Field(min_length=1, max_length=8)
    counter_to_bull_case: list[NonEmptyText] = Field(min_length=1, max_length=8)
    finding_coverage: FindingCoverageMap = Field(min_length=4, max_length=4)
    unresolved_risks: list[NonEmptyText] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_data: list[NonEmptyText] = Field(default_factory=list, max_length=8)

    @field_validator("finding_coverage")
    @classmethod
    def validate_finding_coverage(cls, value: FindingCoverageMap) -> FindingCoverageMap:
        return validate_finding_coverage_keys(value)


class JudgeDecision(WorkflowModel):
    verdict: VerdictLabel
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1, max_length=1200)
    rationale: str = Field(min_length=1, max_length=2000)
    positive_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    negative_evidence: list[EvidenceItem] = Field(min_length=1, max_length=10)
    eps_outlook: str = Field(min_length=1, max_length=1200)
    eps_outlook_reason: str = Field(min_length=1, max_length=2000)
    fcf_outlook: str = Field(min_length=1, max_length=1200)
    fcf_outlook_reason: str = Field(min_length=1, max_length=2000)
    purpose: Literal["earnings_review_not_investment_advice"] = (
        "earnings_review_not_investment_advice"
    )
    is_investment_advice: Literal[False] = False


FinalVerdict = JudgeDecision


class ReviewResponse(WorkflowModel):
    request_id: str | None = Field(default=None, max_length=80)
    ticker: str = Field(min_length=1, max_length=15)
    fiscal_period: str = Field(pattern=r"^\d{4}Q[1-4]$")
    steps: list[StepStatus] = Field(min_length=1, max_length=20)
    analysis_brief: AnalysisBrief
    bull_case: BullCase
    bear_case: BearCase
    debate_result: DebateResult
    judge_decision: JudgeDecision
    markdown_report: str = Field(min_length=1, max_length=60000)
    warnings: list[NonEmptyText] = Field(default_factory=list, max_length=50)
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

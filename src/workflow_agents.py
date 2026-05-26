"""API-first workflow agent wrappers.

This module owns the LLM call boundary for the earnings-review workflow:
agents receive a small routed context, call ``LLMProvider.complete()``, and
return Pydantic-validated JSON objects.

``src.workflow_models`` is expected to become the canonical contract module.
Until then, fallback models below keep this wrapper testable and make the
future import surface explicit.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .llm import LLMProvider
from .structured import parse_model


class WorkflowAgentError(RuntimeError):
    """Base exception for workflow agent failures."""


class AgentRoleMismatch(WorkflowAgentError):
    """Raised when validated JSON belongs to a different agent role."""


class AgentOutputValidationError(WorkflowAgentError):
    """Raised when the LLM output cannot be parsed into the output contract."""


class _FallbackContract(BaseModel):
    """Temporary permissive base until src.workflow_models lands.

    The future workflow models should be stricter and can be wired by exporting
    the class names used in the import fallback block below.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)


class EvidenceItem(_FallbackContract):
    source_ref: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_type: str | None = None
    metric: str | None = None
    period: str | None = None


class _FallbackFinding(_FallbackContract):
    agent_name: str = Field(min_length=1)
    stance: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    key_evidence: list[EvidenceItem] = Field(default_factory=list)
    counter_evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_data: list[str] = Field(default_factory=list)
    handoff_summary: str = Field(default="", max_length=2000)


class _FallbackEPSQualityFinding(_FallbackFinding):
    pass


class _FallbackProfitabilityFinding(_FallbackFinding):
    pass


class _FallbackCashFlowFcfFinding(_FallbackFinding):
    pass


class _FallbackBalanceSheetRiskFinding(_FallbackFinding):
    pass


class _FallbackManagementIntentFinding(_FallbackFinding):
    pass


class _FallbackGuidanceFinding(_FallbackFinding):
    pass


class _FallbackBullCase(_FallbackContract):
    agent_name: str = Field(min_length=1)
    thesis: str = Field(min_length=1)
    stance_strength: str = Field(min_length=1)
    strongest_positive_evidence: list[EvidenceItem] = Field(default_factory=list)
    eps_bull_argument: str = Field(default="")
    fcf_bull_argument: str = Field(default="")
    conditions_needed: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    disputed_points_to_watch: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_data: list[str] = Field(default_factory=list)


class _FallbackBearCase(_FallbackContract):
    agent_name: str = Field(min_length=1)
    thesis: str = Field(min_length=1)
    stance_strength: str = Field(min_length=1)
    strongest_negative_evidence: list[EvidenceItem] = Field(default_factory=list)
    eps_bear_argument: str = Field(default="")
    fcf_bear_argument: str = Field(default="")
    failure_modes: list[str] = Field(default_factory=list)
    counter_to_bull_case: list[str] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_data: list[str] = Field(default_factory=list)


class _FallbackJudgeDecision(_FallbackContract):
    agent_name: str = Field(min_length=1)
    label: str = Field(pattern=r"^(good|neutral|bad)$")
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    positive_evidence: list[EvidenceItem] = Field(default_factory=list)
    negative_evidence: list[EvidenceItem] = Field(default_factory=list)
    eps_outlook: str = Field(min_length=1)
    eps_outlook_reason: str = Field(min_length=1)
    fcf_outlook: str = Field(min_length=1)
    fcf_outlook_reason: str = Field(min_length=1)
    key_disputed_points: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    non_advice_disclaimer: str = Field(min_length=1)


try:  # pragma: no cover - exercised once src.workflow_models exists.
    from . import workflow_models as _workflow_models
except ImportError:  # pragma: no cover - current repository state.
    _workflow_models = None


EPSQualityFinding = getattr(
    _workflow_models, "EPSQualityFinding", _FallbackEPSQualityFinding
)
ProfitabilityFinding = getattr(
    _workflow_models, "ProfitabilityFinding", _FallbackProfitabilityFinding
)
CashFlowFcfFinding = getattr(
    _workflow_models, "CashFlowFcfFinding", _FallbackCashFlowFcfFinding
)
BalanceSheetRiskFinding = getattr(
    _workflow_models, "BalanceSheetRiskFinding", _FallbackBalanceSheetRiskFinding
)
ManagementIntentFinding = getattr(
    _workflow_models, "ManagementIntentFinding", _FallbackManagementIntentFinding
)
GuidanceFinding = getattr(_workflow_models, "GuidanceFinding", _FallbackGuidanceFinding)
BullCase = getattr(_workflow_models, "BullCase", _FallbackBullCase)
BearCase = getattr(_workflow_models, "BearCase", _FallbackBearCase)
JudgeDecision = getattr(
    _workflow_models,
    "JudgeDecision",
    getattr(_workflow_models, "FinalVerdict", _FallbackJudgeDecision),
)


JsonModel = type[BaseModel]


@dataclass(frozen=True)
class AgentSpec:
    public_role: str
    output_agent_name: str
    output_model: JsonModel
    context_keys: tuple[str, ...]
    system_prompt: str
    task_prompt: str
    role_aliases: tuple[str, ...] = ()
    max_tokens: int = 1600
    temperature: float = 0.2

    @property
    def accepted_role_values(self) -> tuple[str, ...]:
        return (self.output_agent_name, self.public_role, *self.role_aliases)


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _to_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )


def _model_schema(model_type: JsonModel) -> dict[str, Any]:
    if hasattr(model_type, "model_json_schema"):
        return model_type.model_json_schema()
    return {"title": getattr(model_type, "__name__", str(model_type))}


def _extract_role(value: BaseModel) -> str | None:
    for field_name in ("agent_name", "role", "agent_role"):
        if hasattr(value, field_name):
            role = getattr(value, field_name)
            if role is None:
                return None
            enum_value = getattr(role, "value", None)
            return str(enum_value if enum_value is not None else role)
    return None


class WorkflowAgent:
    """Small LLM wrapper for one specialist role."""

    spec: AgentSpec

    def __init__(self, llm: LLMProvider, *, max_retries: int = 1):
        self.llm = llm
        self.max_retries = max(0, max_retries)

    def __call__(self, **context: Any) -> BaseModel:
        return self.run(context)

    def run(self, context: Mapping[str, Any] | None = None, **kwargs: Any) -> BaseModel:
        merged: dict[str, Any] = {}
        if context:
            merged.update(context)
        merged.update(kwargs)
        routed_context = self._select_context(merged)
        user_prompt = self._build_user_prompt(routed_context)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            prompt = (
                user_prompt
                if attempt == 0
                else self._repair_prompt(user_prompt, last_error)
            )
            response = self.llm.complete(
                system=self.spec.system_prompt,
                user=prompt,
                max_tokens=self.spec.max_tokens,
                temperature=self.spec.temperature,
            )
            text = getattr(response, "text", response)
            try:
                parsed = parse_model(self.spec.output_model, str(text))
                self._validate_role(parsed)
                return parsed
            except Exception as exc:  # noqa: BLE001 - wrap Pydantic/JSON/mismatch uniformly.
                last_error = exc

        if isinstance(last_error, AgentRoleMismatch):
            raise last_error

        raise AgentOutputValidationError(
            f"{self.spec.public_role} failed to produce valid JSON for "
            f"{self.spec.output_model.__name__}: {last_error}"
        ) from last_error

    def _select_context(self, context: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: context[key]
            for key in self.spec.context_keys
            if key in context and context[key] is not None
        }

    def _build_user_prompt(self, routed_context: Mapping[str, Any]) -> str:
        schema = _model_schema(self.spec.output_model)
        return (
            f"{self.spec.task_prompt}\n\n"
            "制約:\n"
            "- 入力された routed_context だけを使う。\n"
            "- 財務指標を自分で計算しない。\n"
            "- 株価予測、目標株価、売買推奨を書かない。\n"
            "- JSONのみを返す。Markdownや前置きは禁止。\n"
            f"- role field がある場合は {self.spec.output_agent_name!r} を入れる。\n\n"
            "# routed_context\n"
            f"{_to_json(routed_context)}\n\n"
            "# expected_output_schema\n"
            f"{_to_json(schema)}"
        )

    def _repair_prompt(self, original_prompt: str, error: Exception | None) -> str:
        return (
            f"{original_prompt}\n\n"
            "# previous_output_error\n"
            f"{type(error).__name__}: {error}\n\n"
            "上のエラーを修正し、同じschemaに合うJSONのみを返してください。"
        )

    def _validate_role(self, output: BaseModel) -> None:
        actual = _extract_role(output)
        if actual is None:
            return
        if actual not in self.spec.accepted_role_values:
            expected = ", ".join(repr(v) for v in self.spec.accepted_role_values)
            raise AgentRoleMismatch(
                f"{self.spec.public_role} expected role {expected}, got {actual!r}"
            )


def _system(role: str, scope: str) -> str:
    return (
        f"あなたは米国株四半期決算レビューworkflowの {role} です。\n"
        f"責務: {scope}\n"
        "必要最小限のcontextだけを使い、計算済みデータと根拠文書から解釈する。\n"
        "入力にない事実、外部知識、投資助言、株価予測、目標株価は禁止。\n"
        "出力は必ずJSONのみ。"
    )


class EPSQualityAnalyst(WorkflowAgent):
    spec = AgentSpec(
        public_role="EPSQualityAnalyst",
        output_agent_name="EPSQualityAnalyst",
        output_model=EPSQualityFinding,
        context_keys=(
            "run_spec",
            "eps_metrics",
            "profitability_metrics",
            "eps_sections",
            "source_index",
            "analysis_config",
        ),
        system_prompt=_system(
            "EPSQualityAnalyst",
            "EPS surpriseの質、一時要因と継続要因、将来EPSへの示唆を分析する。",
        ),
        task_prompt="EPSQualityFinding JSONを作成してください。",
        role_aliases=("eps_analyst",),
    )


class ProfitabilityAnalyst(WorkflowAgent):
    spec = AgentSpec(
        public_role="ProfitabilityAnalyst",
        output_agent_name="ProfitabilityAnalyst",
        output_model=ProfitabilityFinding,
        context_keys=(
            "run_spec",
            "profitability_metrics",
            "revenue_metrics",
            "margin_metrics",
            "profitability_sections",
            "segment_sections",
            "source_index",
            "analysis_config",
        ),
        system_prompt=_system(
            "ProfitabilityAnalyst",
            "売上品質、粗利率、営業利益率、営業レバレッジ、segment mixを分析する。",
        ),
        task_prompt="ProfitabilityFinding JSONを作成してください。",
        role_aliases=("pnl_analyst",),
    )


class CashFlowFcfAnalyst(WorkflowAgent):
    spec = AgentSpec(
        public_role="CashFlowFcfAnalyst",
        output_agent_name="CashFlowFcfAnalyst",
        output_model=CashFlowFcfFinding,
        context_keys=(
            "run_spec",
            "cash_flow_metrics",
            "fcf_metrics",
            "capex_metrics",
            "working_capital_metrics",
            "cash_flow_sections",
            "capex_sections",
            "source_index",
            "analysis_config",
        ),
        system_prompt=_system(
            "CashFlowFcfAnalyst",
            "営業CF、FCF、CapEx、運転資本が将来FCFへ与える影響を分析する。",
        ),
        task_prompt="CashFlowFcfFinding JSONを作成してください。",
        role_aliases=("cfs_analyst",),
    )


class BalanceSheetRiskAnalyst(WorkflowAgent):
    spec = AgentSpec(
        public_role="BalanceSheetRiskAnalyst",
        output_agent_name="BalanceSheetRiskAnalyst",
        output_model=BalanceSheetRiskFinding,
        context_keys=(
            "run_spec",
            "balance_sheet_metrics",
            "debt_liquidity_metrics",
            "balance_sheet_sections",
            "risk_sections",
            "source_index",
            "analysis_config",
        ),
        system_prompt=_system(
            "BalanceSheetRiskAnalyst",
            "BSの健全性、流動性、負債水準、財務制約リスクを分析する。",
        ),
        task_prompt="BalanceSheetRiskFinding JSONを作成してください。",
        role_aliases=("bs_analyst",),
    )


class ManagementIntentAnalyst(WorkflowAgent):
    spec = AgentSpec(
        public_role="ManagementIntentAnalyst",
        output_agent_name="ManagementIntentAnalyst",
        output_model=ManagementIntentFinding,
        context_keys=(
            "run_spec",
            "financial_snapshot_minimal",
            "management_sections",
            "mdna_sections",
            "risk_sections",
            "source_index",
        ),
        system_prompt=_system(
            "ManagementIntentAnalyst",
            "経営陣の意図、優先順位、投資判断、EPS/FCFへの時間軸別示唆を分析する。",
        ),
        task_prompt="ManagementIntentFinding JSONを作成してください。",
        role_aliases=("management_eval",),
    )


class GuidanceAnalyst(WorkflowAgent):
    spec = AgentSpec(
        public_role="GuidanceAnalyst",
        output_agent_name="GuidanceAnalyst",
        output_model=GuidanceFinding,
        context_keys=(
            "run_spec",
            "guidance_sections",
            "consensus_deltas",
            "guidance_assumptions_sections",
            "prior_guidance_track_record",
            "management_intent_handoff",
            "source_index",
            "analysis_config",
        ),
        system_prompt=_system(
            "GuidanceAnalyst",
            "guidanceとprecomputed consensus差分、前提、達成可能性、revision riskを分析する。",
        ),
        task_prompt="GuidanceFinding JSONを作成してください。",
        role_aliases=("guidance",),
    )


class BullAgent(WorkflowAgent):
    spec = AgentSpec(
        public_role="BullAgent",
        output_agent_name="bull_agent",
        output_model=BullCase,
        context_keys=(
            "run_spec",
            "financial_snapshot_summary",
            "analysis_brief",
            "positive_evidence_pool",
            "negative_evidence_pool",
            "disputed_points",
            "missing_data",
        ),
        system_prompt=_system(
            "BullAgent",
            "validated AnalysisBriefだけからgoodと評価できる最も強いcaseを作る。",
        ),
        task_prompt="BullCase JSONを作成してください。",
        role_aliases=("BullAgent", "bull"),
        max_tokens=1400,
    )


class BearAgent(WorkflowAgent):
    spec = AgentSpec(
        public_role="BearAgent",
        output_agent_name="bear_agent",
        output_model=BearCase,
        context_keys=(
            "run_spec",
            "analysis_brief",
            "bull_case_summary",
            "positive_evidence_pool",
            "negative_evidence_pool",
            "disputed_points",
            "missing_data",
        ),
        system_prompt=_system(
            "BearAgent",
            "validated AnalysisBriefと必要ならBullCaseSummaryからdownside/neutral caseを作る。",
        ),
        task_prompt="BearCase JSONを作成してください。",
        role_aliases=("BearAgent", "bear"),
        max_tokens=1400,
    )


class JudgeAgent(WorkflowAgent):
    spec = AgentSpec(
        public_role="JudgeAgent",
        output_agent_name="judge_agent",
        output_model=JudgeDecision,
        context_keys=(
            "run_spec",
            "financial_snapshot_summary",
            "analysis_brief",
            "bull_case",
            "bear_case",
        ),
        system_prompt=_system(
            "JudgeAgent",
            "validated AnalysisBrief、BullCase、BearCaseを比較しgood/neutral/badを判定する。",
        ),
        task_prompt="JudgeDecision JSONを作成してください。",
        role_aliases=("JudgeAgent", "judge"),
        max_tokens=1400,
        temperature=0.1,
    )


SPECIALIST_AGENT_CLASSES: tuple[type[WorkflowAgent], ...] = (
    EPSQualityAnalyst,
    ProfitabilityAnalyst,
    CashFlowFcfAnalyst,
    BalanceSheetRiskAnalyst,
    ManagementIntentAnalyst,
    GuidanceAnalyst,
)

DEBATE_AGENT_CLASSES: tuple[type[WorkflowAgent], ...] = (BullAgent, BearAgent)

ALL_WORKFLOW_AGENT_CLASSES: tuple[type[WorkflowAgent], ...] = (
    *SPECIALIST_AGENT_CLASSES,
    *DEBATE_AGENT_CLASSES,
    JudgeAgent,
)


def build_default_agents(llm: LLMProvider) -> dict[str, WorkflowAgent]:
    """Create one wrapper per workflow role, keyed by public role name."""

    return {agent_cls.spec.public_role: agent_cls(llm) for agent_cls in ALL_WORKFLOW_AGENT_CLASSES}

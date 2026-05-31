"""API-first workflow agent wrappers.

This module owns the LLM call boundary for the earnings-review workflow:
agents receive a small routed context, call ``LLMProvider.complete()``, and
return Pydantic-validated JSON objects.

``src.workflow_models`` is the canonical contract module.  This wrapper keeps a
small compatibility bridge for Plan/active models that may not have landed in
``workflow_models`` yet, but runtime agent specs always point at strict
workflow contracts rather than permissive ad-hoc fallback models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from pydantic import BaseModel, field_validator

from . import workflow_models as _workflow_models
from .llm import LLMProvider
from .prompt_loader import build_system_prompt, resolve_skill_target
from .structured import parse_model


class WorkflowAgentError(RuntimeError):
    """Base exception for workflow agent failures."""


class AgentRoleMismatch(WorkflowAgentError):
    """Raised when validated JSON belongs to a different agent role."""


class AgentOutputValidationError(WorkflowAgentError):
    """Raised when the LLM output cannot be parsed into the output contract."""


REQUIRED_FINDING_COVERAGE_KEYS = {
    "earnings_quality",
    "cash_flow_risk",
    "management_intent",
    "guidance",
}


class _PlanFinding(_workflow_models.AgentFinding):
    """Strict bridge for Plan/active specialist contracts.

    The nested Plan objects are intentionally typed as JSON dictionaries here
    because ``workflow_models`` owns the final canonical shape.  This still
    forbids extra top-level fields and keeps the role-specific required fields
    visible in the output schema.
    """


class _BridgeEarningsQualityFinding(_PlanFinding):
    agent_name: Literal["EarningsQualityAnalyst"] = "EarningsQualityAnalyst"
    eps_surprise_assessment: dict[str, Any]
    quality_of_earnings: dict[str, Any]
    revenue_quality: dict[str, Any]
    margin_trend: dict[str, Any]
    operating_leverage: dict[str, Any]
    segment_mix_effect: dict[str, Any]
    eps_outlook_signal: dict[str, Any]
    fcf_implication: dict[str, Any]


class _BridgeCashFlowRiskFinding(_PlanFinding):
    agent_name: Literal["CashFlowRiskAnalyst"] = "CashFlowRiskAnalyst"
    fcf_trend_assessment: dict[str, Any]
    cash_conversion_assessment: dict[str, Any]
    capex_assessment: dict[str, Any]
    working_capital_effect: dict[str, Any]
    liquidity_assessment: dict[str, Any]
    leverage_or_financing_risk: dict[str, Any]
    fcf_outlook_signal: dict[str, Any]
    eps_constraint: dict[str, Any]


class _BridgeBullCase(_workflow_models.BullCase):
    finding_coverage: _workflow_models.FindingCoverageMap

    @field_validator("finding_coverage")
    @classmethod
    def require_all_specialist_findings(
        cls, value: _workflow_models.FindingCoverageMap
    ) -> _workflow_models.FindingCoverageMap:
        missing = REQUIRED_FINDING_COVERAGE_KEYS.difference(value)
        if missing:
            raise ValueError("finding_coverage missing keys: " + ", ".join(sorted(missing)))
        return value


class _BridgeBearCase(_workflow_models.BearCase):
    finding_coverage: _workflow_models.FindingCoverageMap

    @field_validator("finding_coverage")
    @classmethod
    def require_all_specialist_findings(
        cls, value: _workflow_models.FindingCoverageMap
    ) -> _workflow_models.FindingCoverageMap:
        missing = REQUIRED_FINDING_COVERAGE_KEYS.difference(value)
        if missing:
            raise ValueError("finding_coverage missing keys: " + ", ".join(sorted(missing)))
        return value


EarningsQualityFinding = getattr(
    _workflow_models, "EarningsQualityFinding", _BridgeEarningsQualityFinding
)
CashFlowRiskFinding = getattr(_workflow_models, "CashFlowRiskFinding", _BridgeCashFlowRiskFinding)
ManagementIntentFinding = getattr(_workflow_models, "ManagementIntentFinding")
GuidanceFinding = getattr(_workflow_models, "GuidanceFinding")

_WorkflowBullCase = getattr(_workflow_models, "BullCase")
_WorkflowBearCase = getattr(_workflow_models, "BearCase")
BullCase = (
    _WorkflowBullCase if "finding_coverage" in _WorkflowBullCase.model_fields else _BridgeBullCase
)
BearCase = (
    _WorkflowBearCase if "finding_coverage" in _WorkflowBearCase.model_fields else _BridgeBearCase
)
FinalVerdict = getattr(_workflow_models, "FinalVerdict", _workflow_models.JudgeDecision)
JudgeDecision = getattr(_workflow_models, "JudgeDecision", FinalVerdict)

# Import compatibility for older callers.  These models are not used by active
# runtime agent specs below.
EPSQualityFinding = getattr(_workflow_models, "EPSQualityFinding", EarningsQualityFinding)
ProfitabilityFinding = getattr(_workflow_models, "ProfitabilityFinding", EarningsQualityFinding)
CashFlowFcfFinding = getattr(_workflow_models, "CashFlowFcfFinding", CashFlowRiskFinding)
BalanceSheetRiskFinding = getattr(_workflow_models, "BalanceSheetRiskFinding", CashFlowRiskFinding)


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
        resolve_skill_target(self.spec.public_role)
        routed_context = self._select_context(merged)
        user_prompt = self._build_user_prompt(routed_context)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            prompt = user_prompt if attempt == 0 else self._repair_prompt(user_prompt, last_error)
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
            "- EvidenceItem.source_ref は routed_context.source_index にある"
            " source_ref/source entry を正確にコピーする。source_id, source_type,"
            " url, document_id, section_id, metric_name, page, title を省略・変更しない。\n"
            "- `financial_api:NVDA:2027Q1` のような汎用source_idを新規作成しない。"
            " source_id は source_index に存在する値だけを使う。\n"
            "- routed_context に valid_positive_evidence_ids や valid_negative_evidence_ids が"
            "ある場合、strongest evidence の evidence_id はその一覧から完全一致で選ぶ。\n"
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
            "上のエラーを修正し、同じschemaに合うJSONのみを返してください。\n"
            "`source_ref` は routed_context.source_index に存在するentryを正確にコピーしてください。"
            "source_id, source_type, url, document_id, section_id, metric_name, page, title を"
            "省略・変更しないでください。source_indexに存在しないsource_idを作らないでください。\n"
            "`source_ref.source_type` が `financial_api` または `derived_metric` の場合、"
            "入力済みsource_refにある正確な `metric_name` を nested `source_ref` に必ず含めてください。"
            "metric_nameを新規作成したり、根拠を補正・捏造したりしないでください。"
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
    return build_system_prompt(role, scope)


class EarningsQualityAnalyst(WorkflowAgent):
    spec = AgentSpec(
        public_role="EarningsQualityAnalyst",
        output_agent_name="EarningsQualityAnalyst",
        output_model=EarningsQualityFinding,
        context_keys=(
            "run_spec",
            "earnings_quality_metrics",
            "earnings_quality_sections",
            "source_index",
            "analysis_config",
        ),
        system_prompt=_system(
            "EarningsQualityAnalyst",
            (
                "EPS surpriseとP&Lの質を統合し、売上品質、margin trend、"
                "operating leverage、一時要因/継続要因、将来EPSへの示唆を分析する。"
            ),
        ),
        task_prompt="EarningsQualityFinding JSONを作成してください。",
        role_aliases=("eps_analyst", "pnl_analyst"),
    )


class CashFlowRiskAnalyst(WorkflowAgent):
    spec = AgentSpec(
        public_role="CashFlowRiskAnalyst",
        output_agent_name="CashFlowRiskAnalyst",
        output_model=CashFlowRiskFinding,
        context_keys=(
            "run_spec",
            "cash_flow_risk_metrics",
            "cash_flow_risk_sections",
            "cash_conversion_inputs",
            "source_index",
            "analysis_config",
        ),
        system_prompt=_system(
            "CashFlowRiskAnalyst",
            (
                "CFO、FCF、CapEx、working capital、liquidity、debt、"
                "financing constraintを統合し、将来FCF改善方向とリスクを分析する。"
            ),
        ),
        task_prompt="CashFlowRiskFinding JSONを作成してください。",
        role_aliases=("cfs_analyst", "bs_analyst"),
    )


# Legacy import aliases only.  They are intentionally excluded from
# SPECIALIST_AGENT_CLASSES and ALL_WORKFLOW_AGENT_CLASSES.
EPSQualityAnalyst = EarningsQualityAnalyst
ProfitabilityAnalyst = EarningsQualityAnalyst
CashFlowFcfAnalyst = CashFlowRiskAnalyst
BalanceSheetRiskAnalyst = CashFlowRiskAnalyst


class ManagementIntentAnalyst(WorkflowAgent):
    spec = AgentSpec(
        public_role="ManagementIntentAnalyst",
        output_agent_name="ManagementIntentAnalyst",
        output_model=ManagementIntentFinding,
        context_keys=(
            "run_spec",
            "financial_snapshot_minimal",
            "management_sections",
            "management_intent_sections",
            "strategy_sections",
            "mdna_sections",
            "risk_sections",
            "source_index",
            "analysis_config",
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
            "guidance_metrics",
            "guidance_consensus_deltas",
            "consensus_deltas",
            "guidance_sections",
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
            "earnings_quality_finding",
            "cash_flow_risk_finding",
            "management_intent_finding",
            "guidance_finding",
            "positive_evidence_pool",
            "negative_evidence_pool",
            "disputed_points",
            "missing_data",
        ),
        system_prompt=_system(
            "BullAgent",
            "validated AnalysisBriefだけからgoodと評価できる最も強いcaseを作る。",
        ),
        task_prompt=(
            "BullCase JSONを作成してください。finding_coverageには earnings_quality, "
            "cash_flow_risk, management_intent, guidance を必ず含めてください。"
        ),
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
            "financial_snapshot_summary",
            "analysis_brief",
            "earnings_quality_finding",
            "cash_flow_risk_finding",
            "management_intent_finding",
            "guidance_finding",
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
        task_prompt=(
            "BearCase JSONを作成してください。finding_coverageには earnings_quality, "
            "cash_flow_risk, management_intent, guidance を必ず含めてください。"
        ),
        role_aliases=("BearAgent", "bear"),
        max_tokens=1400,
    )


class JudgeAgent(WorkflowAgent):
    spec = AgentSpec(
        public_role="JudgeAgent",
        output_agent_name="judge_agent",
        output_model=FinalVerdict,
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
    EarningsQualityAnalyst,
    CashFlowRiskAnalyst,
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

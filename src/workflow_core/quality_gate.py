"""AND-condition policy aggregation (Plan-N0002 R5).

gate is the agent's single final branch point: it evaluates every policy
condition — ``tool: "check"`` reads the checks table, every other condition
is judged as a statistical verdict over that metric's samples (future tools
only need to write samples; gate does not enumerate tools) — records the
verdicts and the gate result, and reduces everything to one result.
``retry_then_fail`` counts prior inconclusive evaluations for the same
(candidate_run_id, policy_hash) via the store, so gate stays stateless per
call while retries stay bounded.
"""

from __future__ import annotations

from typing import Literal

from workflow_core import verdict as verdict_mod
from workflow_core.contracts import StrictModel
from workflow_core.policy import Policy, PolicyCondition
from workflow_core.runstore import RunStore
from workflow_core.verdict import VerdictOutcome

ConditionResult = Literal["pass", "fail", "regression", "inconclusive", "error"]
GateResult = Literal["pass", "fail", "inconclusive", "error"]


class ConditionOutcome(StrictModel):
    tool: str
    metric: str
    result: ConditionResult
    detail: str
    verdict: VerdictOutcome | None = None


class GateReport(StrictModel):
    policy_hash: str
    baseline_run_id: str
    candidate_run_id: str
    conditions: list[ConditionOutcome]
    result: GateResult
    warnings: list[str]
    retries_used: int


def _eval_check(store: RunStore, condition: PolicyCondition, run_id: str) -> ConditionOutcome:
    if condition.require not in (None, "pass"):
        detail = f"unsupported require {condition.require!r}; only 'pass' is defined"
        return ConditionOutcome(
            tool="check", metric=condition.metric, result="error", detail=detail
        )
    rows = store.checks_for_run(run_id)
    if condition.metric != "overall":
        rows = [row for row in rows if row.name == condition.metric]
    if not rows:
        detail = f"no check results recorded for run {run_id} (metric {condition.metric!r})"
        return ConditionOutcome(
            tool="check", metric=condition.metric, result="error", detail=detail
        )
    failing = [row.name for row in rows if row.status != "pass"]
    if failing:
        detail = f"failing checks: {', '.join(failing)}"
        return ConditionOutcome(tool="check", metric=condition.metric, result="fail", detail=detail)
    return ConditionOutcome(
        tool="check", metric=condition.metric, result="pass", detail="all checks passed"
    )


def _eval_verdict(
    store: RunStore,
    condition: PolicyCondition,
    baseline_run_id: str,
    candidate_run_id: str,
    *,
    policy_hash: str,
    resamples: int,
    seed: int,
    warnings: list[str],
) -> ConditionOutcome:
    if condition.mode is None or condition.threshold_pct is None:
        detail = "verdict-style condition needs both mode and threshold_pct"
        return ConditionOutcome(
            tool=condition.tool, metric=condition.metric, result="error", detail=detail
        )
    outcome = verdict_mod.compare(
        store.sample_values(baseline_run_id, condition.metric),
        store.sample_values(candidate_run_id, condition.metric),
        mode=condition.mode,
        threshold_pct=condition.threshold_pct,
        metric=condition.metric,
        statistic=condition.statistic,
        resamples=resamples,
        seed=seed,
        warnings=warnings,
    )
    store.record_verdict(
        run_id=candidate_run_id,
        baseline_run_id=baseline_run_id,
        metric=condition.metric,
        statistic=outcome.statistic,
        delta_pct=outcome.delta_pct,
        ci_low=outcome.ci_low,
        ci_high=outcome.ci_high,
        n_base=outcome.n_base,
        n_cand=outcome.n_cand,
        threshold=condition.threshold_pct,
        result=outcome.result,
        reason=outcome.reason,
        policy_hash=policy_hash,
    )
    return ConditionOutcome(
        tool=condition.tool,
        metric=condition.metric,
        result=outcome.result,
        detail=outcome.reason,
        verdict=outcome,
    )


def _fingerprint_warnings(
    store: RunStore, baseline_run_id: str, candidate_run_id: str
) -> list[str]:
    base, cand = store.get_run(baseline_run_id), store.get_run(candidate_run_id)
    if (
        base is not None
        and cand is not None
        and base.env_fingerprint
        and cand.env_fingerprint
        and base.env_fingerprint != cand.env_fingerprint
    ):
        return [f"env_fingerprint mismatch between {baseline_run_id} and {candidate_run_id} (R13)"]
    return []


def _aggregate(
    outcomes: list[ConditionOutcome], policy: Policy, retries_used: int
) -> tuple[GateResult, list[str]]:
    results = {outcome.result for outcome in outcomes}
    if "error" in results:
        return "error", []
    if "fail" in results or "regression" in results:
        return "fail", []
    if "inconclusive" not in results:
        return "pass", []
    metrics = ", ".join(o.metric for o in outcomes if o.result == "inconclusive")
    if policy.on_inconclusive == "pass_with_warning":
        return "pass", [f"inconclusive conditions passed with warning: {metrics}"]
    if policy.on_inconclusive == "retry_then_fail" and retries_used < policy.max_retries:
        return "inconclusive", [f"re-measure requested for: {metrics}"]
    if policy.on_inconclusive == "retry_then_fail":
        return "fail", [
            f"max_retries={policy.max_retries} exhausted; still inconclusive: {metrics}"
        ]
    return "fail", [f"on_inconclusive=fail; inconclusive: {metrics}"]


def evaluate_gate(
    store: RunStore,
    policy: Policy,
    policy_hash: str,
    *,
    baseline_run_id: str,
    candidate_run_id: str,
    decided_at: str,
    resamples: int = verdict_mod.DEFAULT_RESAMPLES,
    seed: int = verdict_mod.DEFAULT_SEED,
) -> GateReport:
    warnings = _fingerprint_warnings(store, baseline_run_id, candidate_run_id)
    outcomes = [
        _eval_check(store, condition, candidate_run_id)
        if condition.tool == "check"
        else _eval_verdict(
            store,
            condition,
            baseline_run_id,
            candidate_run_id,
            policy_hash=policy_hash,
            resamples=resamples,
            seed=seed,
            warnings=warnings,
        )
        for condition in policy.conditions
    ]
    retries_used = store.inconclusive_gate_count(candidate_run_id, policy_hash)
    result, aggregate_warnings = _aggregate(outcomes, policy, retries_used)
    report = GateReport(
        policy_hash=policy_hash,
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        conditions=outcomes,
        result=result,
        warnings=warnings + aggregate_warnings,
        retries_used=retries_used,
    )
    store.record_gate_result(
        candidate_run_id=candidate_run_id,
        baseline_run_id=baseline_run_id,
        policy_hash=policy_hash,
        result=result,
        report_json=report.model_dump_json(),
        decided_at=decided_at,
    )
    return report

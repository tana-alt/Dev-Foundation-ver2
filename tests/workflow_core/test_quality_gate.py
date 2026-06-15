from __future__ import annotations

from pathlib import Path

from workflow_core.policy import Policy, PolicyCondition
from workflow_core.quality_gate import GateReport, evaluate_gate
from workflow_core.runstore import RunStore

# Pinned datasets shared with test_verdict.py (stable at >=1500 resamples).
BASE = [100.0, 101.0, 99.0, 100.5, 100.2, 99.8, 100.1, 100.3, 99.9, 100.0]
REGRESS = [112.0, 113.0, 111.0, 112.5, 112.2, 111.8, 112.1, 112.3, 111.9, 112.0]
STRADDLE = [104.0, 106.0, 103.0, 108.0, 102.0, 107.0, 105.0, 104.5, 105.5, 106.5]
RESAMPLES = 1500

CHECK_COND = PolicyCondition(tool="check", metric="overall", require="pass")
VERDICT_COND = PolicyCondition(tool="verdict", metric="m", mode="non_regression", threshold_pct=5.0)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_store(tmp_path: Path) -> RunStore:
    return RunStore(tmp_path / "runs.db")


def seed_runs(
    store: RunStore,
    cand_values: list[float],
    *,
    check_status: str = "pass",
    cand_fingerprint: str = "fp",
) -> None:
    store.create_run("base", started_at="t0", env_fingerprint="fp")
    store.create_run("cand", started_at="t1", env_fingerprint=cand_fingerprint)
    for i, value in enumerate(BASE):
        store.record_sample("base", "m", i, value)
    for i, value in enumerate(cand_values):
        store.record_sample("cand", "m", i, value)
    store.record_check("cand", "test", status=check_status, duration_s=1.0, command="pytest")


def gate(store: RunStore, policy: Policy) -> GateReport:
    return evaluate_gate(
        store,
        policy,
        "ph-test",
        baseline_run_id="base",
        candidate_run_id="cand",
        decided_at="t2",
        resamples=RESAMPLES,
    )


def make_policy(
    conditions: list[PolicyCondition], on_inconclusive: str = "fail", max_retries: int = 0
) -> Policy:
    return Policy.model_validate(
        {
            "policy_version": 1,
            "conditions": [c.model_dump() for c in conditions],
            "on_inconclusive": on_inconclusive,
            "max_retries": max_retries,
        }
    )


# ---------------------------------------------------------------------------
# aggregation: pass / fail / error
# ---------------------------------------------------------------------------


def test_all_conditions_pass(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    seed_runs(store, list(BASE))
    report = gate(store, make_policy([CHECK_COND, VERDICT_COND]))
    assert report.result == "pass"
    assert [c.result for c in report.conditions] == ["pass", "pass"]
    store.close()


def test_regression_fails_gate_and_records_verdict(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    seed_runs(store, REGRESS)
    report = gate(store, make_policy([CHECK_COND, VERDICT_COND]))
    assert report.result == "fail"
    verdicts = store.verdicts_for_run("cand")
    assert len(verdicts) == 1
    assert verdicts[0].result == "regression"
    assert verdicts[0].policy_hash == "ph-test"
    store.close()


def test_failing_check_fails_gate(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    seed_runs(store, list(BASE), check_status="fail")
    report = gate(store, make_policy([CHECK_COND, VERDICT_COND]))
    assert report.result == "fail"
    assert report.conditions[0].result == "fail"
    store.close()


def test_missing_check_rows_is_error(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.create_run("base", started_at="t0")
    store.create_run("cand", started_at="t1")
    report = gate(store, make_policy([CHECK_COND]))
    assert report.result == "error"
    assert "no check results" in report.conditions[0].detail
    store.close()


def test_condition_without_threshold_is_error(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    seed_runs(store, list(BASE))
    bare = PolicyCondition(tool="verdict", metric="m")
    report = gate(store, make_policy([bare]))
    assert report.result == "error"
    assert "mode and threshold_pct" in report.conditions[0].detail
    store.close()


# ---------------------------------------------------------------------------
# on_inconclusive handling
# ---------------------------------------------------------------------------


def test_retry_then_fail_counts_down_then_fails(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    seed_runs(store, STRADDLE)
    policy = make_policy([VERDICT_COND], on_inconclusive="retry_then_fail", max_retries=2)
    first = gate(store, policy)
    second = gate(store, policy)
    third = gate(store, policy)
    assert (first.result, second.result, third.result) == (
        "inconclusive",
        "inconclusive",
        "fail",
    )
    assert (first.retries_used, second.retries_used, third.retries_used) == (0, 1, 2)
    assert "max_retries=2 exhausted" in third.warnings[-1]
    store.close()


def test_on_inconclusive_fail(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    seed_runs(store, STRADDLE)
    report = gate(store, make_policy([VERDICT_COND], on_inconclusive="fail"))
    assert report.result == "fail"
    store.close()


def test_on_inconclusive_pass_with_warning(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    seed_runs(store, STRADDLE)
    report = gate(store, make_policy([VERDICT_COND], on_inconclusive="pass_with_warning"))
    assert report.result == "pass"
    assert any("m" in warning for warning in report.warnings)
    store.close()


# ---------------------------------------------------------------------------
# provenance warnings
# ---------------------------------------------------------------------------


def test_fingerprint_mismatch_warns_but_judges(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    seed_runs(store, list(BASE), cand_fingerprint="other-fp")
    report = gate(store, make_policy([CHECK_COND, VERDICT_COND]))
    assert report.result == "pass"
    assert any("env_fingerprint mismatch" in warning for warning in report.warnings)
    store.close()

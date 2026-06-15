from __future__ import annotations

import pytest

from workflow_core.verdict import VerdictOutcome, compare, mad_filter, statistic_value

# Pinned datasets: stable verdicts verified at 1500/2000/10000 resamples.
BASE = [100.0, 101.0, 99.0, 100.5, 100.2, 99.8, 100.1, 100.3, 99.9, 100.0]
REGRESS = [112.0, 113.0, 111.0, 112.5, 112.2, 111.8, 112.1, 112.3, 111.9, 112.0]
IMPROVE = [60.0, 61.0, 59.0, 60.5, 60.2, 59.8, 60.1, 60.3, 59.9, 60.0]
STRADDLE = [104.0, 106.0, 103.0, 108.0, 102.0, 107.0, 105.0, 104.5, 105.5, 106.5]
RESAMPLES = 1500

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def judge(base: list[float], cand: list[float], **overrides: object) -> VerdictOutcome:
    kwargs: dict[str, object] = {
        "mode": "non_regression",
        "threshold_pct": 5.0,
        "resamples": RESAMPLES,
    }
    kwargs.update(overrides)
    return compare(base, cand, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# statistic_value / mad_filter
# ---------------------------------------------------------------------------


def test_statistic_value_vocabulary() -> None:
    values = [float(i) for i in range(1, 101)]
    assert statistic_value(values, "median") == 50.0
    assert statistic_value(values, "p50") == 50.0
    assert statistic_value(values, "p95") == 95.0
    assert statistic_value(values, "max") == 100.0
    assert statistic_value(values, "mean") == pytest.approx(50.5)


def test_statistic_value_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unknown statistic"):
        statistic_value([1.0], "p99")


def test_mad_filter_keeps_identical_values() -> None:
    kept, excluded = mad_filter([5.0] * 8)
    assert kept == [5.0] * 8
    assert excluded == 0


def test_mad_filter_drops_far_outlier() -> None:
    kept, excluded = mad_filter([*BASE, 500.0])
    assert excluded == 1
    assert 500.0 not in kept


# ---------------------------------------------------------------------------
# compare: the four results
# ---------------------------------------------------------------------------


def test_regression_detected() -> None:
    outcome = judge(BASE, REGRESS)
    assert outcome.result == "regression"
    assert outcome.ci_low is not None and outcome.ci_low > 5.0
    assert outcome.delta_pct == pytest.approx(12.0, abs=1.0)


def test_neutral_passes() -> None:
    outcome = judge(BASE, list(BASE))
    assert outcome.result == "pass"
    assert outcome.ci_high is not None and outcome.ci_high < 5.0


def test_improvement_passes_non_regression() -> None:
    outcome = judge(BASE, IMPROVE)
    assert outcome.result == "pass"
    assert outcome.delta_pct == pytest.approx(-40.0, abs=2.0)


def test_straddle_is_inconclusive_with_suggestion() -> None:
    outcome = judge(BASE, STRADDLE)
    assert outcome.result == "inconclusive"
    assert "straddles" in outcome.reason
    suggestion = outcome.suggested_additional_iterations
    assert suggestion is not None and suggestion >= 1


def test_insufficient_samples_is_error() -> None:
    outcome = judge(BASE[:6], REGRESS)
    assert outcome.result == "error"
    assert outcome.reason.startswith("insufficient_samples")
    assert outcome.delta_pct is None


def test_zero_baseline_is_error() -> None:
    outcome = judge([0.0] * 10, list(BASE))
    assert outcome.result == "error"
    assert outcome.reason.startswith("zero_baseline")


# ---------------------------------------------------------------------------
# compare: outlier handling
# ---------------------------------------------------------------------------


def test_single_outlier_filtered_then_pass() -> None:
    outcome = judge([*BASE[:9], 500.0], [*BASE[:9], 480.0])
    assert outcome.excluded_base == 1
    assert outcome.excluded_cand == 1
    assert outcome.result == "pass"


def test_excessive_outliers_inconclusive() -> None:
    outcome = judge([100.0] * 8 + [200.0, 210.0], list(BASE))
    assert outcome.result == "inconclusive"
    assert outcome.reason.startswith("excessive_outliers")


# ---------------------------------------------------------------------------
# compare: modes
# ---------------------------------------------------------------------------


def test_higher_is_better_drop_is_regression() -> None:
    outcome = judge(BASE, IMPROVE, mode="higher_is_better")
    assert outcome.result == "regression"
    assert outcome.delta_pct is not None and outcome.delta_pct > 5.0


def test_higher_is_better_gain_passes() -> None:
    outcome = judge(BASE, REGRESS, mode="higher_is_better")
    assert outcome.result == "pass"


def test_lower_is_better_matches_non_regression() -> None:
    assert judge(BASE, REGRESS, mode="lower_is_better").result == "regression"
    assert judge(BASE, IMPROVE, mode="lower_is_better").result == "pass"


def test_equal_required_pass_and_regression() -> None:
    same = [3.0] * 8
    assert judge(same, list(same), mode="equal_required").result == "pass"
    outcome = judge(same, [4.0] * 8, mode="equal_required")
    assert outcome.result == "regression"
    assert "differs" in outcome.reason


# ---------------------------------------------------------------------------
# compare: reproducibility and plumbing
# ---------------------------------------------------------------------------


def test_same_seed_is_deterministic() -> None:
    first = judge(BASE, STRADDLE, seed=7)
    second = judge(BASE, STRADDLE, seed=7)
    assert first.ci_low == second.ci_low
    assert first.ci_high == second.ci_high
    assert first.seed == 7


def test_unknown_statistic_raises() -> None:
    with pytest.raises(ValueError, match="unknown statistic"):
        judge(BASE, REGRESS, statistic="p99")


def test_warnings_pass_through() -> None:
    outcome = judge(BASE, REGRESS, warnings=["env_fingerprint mismatch"])
    assert outcome.warnings == ["env_fingerprint mismatch"]

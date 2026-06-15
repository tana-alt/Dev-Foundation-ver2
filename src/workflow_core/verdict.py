"""Statistical comparison verdicts for the AB evaluation pipeline (Plan-N0002 R2).

Raw samples in, four-valued judgement out: ``pass`` / ``regression`` /
``inconclusive`` / ``error``. The deliberate core is ``inconclusive`` — when
the bootstrap CI of the relative delta straddles the threshold the tool
refuses to guess, so an agent never loops on "fixing" a phantom regression
born of timer noise. The bootstrap is seeded and the seed is recorded, so
every judgement is reproducible.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import Any, Literal

from workflow_core.contracts import StrictModel
from workflow_core.stats import percentile

Mode = Literal["lower_is_better", "higher_is_better", "equal_required", "non_regression"]
VerdictResult = Literal["pass", "regression", "inconclusive", "error"]

DEFAULT_SEED = 20260612
DEFAULT_RESAMPLES = 10_000
MIN_SAMPLES = 7
_STATISTICS = ("median", "p50", "p95", "max", "mean")
_MAD_CONSISTENCY = 1.4826  # scales MAD to a normal-equivalent sigma
_MAD_SIGMA = 5.0
_MAX_EXCLUSION_RATE = 0.10
_SUGGESTION_CAP = 200


class VerdictOutcome(StrictModel):
    metric: str
    mode: Mode
    statistic: str
    n_base: int
    n_cand: int
    excluded_base: int
    excluded_cand: int
    delta_pct: float | None
    ci_low: float | None
    ci_high: float | None
    threshold_pct: float
    result: VerdictResult
    reason: str
    suggested_additional_iterations: int | None
    seed: int
    resamples: int
    warnings: list[str]


def statistic_value(values: Sequence[float], statistic: str) -> float:
    ordered = sorted(values)
    if statistic in ("median", "p50"):
        return percentile(ordered, 0.50)
    if statistic == "p95":
        return percentile(ordered, 0.95)
    if statistic == "max":
        return ordered[-1]
    if statistic == "mean":
        return sum(ordered) / len(ordered)
    raise ValueError(f"unknown statistic {statistic!r}; expected one of {_STATISTICS}")


def mad_filter(values: Sequence[float]) -> tuple[list[float], int]:
    """Drop values beyond 5 normal-equivalent sigmas of the MAD."""
    med = percentile(sorted(values), 0.50)
    deviations = sorted(abs(v - med) for v in values)
    cutoff = _MAD_SIGMA * _MAD_CONSISTENCY * percentile(deviations, 0.50)
    kept = [v for v in values if abs(v - med) <= cutoff]
    return kept, len(values) - len(kept)


def _bootstrap_deltas(
    base: Sequence[float], cand: Sequence[float], statistic: str, *, resamples: int, seed: int
) -> list[float]:
    """Percentile-bootstrap distribution of the relative delta (in %)."""
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(resamples):
        t_base = statistic_value(rng.choices(base, k=len(base)), statistic)
        if t_base == 0:
            continue
        t_cand = statistic_value(rng.choices(cand, k=len(cand)), statistic)
        deltas.append((t_cand - t_base) / t_base * 100.0)
    return deltas


def _suggest_iterations(n: int, width: float, threshold: float, point: float) -> int:
    """CI width shrinks ~1/sqrt(n); estimate extra iterations to clear the threshold."""
    distance = 2.0 * abs(threshold - point)
    if distance <= 0 or width <= 0:
        return _SUGGESTION_CAP
    needed_total = n * (width / distance) ** 2
    return max(1, min(_SUGGESTION_CAP, math.ceil(needed_total) - n))


def _finish(
    common: dict[str, Any], result: VerdictResult, reason: str, **extra: Any
) -> VerdictOutcome:
    return VerdictOutcome(**{**common, **extra, "result": result, "reason": reason})


def _base_fields(
    base: Sequence[float],
    cand: Sequence[float],
    *,
    mode: Mode,
    threshold_pct: float,
    metric: str,
    statistic: str,
    resamples: int,
    seed: int,
    warnings: Sequence[str],
) -> dict[str, Any]:
    return {
        "metric": metric,
        "mode": mode,
        "statistic": statistic,
        "threshold_pct": threshold_pct,
        "seed": seed,
        "resamples": resamples,
        "warnings": list(warnings),
        "n_base": len(base),
        "n_cand": len(cand),
        "excluded_base": 0,
        "excluded_cand": 0,
        "delta_pct": None,
        "ci_low": None,
        "ci_high": None,
        "suggested_additional_iterations": None,
    }


def _equal_required(
    kept_base: list[float], kept_cand: list[float], statistic: str, common: dict[str, Any]
) -> VerdictOutcome:
    t_base = statistic_value(kept_base, statistic)
    t_cand = statistic_value(kept_cand, statistic)
    if t_base != 0:
        common["delta_pct"] = round((t_cand - t_base) / t_base * 100.0, 4)
    if t_cand == t_base:
        return _finish(common, "pass", f"{statistic} equal ({t_base})")
    reason = f"{statistic} differs: baseline {t_base} candidate {t_cand}"
    return _finish(common, "regression", reason)


def _decide(
    lo: float, hi: float, threshold: float, n_min: int, common: dict[str, Any]
) -> VerdictOutcome:
    ci_text = f"95% CI [{round(lo, 4)}, {round(hi, 4)}]"
    if lo > threshold:
        return _finish(common, "regression", f"{ci_text} above threshold {threshold}")
    if hi < threshold:
        return _finish(common, "pass", f"{ci_text} below threshold {threshold}")
    point = float(common["delta_pct"])
    suggestion = _suggest_iterations(n_min, hi - lo, threshold, point)
    return _finish(
        common,
        "inconclusive",
        f"{ci_text} straddles threshold {threshold}",
        suggested_additional_iterations=suggestion,
    )


def compare(
    base: Sequence[float],
    cand: Sequence[float],
    *,
    mode: Mode,
    threshold_pct: float,
    metric: str = "",
    statistic: str = "median",
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    warnings: Sequence[str] = (),
) -> VerdictOutcome:
    """Judge candidate samples against baseline samples per R2 steps 1-7."""
    if statistic not in _STATISTICS:
        raise ValueError(f"unknown statistic {statistic!r}; expected one of {_STATISTICS}")
    common = _base_fields(
        base,
        cand,
        mode=mode,
        threshold_pct=threshold_pct,
        metric=metric,
        statistic=statistic,
        resamples=resamples,
        seed=seed,
        warnings=warnings,
    )
    if len(base) < MIN_SAMPLES or len(cand) < MIN_SAMPLES:
        reason = (
            f"insufficient_samples: need >= {MIN_SAMPLES} per side,"
            f" got n_base={len(base)} n_cand={len(cand)}"
        )
        return _finish(common, "error", reason)
    kept_base, excluded_base = mad_filter(base)
    kept_cand, excluded_cand = mad_filter(cand)
    common["excluded_base"], common["excluded_cand"] = excluded_base, excluded_cand
    if max(excluded_base / len(base), excluded_cand / len(cand)) > _MAX_EXCLUSION_RATE:
        reason = (
            f"excessive_outliers: excluded {excluded_base}/{len(base)} baseline and"
            f" {excluded_cand}/{len(cand)} candidate samples (limit 10%)"
        )
        return _finish(common, "inconclusive", reason)
    if mode == "equal_required":
        return _equal_required(kept_base, kept_cand, statistic, common)
    t_base = statistic_value(kept_base, statistic)
    if t_base == 0:
        return _finish(common, "error", "zero_baseline: relative delta is undefined")
    t_cand = statistic_value(kept_cand, statistic)
    point = (t_cand - t_base) / t_base * 100.0
    deltas = _bootstrap_deltas(kept_base, kept_cand, statistic, resamples=resamples, seed=seed)
    if len(deltas) < resamples // 2:
        return _finish(common, "error", "degenerate_bootstrap: too many zero-baseline resamples")
    ordered = sorted(deltas)
    lo, hi = percentile(ordered, 0.025), percentile(ordered, 0.975)
    if mode == "higher_is_better":
        point, lo, hi = -point, -hi, -lo
    common["delta_pct"] = round(point, 4)
    common["ci_low"], common["ci_high"] = round(lo, 4), round(hi, 4)
    return _decide(lo, hi, threshold_pct, min(len(kept_base), len(kept_cand)), common)

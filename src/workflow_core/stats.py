"""Shared distribution statistics for the harness's sample stores.

``NfrStore`` (budget verdicts) and ``BenchStore`` (baseline comparisons) both
reduce ordered samples to the same four statistics; this module owns that
vocabulary so the two stores cannot drift apart on percentile semantics.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal, NamedTuple

Statistic = Literal["p50", "p95", "max", "mean"]


class Distribution(NamedTuple):
    p50: float
    p95: float
    max: float
    mean: float


def percentile(ordered: Sequence[float], q: float) -> float:
    """Nearest-rank percentile over pre-sorted values."""
    rank = max(math.ceil(q * len(ordered)), 1)
    return ordered[rank - 1]


def describe(ordered: Sequence[float]) -> Distribution:
    """Reduce non-empty pre-sorted values to the shared summary statistics."""
    return Distribution(
        p50=percentile(ordered, 0.50),
        p95=percentile(ordered, 0.95),
        max=ordered[-1],
        mean=round(sum(ordered) / len(ordered), 4),
    )

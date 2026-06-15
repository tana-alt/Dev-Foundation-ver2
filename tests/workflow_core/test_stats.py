from __future__ import annotations

import pytest

from workflow_core.stats import describe, percentile

# ---------------------------------------------------------------------------
# percentile
# ---------------------------------------------------------------------------


def test_percentile_single_element() -> None:
    assert percentile([42.0], 0.50) == 42.0
    assert percentile([42.0], 0.95) == 42.0


def test_percentile_p50_and_p95_on_1_to_100() -> None:
    data = [float(i) for i in range(1, 101)]
    assert percentile(data, 0.50) == 50.0
    assert percentile(data, 0.95) == 95.0


# ---------------------------------------------------------------------------
# describe
# ---------------------------------------------------------------------------


def test_describe_on_1_to_100() -> None:
    data = [float(i) for i in range(1, 101)]
    dist = describe(data)
    assert dist.p50 == 50.0
    assert dist.p95 == 95.0
    assert dist.max == 100.0
    assert dist.mean == pytest.approx(50.5, abs=1e-3)


def test_describe_rounds_mean_to_four_decimals() -> None:
    dist = describe([1.0, 2.0, 2.0])
    assert dist.mean == round(5.0 / 3.0, 4)

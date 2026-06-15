from __future__ import annotations

from pathlib import Path

import pytest

from workflow_core.nfr import NfrStore, NfrSummary, NfrVerdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_store(tmp_path: Path) -> NfrStore:
    return NfrStore(tmp_path / "nfr.db")


def record_range(store: NfrStore, metric: str, values: list[float], *, unit: str = "ms") -> None:
    """Insert values with synthetic timestamps derived from position."""
    for i, v in enumerate(values):
        store.record(metric, v, ts=f"2026-01-01T00:00:{i:02d}Z", unit=unit)


# ---------------------------------------------------------------------------
# record → summarize
# ---------------------------------------------------------------------------


def test_summarize_count_p50_p95_max_mean(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    values = [float(i) for i in range(1, 101)]  # 1..100
    record_range(store, "latency", values)
    s = store.summarize("latency")
    assert isinstance(s, NfrSummary)
    assert s.count == 100
    assert s.p50 == 50.0
    assert s.p95 == 95.0
    assert s.max == 100.0
    assert s.mean == pytest.approx(50.5, abs=1e-3)
    store.close()


def test_summarize_preserves_unit(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("cpu", 0.8, ts="2026-01-01T00:00:00Z", unit="ratio")
    s = store.summarize("cpu")
    assert s is not None
    assert s.unit == "ratio"
    store.close()


def test_summarize_unknown_metric_returns_none(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert store.summarize("does_not_exist") is None
    store.close()


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------


def test_evaluate_unknown_metric_returns_none(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert store.evaluate("does_not_exist", threshold=100.0) is None
    store.close()


def test_evaluate_passed_when_at_threshold(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_range(store, "latency", [float(i) for i in range(1, 101)])
    verdict = store.evaluate("latency", threshold=95.0, statistic="p95")
    assert isinstance(verdict, NfrVerdict)
    assert verdict.passed is True
    assert verdict.observed == 95.0
    store.close()


def test_evaluate_failed_when_over_threshold(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_range(store, "latency", [float(i) for i in range(1, 101)])
    verdict = store.evaluate("latency", threshold=94.9, statistic="p95")
    assert isinstance(verdict, NfrVerdict)
    assert verdict.passed is False
    assert verdict.observed == 95.0
    store.close()


def test_evaluate_statistic_max(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_range(store, "latency", [10.0, 20.0, 300.0])
    verdict_ok = store.evaluate("latency", threshold=300.0, statistic="max")
    assert verdict_ok is not None
    assert verdict_ok.passed is True
    verdict_fail = store.evaluate("latency", threshold=299.9, statistic="max")
    assert verdict_fail is not None
    assert verdict_fail.passed is False
    store.close()


def test_evaluate_statistic_mean(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_range(store, "latency", [10.0, 20.0, 30.0])
    verdict = store.evaluate("latency", threshold=20.0, statistic="mean")
    assert verdict is not None
    assert verdict.passed is True
    assert verdict.observed == pytest.approx(20.0, abs=1e-3)
    store.close()


def test_evaluate_statistic_p50(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_range(store, "latency", [float(i) for i in range(1, 101)])
    verdict = store.evaluate("latency", threshold=50.0, statistic="p50")
    assert verdict is not None
    assert verdict.passed is True
    assert verdict.observed == 50.0
    store.close()


def test_evaluate_verdict_carries_count(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_range(store, "latency", [1.0, 2.0, 3.0])
    verdict = store.evaluate("latency", threshold=999.0)
    assert verdict is not None
    assert verdict.count == 3
    store.close()


# ---------------------------------------------------------------------------
# enforce_retention
# ---------------------------------------------------------------------------


def test_enforce_retention_drops_oldest_samples(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    # ts ascending: 00, 01, ..., 04 → oldest are ts 00, 01, 02
    for i in range(5):
        store.record("lat", float(i + 1), ts=f"2026-01-01T00:00:0{i}Z")
    purged = store.enforce_retention(max_samples_per_metric=2)
    assert purged == 3
    s = store.summarize("lat")
    assert s is not None
    assert s.count == 2
    assert s.max == 5.0  # only newest two (4.0, 5.0) remain
    store.close()


def test_enforce_retention_noop_under_threshold(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_range(store, "lat", [1.0, 2.0])
    assert store.enforce_retention(max_samples_per_metric=10) == 0
    store.close()


def test_enforce_retention_does_not_affect_other_metrics(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    # "lat" gets 5 samples; "cpu" gets 2 — only lat should be trimmed
    for i in range(5):
        store.record("lat", float(i + 1), ts=f"2026-01-01T00:00:0{i}Z")
    store.record("cpu", 0.5, ts="2026-01-01T00:00:00Z")
    store.record("cpu", 0.6, ts="2026-01-01T00:00:01Z")
    purged = store.enforce_retention(max_samples_per_metric=2)
    assert purged == 3
    cpu_summary = store.summarize("cpu")
    assert cpu_summary is not None
    assert cpu_summary.count == 2
    store.close()


def test_enforce_retention_returns_total_across_metrics(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    for i in range(4):
        store.record("a", float(i), ts=f"2026-01-01T00:00:0{i}Z")
    for i in range(4):
        store.record("b", float(i), ts=f"2026-01-01T00:00:0{i}Z")
    purged = store.enforce_retention(max_samples_per_metric=2)
    assert purged == 4  # 2 from "a" + 2 from "b"
    store.close()


# ---------------------------------------------------------------------------
# purge_metric
# ---------------------------------------------------------------------------


def test_purge_metric_removes_all_samples(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_range(store, "lat", [1.0, 2.0, 3.0])
    deleted = store.purge_metric("lat")
    assert deleted == 3
    assert store.summarize("lat") is None
    store.close()


def test_purge_metric_other_metrics_unaffected(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_range(store, "lat", [1.0, 2.0])
    record_range(store, "cpu", [0.5, 0.6, 0.7])
    store.purge_metric("lat")
    cpu_summary = store.summarize("cpu")
    assert cpu_summary is not None
    assert cpu_summary.count == 3
    store.close()


def test_purge_metric_nonexistent_returns_zero(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert store.purge_metric("ghost") == 0
    store.close()


# ---------------------------------------------------------------------------
# record validation
# ---------------------------------------------------------------------------


def test_record_empty_metric_raises_value_error(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="metric"):
        store.record("", 1.0, ts="2026-01-01T00:00:00Z")
    store.close()


def test_record_whitespace_only_metric_raises_value_error(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="metric"):
        store.record("   ", 1.0, ts="2026-01-01T00:00:00Z")
    store.close()


# ---------------------------------------------------------------------------
# Context-manager protocol
# ---------------------------------------------------------------------------


def test_nfr_context_manager_record_and_read() -> None:
    """NfrStore works as a context manager; data is readable inside the block."""
    with NfrStore(":memory:") as store:
        store.record("latency", 42.0, ts="2026-06-11T00:00:00Z")
        s = store.summarize("latency")
        assert s is not None
        assert s.count == 1
        assert s.max == 42.0


def test_nfr_context_manager_connection_closed_after_exit() -> None:
    """After the with block, the connection is closed and raises ProgrammingError."""
    import sqlite3

    store = NfrStore(":memory:")
    with store:
        store.record("latency", 10.0, ts="2026-06-11T00:00:00Z")
    with pytest.raises(sqlite3.ProgrammingError):
        store._conn.execute("SELECT 1")


# ---------------------------------------------------------------------------
# Non-finite value validation
# ---------------------------------------------------------------------------


def test_record_nan_raises_value_error(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="finite"):
        store.record("lat", float("nan"), ts="2026-06-11T00:00:00Z")
    store.close()


def test_record_inf_raises_value_error(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="finite"):
        store.record("lat", float("inf"), ts="2026-06-11T00:00:00Z")
    store.close()


def test_record_negative_inf_raises_value_error(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="finite"):
        store.record("lat", float("-inf"), ts="2026-06-11T00:00:00Z")
    store.close()

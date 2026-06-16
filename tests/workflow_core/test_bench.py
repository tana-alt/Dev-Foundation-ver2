from __future__ import annotations

from pathlib import Path

import pytest

from workflow_core.bench import BenchComparison, BenchStore, BenchSummary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_store(tmp_path: Path) -> BenchStore:
    return BenchStore(tmp_path / "bench.db")


def record_series(
    store: BenchStore, benchmark: str, label: str, values: list[float], *, unit: str = "ms"
) -> None:
    """Insert values with synthetic timestamps derived from position."""
    for i, v in enumerate(values):
        store.record(benchmark, v, label=label, ts=f"2026-01-01T00:00:{i:02d}Z", unit=unit)


# ---------------------------------------------------------------------------
# record → summarize
# ---------------------------------------------------------------------------


def test_summarize_count_p50_p95_max_mean(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [float(i) for i in range(1, 101)])
    s = store.summarize("api", "baseline")
    assert isinstance(s, BenchSummary)
    assert s.count == 100
    assert s.p50 == 50.0
    assert s.p95 == 95.0
    assert s.max == 100.0
    assert s.mean == pytest.approx(50.5, abs=1e-3)
    store.close()


def test_summarize_preserves_unit_and_label(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record("mem", 512.0, label="baseline", ts="2026-01-01T00:00:00Z", unit="kb")
    s = store.summarize("mem", "baseline")
    assert s is not None
    assert s.unit == "kb"
    assert s.benchmark == "mem"
    assert s.label == "baseline"
    store.close()


def test_summarize_unknown_benchmark_or_label_returns_none(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [1.0])
    assert store.summarize("ghost", "baseline") is None
    assert store.summarize("api", "ghost") is None
    store.close()


def test_benchmarks_and_labels_listing(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [1.0])
    record_series(store, "api", "candidate", [1.0])
    record_series(store, "batch", "baseline", [1.0])
    assert store.benchmarks() == ["api", "batch"]
    assert store.labels("api") == ["baseline", "candidate"]
    assert store.labels("batch") == ["baseline"]
    store.close()


# ---------------------------------------------------------------------------
# compare verdicts
# ---------------------------------------------------------------------------


def test_compare_improved(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [100.0, 100.0, 100.0])
    record_series(store, "api", "candidate", [50.0, 50.0, 50.0])
    c = store.compare("api")
    assert isinstance(c, BenchComparison)
    assert c.verdict == "improved"
    assert c.baseline_value == 100.0
    assert c.candidate_value == 50.0
    assert c.delta == -50.0
    assert c.improvement_pct == pytest.approx(50.0)
    store.close()


def test_compare_regressed(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [100.0])
    record_series(store, "api", "candidate", [150.0])
    c = store.compare("api")
    assert c is not None
    assert c.verdict == "regressed"
    assert c.improvement_pct == pytest.approx(-50.0)
    store.close()


def test_compare_unchanged_within_noise_band(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [100.0])
    record_series(store, "api", "candidate", [98.0])  # 2% < default 3% band
    c = store.compare("api")
    assert c is not None
    assert c.verdict == "unchanged"
    store.close()


def test_compare_band_boundary_is_inclusive(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [100.0])
    record_series(store, "api", "candidate", [97.0])  # exactly 3%
    c = store.compare("api", min_change_pct=3.0)
    assert c is not None
    assert c.verdict == "improved"
    store.close()


def test_compare_zero_band_keeps_equal_distributions_unchanged(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [100.0])
    record_series(store, "api", "candidate", [100.0])
    c = store.compare("api", min_change_pct=0.0)
    assert c is not None
    assert c.verdict == "unchanged"
    store.close()


def test_compare_zero_band_flags_any_change(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [100.0])
    record_series(store, "api", "candidate", [99.9])
    c = store.compare("api", min_change_pct=0.0)
    assert c is not None
    assert c.verdict == "improved"
    store.close()


def test_compare_missing_side_returns_none(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [1.0])
    assert store.compare("api") is None
    assert store.compare("ghost") is None
    store.close()


def test_compare_custom_labels(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "v1", [100.0])
    record_series(store, "api", "v2", [80.0])
    c = store.compare("api", baseline="v1", candidate="v2")
    assert c is not None
    assert c.verdict == "improved"
    assert c.baseline.label == "v1"
    assert c.candidate.label == "v2"
    store.close()


def test_compare_statistic_selection(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    # Same median, much worse tail: p50 unchanged, p95 regressed.
    # n=20 → nearest-rank p95 is the 19th sorted value, so the tail needs two
    # elevated samples to land on it.
    record_series(store, "api", "baseline", [100.0] * 18 + [110.0, 120.0])
    record_series(store, "api", "candidate", [100.0] * 18 + [300.0, 310.0])
    by_p50 = store.compare("api", statistic="p50")
    by_p95 = store.compare("api", statistic="p95")
    assert by_p50 is not None and by_p50.verdict == "unchanged"
    assert by_p95 is not None and by_p95.verdict == "regressed"
    store.close()


def test_compare_unit_mismatch_raises(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [1.0], unit="ms")
    record_series(store, "api", "candidate", [1.0], unit="s")
    with pytest.raises(ValueError, match="unit mismatch"):
        store.compare("api")
    store.close()


def test_compare_negative_band_raises(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="min_change_pct"):
        store.compare("api", min_change_pct=-1.0)
    store.close()


def test_compare_zero_baseline_zero_candidate_unchanged(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [0.0])
    record_series(store, "api", "candidate", [0.0])
    c = store.compare("api")
    assert c is not None
    assert c.verdict == "unchanged"
    assert c.improvement_pct == 0.0
    store.close()


def test_compare_zero_baseline_nonzero_candidate_regressed(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [0.0])
    record_series(store, "api", "candidate", [5.0])
    c = store.compare("api")
    assert c is not None
    assert c.verdict == "regressed"
    assert c.improvement_pct == 0.0
    store.close()


# ---------------------------------------------------------------------------
# enforce_retention
# ---------------------------------------------------------------------------


def test_enforce_retention_drops_oldest_per_label(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [1.0, 2.0, 3.0, 4.0, 5.0])
    purged = store.enforce_retention(max_samples_per_label=2)
    assert purged == 3
    s = store.summarize("api", "baseline")
    assert s is not None
    assert s.count == 2
    assert s.max == 5.0  # only newest two (4.0, 5.0) remain
    store.close()


def test_enforce_retention_labels_are_independent(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [1.0, 2.0, 3.0, 4.0, 5.0])
    record_series(store, "api", "candidate", [1.0, 2.0])
    purged = store.enforce_retention(max_samples_per_label=2)
    assert purged == 3
    candidate = store.summarize("api", "candidate")
    assert candidate is not None
    assert candidate.count == 2
    store.close()


def test_enforce_retention_noop_under_threshold(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [1.0, 2.0])
    assert store.enforce_retention(max_samples_per_label=10) == 0
    store.close()


# ---------------------------------------------------------------------------
# purge
# ---------------------------------------------------------------------------


def test_purge_label_only(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [1.0, 2.0])
    record_series(store, "api", "candidate", [3.0])
    assert store.purge("api", "candidate") == 1
    assert store.summarize("api", "candidate") is None
    assert store.summarize("api", "baseline") is not None
    store.close()


def test_purge_whole_benchmark(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    record_series(store, "api", "baseline", [1.0, 2.0])
    record_series(store, "api", "candidate", [3.0])
    record_series(store, "batch", "baseline", [4.0])
    assert store.purge("api") == 3
    assert store.labels("api") == []
    assert store.summarize("batch", "baseline") is not None
    store.close()


def test_purge_nonexistent_returns_zero(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert store.purge("ghost") == 0
    store.close()


# ---------------------------------------------------------------------------
# record validation
# ---------------------------------------------------------------------------


def test_record_empty_benchmark_raises(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="benchmark"):
        store.record("", 1.0, label="baseline", ts="2026-01-01T00:00:00Z")
    store.close()


def test_record_empty_label_raises(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="label"):
        store.record("api", 1.0, label="   ", ts="2026-01-01T00:00:00Z")
    store.close()


def test_record_non_finite_raises(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite"):
            store.record("api", bad, label="baseline", ts="2026-01-01T00:00:00Z")
    store.close()


def test_record_negative_raises(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="non-negative"):
        store.record("api", -1.0, label="baseline", ts="2026-01-01T00:00:00Z")
    store.close()


# ---------------------------------------------------------------------------
# Context-manager protocol
# ---------------------------------------------------------------------------


def test_bench_context_manager_record_and_read() -> None:
    with BenchStore(":memory:") as store:
        store.record("api", 42.0, label="baseline", ts="2026-06-12T00:00:00Z")
        s = store.summarize("api", "baseline")
        assert s is not None
        assert s.count == 1
        assert s.max == 42.0


def test_bench_context_manager_connection_closed_after_exit() -> None:
    import sqlite3

    store = BenchStore(":memory:")
    with store:
        store.record("api", 10.0, label="baseline", ts="2026-06-12T00:00:00Z")
    with pytest.raises(sqlite3.ProgrammingError):
        store._conn.execute("SELECT 1")


def test_benchstore_sets_schema_user_version_on_fresh_store(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    version = store._conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == BenchStore.SCHEMA_VERSION
    store.close()


def test_benchstore_migrates_legacy_zero_version_without_losing_rows(tmp_path: Path) -> None:
    db = tmp_path / "bench.db"
    import sqlite3

    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE bench_samples (
            benchmark TEXT,
            label TEXT,
            value REAL,
            unit TEXT,
            run_id TEXT,
            ts TEXT
        );
        INSERT INTO bench_samples VALUES ('api', 'baseline', 42.0, 'ms', '', 't');
        """
    )
    conn.commit()
    conn.close()

    store = BenchStore(db)
    version = store._conn.execute("PRAGMA user_version").fetchone()[0]
    summary = store.summarize("api", "baseline")

    assert version == BenchStore.SCHEMA_VERSION
    assert summary is not None
    assert summary.max == 42.0
    store.close()

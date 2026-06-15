from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from workflow_core.runstore import RunStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_store(tmp_path: Path) -> RunStore:
    return RunStore(tmp_path / "runs.db")


def make_run(store: RunStore, run_id: str, **overrides: str) -> None:
    store.create_run(
        run_id,
        started_at=overrides.get("started_at", "2026-06-12T00:00:00.000000Z"),
        commit_sha=overrides.get("commit_sha", "abc123"),
        env_fingerprint=overrides.get("env_fingerprint", "fp1"),
        config_hash=overrides.get("config_hash", "cfg1"),
    )


def record_series(store: RunStore, run_id: str, metric: str, values: list[float]) -> None:
    for i, value in enumerate(values):
        store.record_sample(run_id, metric, i, value, unit="ms", recorded_at=f"t{i}")


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------


def test_create_and_get_run_roundtrip(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.create_run(
        "r1",
        started_at="2026-06-12T00:00:00.000000Z",
        task_id="task",
        worktree="/wt",
        commit_sha="sha",
        env_fingerprint="fp",
        config_hash="cfg",
        tool_versions={"abrun": "0.1.0"},
        metadata={"note": "x"},
    )
    run = store.get_run("r1")
    assert run is not None
    assert run.task_id == "task"
    assert run.commit_sha == "sha"
    assert run.tool_versions == {"abrun": "0.1.0"}
    assert run.metadata == {"note": "x"}
    store.close()


def test_get_run_missing_returns_none(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert store.get_run("nope") is None
    store.close()


def test_duplicate_run_id_rejected(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    make_run(store, "r1")
    with pytest.raises(sqlite3.IntegrityError):
        make_run(store, "r1")
    store.close()


def test_empty_run_id_rejected(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="run_id"):
        store.create_run("  ", started_at="t")
    store.close()


def test_find_cached_run_matches_newest(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    make_run(store, "old", started_at="2026-06-12T00:00:00Z")
    make_run(store, "new", started_at="2026-06-12T01:00:00Z")
    assert store.find_cached_run("abc123", "cfg1", "fp1") == "new"
    store.close()


def test_find_cached_run_requires_full_key(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    make_run(store, "r1")
    assert store.find_cached_run("abc123", "cfg1", "other") is None
    assert store.find_cached_run("", "cfg1", "fp1") is None
    store.close()


# ---------------------------------------------------------------------------
# samples -> aggregate cache
# ---------------------------------------------------------------------------


def test_sample_values_ordered_by_iteration(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    make_run(store, "r1")
    store.record_sample("r1", "m", 1, 2.0)
    store.record_sample("r1", "m", 0, 1.0)
    assert store.sample_values("r1", "m") == [1.0, 2.0]
    store.close()


def test_empty_metric_rejected(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="metric"):
        store.record_sample("r1", " ", 0, 1.0)
    store.close()


def test_aggregate_run_derives_from_samples(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    make_run(store, "r1")
    record_series(store, "r1", "lat", [float(i) for i in range(1, 101)])
    aggregates = store.aggregate_run("r1")
    assert len(aggregates) == 1
    agg = aggregates[0]
    assert agg.n_samples == 100
    assert agg.p50 == 50.0
    assert agg.p95 == 95.0
    assert agg.value == agg.p50
    assert agg.unit == "ms"
    assert agg.stddev == pytest.approx(29.0115, abs=1e-3)
    store.close()


def test_aggregate_run_is_regenerable(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    make_run(store, "r1")
    record_series(store, "r1", "lat", [10.0, 20.0, 30.0])
    first = store.aggregate_run("r1")
    store.record_sample("r1", "lat", 3, 40.0)
    second = store.aggregate_run("r1")
    assert first[0].n_samples == 3
    assert second[0].n_samples == 4
    # re-aggregation replaces, never appends
    assert len(second) == 1
    store.close()


def test_aggregate_run_empty_is_empty(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    make_run(store, "r1")
    assert store.aggregate_run("r1") == []
    store.close()


def test_metric_names_distinct_sorted(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    make_run(store, "r1")
    record_series(store, "r1", "b", [1.0])
    record_series(store, "r1", "a", [1.0, 2.0])
    assert store.metric_names("r1") == ["a", "b"]
    store.close()


# ---------------------------------------------------------------------------
# verdicts
# ---------------------------------------------------------------------------


def test_verdict_roundtrip(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_verdict(
        run_id="cand",
        baseline_run_id="base",
        metric="m",
        statistic="median",
        delta_pct=11.3,
        ci_low=4.1,
        ci_high=18.9,
        n_base=20,
        n_cand=20,
        threshold=5.0,
        result="inconclusive",
        reason="straddles",
        policy_hash="ph",
    )
    rows = store.verdicts_for_run("cand")
    assert len(rows) == 1
    assert rows[0].result == "inconclusive"
    assert rows[0].ci_low == 4.1
    assert rows[0].policy_hash == "ph"
    assert store.verdicts_for_run("base") == []
    store.close()


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------


def test_check_roundtrip(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_check(
        "r1", "test", status="fail", duration_s=1.5, command="pytest", failures=["exit 1"]
    )
    store.record_check("r1", "lint", status="pass", duration_s=0.5, command="ruff", failures=[])
    rows = store.checks_for_run("r1")
    assert [row.name for row in rows] == ["test", "lint"]
    assert rows[0].failures == ["exit 1"]
    assert rows[1].status == "pass"
    store.close()


# ---------------------------------------------------------------------------
# gate results
# ---------------------------------------------------------------------------


def test_inconclusive_gate_count_scoped(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    for result in ("inconclusive", "inconclusive", "fail"):
        store.record_gate_result(
            candidate_run_id="cand",
            baseline_run_id="base",
            policy_hash="ph",
            result=result,
            report_json="{}",
            decided_at="t",
        )
    store.record_gate_result(
        candidate_run_id="cand",
        baseline_run_id="base",
        policy_hash="other",
        result="inconclusive",
        report_json="{}",
        decided_at="t",
    )
    assert store.inconclusive_gate_count("cand", "ph") == 2
    assert store.inconclusive_gate_count("cand", "other") == 1
    assert store.inconclusive_gate_count("nope", "ph") == 0
    store.close()


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------


def test_context_manager_protocol(tmp_path: Path) -> None:
    with RunStore(tmp_path / "runs.db") as store:
        make_run(store, "r1")
        assert store.get_run("r1") is not None

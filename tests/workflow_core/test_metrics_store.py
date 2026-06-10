from __future__ import annotations

from pathlib import Path

from workflow_core.evaluation import EvalScore
from workflow_core.metrics_store import MetricsStore


def score(run_id: str, *, succeeded: bool = True, unexpected: list[str] | None = None) -> EvalScore:
    return EvalScore(
        run_id=run_id,
        succeeded=succeeded,
        event_count=4,
        tool_calls=2,
        tool_call_rate=0.5,
        skill_uses=1,
        skill_usage_rate=0.5,
        unexpected_actions=unexpected or [],
    )


def make_store(tmp_path: Path) -> MetricsStore:
    return MetricsStore(tmp_path / "eval.db")


def test_record_and_counts(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_run(score("a"), raw_trajectory='{"k":1}', created_at="2026-06-11T00:00:00Z")
    store.record_run(score("b"), raw_trajectory='{"k":2}', created_at="2026-06-11T00:00:01Z")
    assert store.raw_count() == 2
    assert store.metrics_count() == 2
    store.close()


def test_retention_purges_raw_but_keeps_structured(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    for i in range(5):
        store.record_run(
            score(f"r{i}", unexpected=["unexpected tool: WebFetch"] if i == 0 else []),
            raw_trajectory=f'{{"i":{i}}}',
            created_at=f"2026-06-11T00:00:0{i}Z",
        )
    purged = store.enforce_retention(max_raw_runs=2)
    assert purged == 3
    assert store.raw_count() == 2
    # structured metrics survive the raw purge
    assert store.metrics_count() == 5
    metrics = store.metrics()
    assert metrics[0]["run_id"] == "r0"
    assert metrics[0]["unexpected_actions"] == ["unexpected tool: WebFetch"]
    store.close()


def test_retention_noop_under_threshold(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_run(score("a"), raw_trajectory="{}", created_at="2026-06-11T00:00:00Z")
    assert store.enforce_retention(max_raw_runs=10) == 0
    store.close()


def test_aggregate_stored(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_run(score("a", succeeded=True), raw_trajectory="{}", created_at="t0")
    store.record_run(score("b", succeeded=False), raw_trajectory="{}", created_at="t1")
    report = store.aggregate_stored()
    assert report.runs == 2
    assert report.success_rate == 0.5
    store.close()

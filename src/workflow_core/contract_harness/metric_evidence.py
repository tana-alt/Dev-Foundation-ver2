from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from workflow_core.bench import BenchStore
from workflow_core.contract_harness.hashing import hash_json
from workflow_core.metrics_store import MetricsStore
from workflow_core.nfr import NfrStore


def metric_evidence(root: Path, task_id: str) -> dict[str, Any]:
    metrics_dir = root / "artifact" / task_id / "metrics"
    data = {
        "status": "absent",
        "eval": _eval_evidence(metrics_dir / "eval.db"),
        "nfr": _nfr_evidence(metrics_dir / "nfr.db"),
        "bench": _bench_evidence(metrics_dir / "bench.db"),
    }
    if data["eval"] or data["nfr"] or data["bench"]:
        data["status"] = "present"
    return data


def metric_evidence_hash(root: Path, task_id: str) -> str:
    return hash_json(metric_evidence(root, task_id))


def _eval_evidence(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with MetricsStore(path) as store:
        rows = store.metrics()
        report = store.aggregate_stored()
        tool_stats = store.tool_stats()
    if not rows:
        return {}
    return {
        "runs": report.runs,
        "success_rate": report.success_rate,
        "tool_calls": sum(int(str(row["tool_calls"])) for row in rows),
        "tool_call_rate": report.mean_tool_call_rate,
        "skill_uses": sum(int(str(row["skill_uses"])) for row in rows),
        "skill_usage_rate": report.mean_skill_usage_rate,
        "unexpected_actions": sorted(
            {item for row in rows for item in cast(list[str], row["unexpected_actions"])}
        ),
        "tool_stats": [item.model_dump() for item in tool_stats],
    }


def _nfr_evidence(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with NfrStore(path) as store:
        return [
            summary.model_dump()
            for metric in store.metrics()
            if (summary := store.summarize(metric)) is not None
        ]


def _bench_evidence(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with BenchStore(path) as store:
        for benchmark in store.benchmarks():
            labels = [
                summary.model_dump()
                for label in store.labels(benchmark)
                if (summary := store.summarize(benchmark, label)) is not None
            ]
            comparison = store.compare(benchmark)
            rows.append(
                {
                    "benchmark": benchmark,
                    "labels": labels,
                    "comparison": comparison.model_dump() if comparison is not None else None,
                }
            )
    return rows

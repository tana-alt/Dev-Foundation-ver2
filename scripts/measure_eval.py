#!/usr/bin/env python3
"""Eval measurement over hook-recorded trajectories (no SDK).

Scans artifact/<project>/trajectory/*.jsonl, scores each run, accumulates the
structured signals plus the raw JSONL into the retention store (raw ages out,
signals persist), records per-tool/skill tallies, and prints the aggregate.
Ingested trajectory files beyond FOUNDATION_TRAJ_MAX_FILES are deleted -- their
raw content lives on in the store's purgeable tier. Supply
Plan/<project>/eval-envelope.json to turn on unexpected-action detection;
otherwise each run is measured against its own observed envelope (counting
only).

Env: FOUNDATION_PROJECT_ID, FOUNDATION_REPO_ROOT,
FOUNDATION_EVAL_MAX_RAW (default 50), FOUNDATION_TRAJ_MAX_FILES (default 50).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _measure_into_store(
    traj_dir: Path, store: Any, fixed_envelope: Any
) -> tuple[list[Any], list[str]]:
    from datetime import UTC, datetime

    from workflow_core.evaluation import tool_usage
    from workflow_core.measure import default_envelope, load_trajectory, measure_trajectory

    scores: list[Any] = []
    ingested: list[str] = []
    for path in sorted(traj_dir.glob("*.jsonl")):
        raw = path.read_text(encoding="utf-8")
        events = load_trajectory(path)
        if not events:
            continue
        envelope = fixed_envelope or default_envelope(events)
        score = measure_trajectory(path.stem, events, envelope)
        scores.append(score)
        created_at = datetime.fromtimestamp(path.stat().st_mtime, UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        store.record_run(score, raw_trajectory=raw, created_at=created_at)
        store.record_tool_usage(path.stem, tool_usage(events))
        ingested.append(path.stem)
        if score.unexpected_actions:
            print(f"- {path.stem}: unexpected={score.unexpected_actions}")
    return scores, ingested


def main() -> int:
    from workflow_core.evaluation import ExpectedEnvelope, aggregate
    from workflow_core.measure import prune_trajectory_files
    from workflow_core.metrics_store import MetricsStore

    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    traj_dir = root / "artifact" / project / "trajectory"
    if not traj_dir.is_dir():
        print(f"measure-eval: no trajectories at {traj_dir.relative_to(root)}")
        return 0

    envelope_path = root / "Plan" / project / "eval-envelope.json"
    fixed_envelope: ExpectedEnvelope | None = None
    if envelope_path.is_file():
        fixed_envelope = ExpectedEnvelope.model_validate_json(envelope_path.read_text("utf-8"))

    store = MetricsStore(root / "artifact" / project / "metrics" / "eval.db")
    scores, ingested = _measure_into_store(traj_dir, store, fixed_envelope)
    purged = store.enforce_retention(
        max_raw_runs=int(os.environ.get("FOUNDATION_EVAL_MAX_RAW", "50"))
    )
    max_files = int(os.environ.get("FOUNDATION_TRAJ_MAX_FILES", "50"))
    pruned = prune_trajectory_files(traj_dir, keep=max_files, ingested=ingested)
    print(
        json.dumps(
            {
                "report": aggregate(scores).model_dump(),
                "runs_measured": len(scores),
                "structured_metrics_kept": store.metrics_count(),
                "raw_purged": purged,
                "trajectory_files_pruned": len(pruned),
                "tool_stats": [stat.model_dump() for stat in store.tool_stats()],
                "envelope": "fixed" if fixed_envelope else "per-run-default",
            },
            indent=2,
            sort_keys=True,
        )
    )
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

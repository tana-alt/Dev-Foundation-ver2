#!/usr/bin/env python3
"""Eval measurement over hook-recorded trajectories (no SDK).

Scans artifact/<project>/trajectory/*.jsonl, scores each run, accumulates the
structured signals into the retention store (raw ages out, signals persist), and
prints the aggregate. Supply Plan/<project>/eval-envelope.json to turn on
unexpected-action detection; otherwise each run is measured against its own
observed envelope (counting only).

Env: FOUNDATION_PROJECT_ID, FOUNDATION_REPO_ROOT, FOUNDATION_EVAL_MAX_RAW (default 50).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from workflow_core.evaluation import ExpectedEnvelope, aggregate
    from workflow_core.measure import default_envelope, load_trajectory, measure_trajectory
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
    scores = []
    for path in sorted(traj_dir.glob("*.jsonl")):
        events = load_trajectory(path)
        if not events:
            continue
        envelope = fixed_envelope or default_envelope(events)
        score = measure_trajectory(path.stem, events, envelope)
        scores.append(score)
        store.record_run(score, raw_trajectory="", created_at=path.stem)
        if score.unexpected_actions:
            print(f"- {path.stem}: unexpected={score.unexpected_actions}")

    max_raw = int(os.environ.get("FOUNDATION_EVAL_MAX_RAW", "50"))
    purged = store.enforce_retention(max_raw_runs=max_raw)
    report = aggregate(scores)
    print(
        json.dumps(
            {
                "report": report.model_dump(),
                "runs_measured": len(scores),
                "structured_metrics_kept": store.metrics_count(),
                "raw_purged": purged,
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

#!/usr/bin/env python3
"""Agent-facing CLI for quantitative NFR evaluation (latency budgets etc.).

Samples land in artifact/<project>/metrics/nfr.db -- a temporary store, not a
durable record. Typical loop: the agent times an operation, `record`s samples,
`evaluate`s the distribution against a budget (exit code 1 on a missed budget,
so it can sit in a gate), copies the verdict into evidence or the plan log, and
`purge`s the metric. Retention also ages out old samples by count.

Usage:
  nfr_metric.py record <metric> <value> [--unit ms] [--run-id ID]
  nfr_metric.py summary [<metric>]
  nfr_metric.py evaluate <metric> --threshold X [--statistic p50|p95|max|mean]
  nfr_metric.py purge <metric>

Exit codes for evaluate: 0 budget met, 1 budget missed, 2 no samples yet
(cold start is distinguishable from a miss for CI callers).

Env: FOUNDATION_PROJECT_ID, FOUNDATION_REPO_ROOT,
FOUNDATION_NFR_MAX_SAMPLES (default 1000, applied on record).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    record = commands.add_parser("record", help="append one sample")
    record.add_argument("metric")
    record.add_argument("value", type=float)
    record.add_argument("--unit", default="ms")
    record.add_argument("--run-id", default="")

    summary = commands.add_parser("summary", help="print distribution summaries")
    summary.add_argument("metric", nargs="?")

    evaluate = commands.add_parser("evaluate", help="check a budget; exit 1 when missed")
    evaluate.add_argument("metric")
    evaluate.add_argument("--threshold", type=float, required=True)
    evaluate.add_argument("--statistic", choices=("p50", "p95", "max", "mean"), default="p95")

    purge = commands.add_parser("purge", help="drop all samples of a metric")
    purge.add_argument("metric")
    return parser


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from datetime import UTC, datetime

    from workflow_core.env import env_int
    from workflow_core.nfr import NfrStore

    args = build_parser().parse_args(argv)
    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    with NfrStore(root / "artifact" / project / "metrics" / "nfr.db") as store:
        if args.command == "record":
            # Microsecond precision: NFR samples can land many per second and
            # retention drops the oldest by ts.
            ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            store.record(args.metric, args.value, ts=ts, unit=args.unit, run_id=args.run_id)
            max_samples = env_int("FOUNDATION_NFR_MAX_SAMPLES", 1000)
            store.enforce_retention(max_samples_per_metric=max_samples)
            return 0
        if args.command == "summary":
            names = [args.metric] if args.metric else store.metrics()
            summaries = [s.model_dump() for n in names if (s := store.summarize(n))]
            print(json.dumps(summaries, indent=2, sort_keys=True))
            return 0
        if args.command == "evaluate":
            verdict = store.evaluate(
                args.metric, threshold=args.threshold, statistic=args.statistic
            )
            if verdict is None:
                print(f"nfr: no samples for metric '{args.metric}'")
                return 2
            print(json.dumps(verdict.model_dump(), indent=2, sort_keys=True))
            return 0 if verdict.passed else 1
        removed = store.purge_metric(args.metric)
        print(f"nfr: purged {removed} sample(s) of '{args.metric}'")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

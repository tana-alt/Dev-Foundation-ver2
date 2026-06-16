#!/usr/bin/env python3
"""Agent-facing CLI for benchmark comparison (speed-up vs baseline).

Samples land in artifact/<project>/metrics/bench.db, namespaced by
(benchmark, label). Typical loop: capture the pre-change distribution under
the label "baseline" (`run` or `record`), implement the optimization, capture
"candidate", then `compare` and copy the comparison into evidence or the plan
log before purging stale labels.

Usage:
  bench_compare.py run <benchmark> --label NAME [--repeat 5] [--warmup 1]
      [--run-id ID] -- <command...>
  bench_compare.py record <benchmark> <value> --label NAME [--unit ms] [--run-id ID]
  bench_compare.py summary [<benchmark>] [--label NAME]
  bench_compare.py compare <benchmark> [--baseline baseline] [--candidate candidate]
      [--statistic p50|p95|max|mean] [--min-change-pct 3.0] [--min-improvement-pct X]
  bench_compare.py purge <benchmark> [--label NAME]

`run` executes the command repeat times (after discarded warmup iterations)
and records wall-clock milliseconds; nothing is recorded unless every
iteration exits 0, so a broken command cannot skew a comparison. Place `run`
options before the `--` separator.

Exit codes (R6 convention -- see docs/reference/exit-codes-reference.md):
  0  no regression (and any required improvement met)
  1  regressed or --min-improvement-pct missed
  2  reserved for inconclusive (unused here)
  3  missing samples on either side or tool error (bad arguments, broken command)

Env: FOUNDATION_PROJECT_ID, FOUNDATION_REPO_ROOT,
FOUNDATION_BENCH_MAX_SAMPLES (default 1000, applied on record/run),
FOUNDATION_BENCH_TIMEOUT_S (default 60, per measured iteration).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workflow_core.bench import BenchStore


def build_parser() -> argparse.ArgumentParser:
    from workflow_core.cli import R6ArgumentParser

    parser = R6ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="time a command (after --) and record its samples")
    run.add_argument("benchmark")
    run.add_argument("--label", required=True)
    run.add_argument("--repeat", type=int, default=5)
    run.add_argument("--warmup", type=int, default=1)
    run.add_argument("--run-id", default="")
    run.add_argument("--timeout-s", type=float, default=None)

    record = commands.add_parser("record", help="append one externally measured sample")
    record.add_argument("benchmark")
    record.add_argument("value", type=float)
    record.add_argument("--label", required=True)
    record.add_argument("--unit", default="ms")
    record.add_argument("--run-id", default="")

    summary = commands.add_parser("summary", help="print distribution summaries")
    summary.add_argument("benchmark", nargs="?")
    summary.add_argument("--label")

    compare = commands.add_parser("compare", help="judge candidate vs baseline; exit 1 on regress")
    compare.add_argument("benchmark")
    compare.add_argument("--baseline", default="baseline")
    compare.add_argument("--candidate", default="candidate")
    compare.add_argument("--statistic", choices=("p50", "p95", "max", "mean"), default="p50")
    compare.add_argument("--min-change-pct", type=float, default=3.0)
    compare.add_argument("--min-improvement-pct", type=float, default=None)

    purge = commands.add_parser("purge", help="drop a label or a whole benchmark")
    purge.add_argument("benchmark")
    purge.add_argument("--label")
    return parser


def _now_ts() -> str:
    # Microsecond precision: samples can land many per second and retention
    # drops the oldest by ts.
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _record_samples(
    store: BenchStore, benchmark: str, label: str, samples: list[float], *, unit: str, run_id: str
) -> None:
    from workflow_core.env import env_int

    for value in samples:
        store.record(benchmark, value, label=label, ts=_now_ts(), unit=unit, run_id=run_id)
    max_samples = env_int("FOUNDATION_BENCH_MAX_SAMPLES", 1000)
    store.enforce_retention(max_samples_per_label=max_samples)


def _measure_command(
    command: list[str],
    *,
    repeat: int,
    warmup: int,
    timeout_s: float,
) -> list[float] | None:
    """Wall-clock samples in ms, or None when an iteration fails."""
    samples: list[float] = []
    for i in range(warmup + repeat):
        started = time.perf_counter()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            print(
                f"bench: iteration {i + 1} timed out after {timeout_s:g}s; "
                f"elapsed {elapsed_ms:.1f}ms; nothing recorded",
                file=sys.stderr,
            )
            return None
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if proc.returncode != 0:
            tail = proc.stderr.strip().splitlines()[-3:]
            print(
                f"bench: iteration {i + 1} exited {proc.returncode}; nothing recorded\n"
                + "\n".join(tail),
                file=sys.stderr,
            )
            return None
        if i >= warmup:
            samples.append(round(elapsed_ms, 4))
    return samples


def _cmd_run(args: argparse.Namespace, store: BenchStore) -> int:
    from workflow_core.env import env_float

    command = list(args.cmd)
    if not command:
        print("bench: run needs a command after --", file=sys.stderr)
        return 3
    if args.repeat < 1 or args.warmup < 0:
        print("bench: --repeat must be >= 1 and --warmup >= 0", file=sys.stderr)
        return 3
    timeout_s = (
        args.timeout_s
        if args.timeout_s is not None
        else env_float("FOUNDATION_BENCH_TIMEOUT_S", 60.0)
    )
    if timeout_s <= 0:
        print("bench: --timeout-s must be > 0", file=sys.stderr)
        return 3
    samples = _measure_command(
        command,
        repeat=args.repeat,
        warmup=args.warmup,
        timeout_s=timeout_s,
    )
    if samples is None:
        return 3
    _record_samples(store, args.benchmark, args.label, samples, unit="ms", run_id=args.run_id)
    summary = store.summarize(args.benchmark, args.label)
    assert summary is not None  # just recorded
    print(json.dumps(summary.model_dump(), indent=2, sort_keys=True))
    return 0


def _cmd_record(args: argparse.Namespace, store: BenchStore) -> int:
    _record_samples(
        store, args.benchmark, args.label, [args.value], unit=args.unit, run_id=args.run_id
    )
    return 0


def _cmd_summary(args: argparse.Namespace, store: BenchStore) -> int:
    names = [args.benchmark] if args.benchmark else store.benchmarks()
    summaries = []
    for name in names:
        labels = [args.label] if args.label else store.labels(name)
        summaries.extend(
            summary.model_dump() for label in labels if (summary := store.summarize(name, label))
        )
    print(json.dumps(summaries, indent=2, sort_keys=True))
    return 0


def _cmd_compare(args: argparse.Namespace, store: BenchStore) -> int:
    comparison = store.compare(
        args.benchmark,
        baseline=args.baseline,
        candidate=args.candidate,
        statistic=args.statistic,
        min_change_pct=args.min_change_pct,
    )
    if comparison is None:
        print(
            f"bench: need samples for both '{args.baseline}' and '{args.candidate}' "
            f"of '{args.benchmark}'"
        )
        return 3
    print(json.dumps(comparison.model_dump(), indent=2, sort_keys=True))
    if comparison.verdict == "regressed":
        return 1
    required = args.min_improvement_pct
    if required is not None and comparison.improvement_pct < required:
        return 1
    return 0


def _cmd_purge(args: argparse.Namespace, store: BenchStore) -> int:
    removed = store.purge(args.benchmark, args.label)
    scope = f"label '{args.label}'" if args.label else "all labels"
    print(f"bench: purged {removed} sample(s) of '{args.benchmark}' ({scope})")
    return 0


def _split_on_dashdash(argv: list[str]) -> tuple[list[str], list[str]]:
    """Everything after the first `--` is the measured command, kept verbatim.

    Splitting before argparse sidesteps the REMAINDER quirk where options
    placed after the positional would be swallowed into the command.
    """
    if "--" in argv:
        index = argv.index("--")
        return argv[:index], argv[index + 1 :]
    return argv, []


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from workflow_core.bench import BenchStore

    raw = list(sys.argv[1:] if argv is None else argv)
    head, command = _split_on_dashdash(raw)
    args = build_parser().parse_args(head)
    args.cmd = command
    if command and args.command != "run":
        print(f"bench: a -- command only applies to run, not {args.command}", file=sys.stderr)
        return 3
    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    handlers = {
        "run": _cmd_run,
        "record": _cmd_record,
        "summary": _cmd_summary,
        "compare": _cmd_compare,
        "purge": _cmd_purge,
    }
    with BenchStore(root / "artifact" / project / "metrics" / "bench.db") as store:
        return handlers[args.command](args, store)


if __name__ == "__main__":
    raise SystemExit(main())

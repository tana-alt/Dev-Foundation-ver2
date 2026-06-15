#!/usr/bin/env python3
"""AB execution orchestrator CLI (Plan-N0002 R3).

Prepares baseline/candidate worktrees from a JSON config, measures them in an
ABAB interleave, and records runs + raw samples in
artifact/<project>/metrics/runs.db. Output is JSON with both run ids — feed
them to scripts/verdict.py or scripts/quality_gate.py.

Usage:
  abrun.py run --config ab.json [--repo PATH] [--no-cache]
  abrun.py aggregate --run RUN_ID
  abrun.py clean --config ab.json [--repo PATH]

Config shape (see docs/reference/harness-observability-reference.md):
  {"baseline": {"ref": "main", "worktree": "../worktrees/<repo>/ab-base"},
   "candidate": {"ref": "HEAD", "worktree": "../worktrees/<repo>/ab-cand"},
   "setup": ["uv sync --frozen"],
   "measure": {"tool": "command", "command": ["python3", "bench.py"],
               "metric": "bench.core.wall_ms", "value_from": "wallclock"},
   "iterations": 20, "warmup": 3, "schedule": "interleaved"}

Worktree paths must resolve OUTSIDE the measured repo; abrun refuses
repo-internal worktrees and `clean` removes only worktrees abrun created
(identified by the .abrun-worktree marker). Matching (commit_sha,
config_hash, env_fingerprint) reuses the cached run unless --no-cache.

Exit codes (R6): 0 ok, 3 tool error (bad config, git/setup/measure failure).
Env: FOUNDATION_REPO_ROOT, FOUNDATION_PROJECT_ID, FOUNDATION_TRACE_PATH
(optional JSONL trace destination), FOUNDATION_SESSION_ID.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workflow_core.runstore import RunStore
    from workflow_core.tracelog import TraceWriter


def build_parser() -> argparse.ArgumentParser:
    from workflow_core.cli import R6ArgumentParser

    parser = R6ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="prepare worktrees, measure, record runs")
    run.add_argument("--config", required=True)
    run.add_argument("--repo", default="")
    run.add_argument("--no-cache", action="store_true")
    aggregate = commands.add_parser("aggregate", help="regenerate the metrics cache for a run")
    aggregate.add_argument("--run", required=True)
    clean = commands.add_parser("clean", help="remove abrun-owned worktrees")
    clean.add_argument("--config", required=True)
    clean.add_argument("--repo", default="")
    return parser


def _trace() -> TraceWriter | None:
    raw = os.environ.get("FOUNDATION_TRACE_PATH", "")
    if not raw.strip():
        return None
    from workflow_core.tracelog import TraceWriter

    session = os.environ.get("FOUNDATION_SESSION_ID", "local")
    return TraceWriter(raw, session_id=session, actor="abrun")


def _cmd_run(args: argparse.Namespace, store: RunStore, repo: Path) -> int:
    from workflow_core import abrun

    config, config_hash = abrun.load_config(Path(args.config))
    result = abrun.orchestrate(
        repo, store, config, config_hash, no_cache=args.no_cache, trace=_trace()
    )
    print(json.dumps(result.model_dump(), indent=2, sort_keys=True))
    return 0


def _cmd_aggregate(args: argparse.Namespace, store: RunStore, repo: Path) -> int:
    aggregates = store.aggregate_run(args.run)
    print(json.dumps([a.model_dump() for a in aggregates], indent=2, sort_keys=True))
    return 0


def _cmd_clean(args: argparse.Namespace, store: RunStore, repo: Path) -> int:
    from workflow_core import abrun

    config, _ = abrun.load_config(Path(args.config))
    removed = abrun.clean(repo, config)
    print(json.dumps({"removed": removed}, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from workflow_core.abrun import AbrunError
    from workflow_core.cli import EXIT_TOOL_ERROR
    from workflow_core.runstore import RunStore

    args = build_parser().parse_args(argv)
    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    repo = Path(args.repo).resolve() if getattr(args, "repo", "") else root
    handlers = {"run": _cmd_run, "aggregate": _cmd_aggregate, "clean": _cmd_clean}
    try:
        with RunStore(root / "artifact" / project / "metrics" / "runs.db") as store:
            return handlers[args.command](args, store, repo)
    except AbrunError as exc:
        print(f"abrun: {exc}", file=sys.stderr)
        return EXIT_TOOL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())

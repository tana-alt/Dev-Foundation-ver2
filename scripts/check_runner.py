#!/usr/bin/env python3
"""Functional-correctness gate runner CLI (Plan-N0002 R4).

Runs the configured verification commands (test / lint / typecheck / build)
inside a worktree and records structured results in
artifact/<project>/metrics/runs.db; quality_gate.py reads them back as the
`check` condition. Performance comparison presupposes a functionally correct
candidate — this tool mechanizes that precondition. If --run-id does not
exist yet a minimal run row is created, so check also works standalone.

Usage:
  check_runner.py run --run-id ID --worktree PATH (--cmd name=command)...
      [--config FILE] [--timeout SECONDS]

--config FILE is JSON: {"commands": {"test": "uv run pytest", ...}};
--cmd entries are appended after config entries and use name=command form.

Exit codes (R6): 0 all checks pass, 1 at least one check failed,
3 tool error (no commands, bad config, missing worktree).

Env: FOUNDATION_REPO_ROOT, FOUNDATION_PROJECT_ID.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workflow_core.runstore import RunStore


def build_parser() -> argparse.ArgumentParser:
    from workflow_core.cli import R6ArgumentParser

    parser = R6ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run checks in a worktree and record results")
    run.add_argument("--run-id", required=True)
    run.add_argument("--worktree", required=True)
    run.add_argument("--cmd", action="append", default=[])
    run.add_argument("--config", default="")
    run.add_argument("--timeout", type=float, default=1800.0)
    return parser


def _load_commands(args: argparse.Namespace) -> list[tuple[str, str]]:
    commands: list[tuple[str, str]] = []
    if args.config:
        data = json.loads(Path(args.config).read_text(encoding="utf-8"))
        for name, command in dict(data.get("commands", {})).items():
            commands.append((str(name), str(command)))
    for raw in args.cmd:
        name, sep, command = raw.partition("=")
        if not sep or not name.strip() or not command.strip():
            raise ValueError(f"--cmd needs name=command, got {raw!r}")
        commands.append((name.strip(), command.strip()))
    return commands


def _now_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _cmd_run(args: argparse.Namespace, store: RunStore) -> int:
    from workflow_core.checkrun import record_report, run_checks
    from workflow_core.cli import EXIT_FAIL, EXIT_PASS, EXIT_TOOL_ERROR

    try:
        commands = _load_commands(args)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"check: {exc}", file=sys.stderr)
        return EXIT_TOOL_ERROR
    if not commands:
        print("check: no commands configured (use --cmd or --config)", file=sys.stderr)
        return EXIT_TOOL_ERROR
    worktree = Path(args.worktree)
    if not worktree.is_dir():
        print(f"check: worktree {worktree} is not a directory", file=sys.stderr)
        return EXIT_TOOL_ERROR
    report = run_checks(commands, cwd=worktree, timeout=args.timeout)
    if store.get_run(args.run_id) is None:
        store.create_run(args.run_id, started_at=_now_ts(), worktree=str(worktree))
    record_report(store, args.run_id, report)
    print(json.dumps(report.to_payload(), indent=2, sort_keys=True))
    return EXIT_PASS if report.overall == "pass" else EXIT_FAIL


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from workflow_core.runstore import RunStore

    args = build_parser().parse_args(argv)
    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    with RunStore(root / "artifact" / project / "metrics" / "runs.db") as store:
        return _cmd_run(args, store)


if __name__ == "__main__":
    raise SystemExit(main())

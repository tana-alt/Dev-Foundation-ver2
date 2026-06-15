#!/usr/bin/env python3
"""Policy-aggregation gate CLI (Plan-N0002 R5).

Evaluates every condition in a policy file — functional checks plus
statistical verdicts — against a baseline/candidate run pair from
artifact/<project>/metrics/runs.db and reduces them to one result and one
exit code: the agent's single final branch point.

Usage:
  quality_gate.py evaluate --policy FILE --baseline-run ID --candidate-run ID
      [--resamples N] [--seed N]

Policy files must live inside FOUNDATION_POLICY_DIR (default
<root>/.agents/policies); thresholds are accepted from nowhere else (R12).
`on_inconclusive` in the policy decides what happens when a verdict cannot
be called: retry_then_fail (exit 2 while retries remain), fail, or
pass_with_warning.

Exit codes (R6): 0 pass (warnings possible), 1 fail (regression, failing
check, or inconclusive per policy), 2 inconclusive (re-measure; retries
remain), 3 tool error (bad policy, missing runs or check data).

Env: FOUNDATION_REPO_ROOT, FOUNDATION_PROJECT_ID, FOUNDATION_POLICY_DIR,
FOUNDATION_TRACE_PATH (optional JSONL trace), FOUNDATION_SESSION_ID.
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
    from workflow_core.quality_gate import GateReport
    from workflow_core.runstore import RunStore


def build_parser() -> argparse.ArgumentParser:
    from workflow_core.cli import R6ArgumentParser

    parser = R6ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("evaluate", help="evaluate all policy conditions")
    evaluate.add_argument("--policy", required=True)
    evaluate.add_argument("--baseline-run", required=True)
    evaluate.add_argument("--candidate-run", required=True)
    evaluate.add_argument("--resamples", type=int, default=10_000)
    evaluate.add_argument("--seed", type=int, default=20260612)
    return parser


def _now_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _emit_trace(report: GateReport) -> None:
    raw = os.environ.get("FOUNDATION_TRACE_PATH", "")
    if not raw.strip():
        return
    from workflow_core.tracelog import TraceWriter

    writer = TraceWriter(
        raw, session_id=os.environ.get("FOUNDATION_SESSION_ID", "local"), actor="gate"
    )
    writer.emit(
        "gate_result",
        {"result": report.result, "warnings": report.warnings},
        {"run_id": report.candidate_run_id, "policy_hash": report.policy_hash},
    )


def _cmd_evaluate(args: argparse.Namespace, store: RunStore, root: Path) -> int:
    from workflow_core.cli import EXIT_FAIL, EXIT_INCONCLUSIVE, EXIT_PASS, EXIT_TOOL_ERROR
    from workflow_core.policy import allowed_policy_dir, load_policy
    from workflow_core.quality_gate import evaluate_gate

    policy, policy_hash = load_policy(Path(args.policy), allowed_dir=allowed_policy_dir(root))
    report = evaluate_gate(
        store,
        policy,
        policy_hash,
        baseline_run_id=args.baseline_run,
        candidate_run_id=args.candidate_run,
        decided_at=_now_ts(),
        resamples=args.resamples,
        seed=args.seed,
    )
    _emit_trace(report)
    print(json.dumps({"tool": "gate", **report.model_dump()}, indent=2, sort_keys=True))
    codes = {"pass": EXIT_PASS, "fail": EXIT_FAIL, "inconclusive": EXIT_INCONCLUSIVE}
    return codes.get(report.result, EXIT_TOOL_ERROR)


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from workflow_core.cli import EXIT_TOOL_ERROR
    from workflow_core.policy import PolicyError
    from workflow_core.runstore import RunStore

    args = build_parser().parse_args(argv)
    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    try:
        with RunStore(root / "artifact" / project / "metrics" / "runs.db") as store:
            return _cmd_evaluate(args, store, root)
    except PolicyError as exc:
        print(f"gate: {exc}", file=sys.stderr)
        return EXIT_TOOL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())

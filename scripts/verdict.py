#!/usr/bin/env python3
"""Statistical comparison verdict CLI (Plan-N0002 R2).

Judges a candidate run against a baseline run from raw samples in
artifact/<project>/metrics/runs.db: MAD outlier filter, seeded percentile
bootstrap of the relative delta, four-valued result (pass / regression /
inconclusive / error). Thresholds come ONLY from a policy file (R12): the
first non-check condition matching --metric supplies mode, threshold_pct,
and the default statistic.

Usage:
  verdict.py compare --baseline-run ID --candidate-run ID --metric NAME
      --policy FILE [--statistic median|p50|p95|max|mean]
      [--resamples N] [--seed N]

Exit codes (R6): 0 pass, 1 regression, 2 inconclusive (re-measure;
suggested_additional_iterations is in the JSON output), 3 tool error
(insufficient samples, zero baseline, bad policy or arguments).

Env: FOUNDATION_REPO_ROOT, FOUNDATION_PROJECT_ID, FOUNDATION_POLICY_DIR
(default <root>/.agents/policies).
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
    from workflow_core.verdict import VerdictOutcome


def build_parser() -> argparse.ArgumentParser:
    from workflow_core.cli import R6ArgumentParser

    parser = R6ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    compare = commands.add_parser("compare", help="judge candidate vs baseline samples")
    compare.add_argument("--baseline-run", required=True)
    compare.add_argument("--candidate-run", required=True)
    compare.add_argument("--metric", required=True)
    compare.add_argument("--policy", required=True)
    compare.add_argument("--statistic", choices=("median", "p50", "p95", "max", "mean"), default="")
    compare.add_argument("--resamples", type=int, default=10_000)
    compare.add_argument("--seed", type=int, default=20260612)
    return parser


def _fingerprint_warnings(store: RunStore, baseline_run: str, candidate_run: str) -> list[str]:
    base, cand = store.get_run(baseline_run), store.get_run(candidate_run)
    if (
        base is not None
        and cand is not None
        and base.env_fingerprint
        and cand.env_fingerprint
        and base.env_fingerprint != cand.env_fingerprint
    ):
        return [f"env_fingerprint mismatch between {baseline_run} and {candidate_run} (R13)"]
    return []


def _emit(args: argparse.Namespace, outcome: VerdictOutcome) -> None:
    repro = (
        f"verdict compare --baseline-run {args.baseline_run}"
        f" --candidate-run {args.candidate_run}"
        f" --metric {args.metric} --policy {args.policy}"
    )
    payload = {
        "tool": "verdict",
        **outcome.model_dump(),
        "baseline_run_id": args.baseline_run,
        "candidate_run_id": args.candidate_run,
        "ci": [outcome.ci_low, outcome.ci_high],
        "repro": repro,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def _cmd_compare(args: argparse.Namespace, store: RunStore, root: Path) -> int:
    from workflow_core import verdict as verdict_mod
    from workflow_core.cli import EXIT_FAIL, EXIT_INCONCLUSIVE, EXIT_PASS, EXIT_TOOL_ERROR
    from workflow_core.policy import allowed_policy_dir, condition_for_metric, load_policy

    policy, policy_hash = load_policy(Path(args.policy), allowed_dir=allowed_policy_dir(root))
    condition = condition_for_metric(policy, args.metric)
    if condition is None or condition.mode is None or condition.threshold_pct is None:
        print(
            f"verdict: policy has no usable (mode + threshold_pct) condition"
            f" for metric {args.metric!r}",
            file=sys.stderr,
        )
        return EXIT_TOOL_ERROR
    outcome = verdict_mod.compare(
        store.sample_values(args.baseline_run, args.metric),
        store.sample_values(args.candidate_run, args.metric),
        mode=condition.mode,
        threshold_pct=condition.threshold_pct,
        metric=args.metric,
        statistic=args.statistic or condition.statistic,
        resamples=args.resamples,
        seed=args.seed,
        warnings=_fingerprint_warnings(store, args.baseline_run, args.candidate_run),
    )
    store.record_verdict(
        run_id=args.candidate_run,
        baseline_run_id=args.baseline_run,
        metric=args.metric,
        statistic=outcome.statistic,
        delta_pct=outcome.delta_pct,
        ci_low=outcome.ci_low,
        ci_high=outcome.ci_high,
        n_base=outcome.n_base,
        n_cand=outcome.n_cand,
        threshold=condition.threshold_pct,
        result=outcome.result,
        reason=outcome.reason,
        policy_hash=policy_hash,
    )
    _emit(args, outcome)
    codes = {"pass": EXIT_PASS, "regression": EXIT_FAIL, "inconclusive": EXIT_INCONCLUSIVE}
    return codes.get(outcome.result, EXIT_TOOL_ERROR)


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
            return _cmd_compare(args, store, root)
    except (PolicyError, ValueError) as exc:
        print(f"verdict: {exc}", file=sys.stderr)
        return EXIT_TOOL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())

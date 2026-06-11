# Harness Observability And Quantitative Eval Reference

Open this only for hook-based monitoring, the metrics store, issue surfacing,
or quantitative NFR evaluation.

## Observe-Mode Pipeline

Wire `templates/claude-hooks-settings.json` (or the Codex equivalent) to turn a
normal agent session into a recorded run:

- `SessionStart` -> `scripts/hook_session_start.py` replays open issues into
  the session context.
- `PostToolUse` -> `scripts/hook_post_tool_use.py` appends one normalized
  `TrajectoryEvent` per tool call to
  `artifact/<project>/trajectory/<session>.jsonl`.
- `Stop` -> `scripts/hook_stop.py` re-runs the completion gate for plan-gated
  work and blocks the stop on failure.

Gating is plan-based: a project loops when `Plan/<project>/plans/` holds an
active `Plan_N000X.md` record (status from `index.yaml`; see
`src/workflow_core/plans.py`). `FOUNDATION_SPEC_PRESENT=1` forces gating;
unplanned work stays single-pass.

Hook robustness contract: hooks run under plain `python3` (no venv). The
PostToolUse recorder and the gating decision are stdlib-only
(`workflow_core.hook_events.event_dict_from_post_tool_use`,
`workflow_core.plans`; the package `__init__` resolves exports lazily so
those imports never pull pydantic). The Stop hook's verdict path needs
pydantic; when it is missing, or `make` exceeds `FOUNDATION_GATE_TIMEOUT_S`
(default 900), the hook fails open -- stderr note, exit 0 -- so an
environment problem never traps the session. Numeric `FOUNDATION_*` knobs
parse via `workflow_core.env` and fall back to their defaults (with a stderr
warning) on malformed values.

## Measurement And Retention (make measure)

`scripts/measure_eval.py` scores every recorded trajectory and accumulates
signals into sqlite at `artifact/<project>/metrics/eval.db`:

- Kept tiers: `run_metrics` (success, rates, unexpected actions) and
  `tool_usage` (per-run call/failure tallies per tool and skill).
- Purgeable tier: `raw_runs` holds the raw trajectory JSONL; the oldest rows
  beyond `FOUNDATION_EVAL_MAX_RAW` (default 50) are deleted.
- Ingested trajectory files beyond `FOUNDATION_TRAJ_MAX_FILES` (default 50)
  are removed from disk -- raw data lives in exactly one tier at a time.

Supply `Plan/<project>/eval-envelope.json` (an `ExpectedEnvelope`) to detect
out-of-envelope tools, writes, and skills as `unexpected_actions`.

## Issue Surfacing (make issues)

`scripts/surface_issues.py` reads the store, derives issues, and writes
`artifact/<project>/metrics/open-issues.{json,md}`:

- success rate below `FOUNDATION_ISSUE_SUCCESS_RATE` (default 0.8),
- per-tool/skill failure rate above `FOUNDATION_ISSUE_FAILURE_RATE`
  (default 0.3) once calls reach `FOUNDATION_ISSUE_MIN_CALLS` (default 5),
- any runs with unexpected actions.

The SessionStart hook prints these at the start of every session, so problems
recur until a fresh `make measure && make issues` clears them. Schedule that
pair (cron or a recurring agent) for periodic surfacing.

## Quantitative NFR Evaluation (scripts/nfr_metric.py)

Non-functional budgets become measurements: record samples into the temporary
store `artifact/<project>/metrics/nfr.db`, then evaluate the distribution.

```sh
python3 scripts/nfr_metric.py record api_latency 142.5 --unit ms
python3 scripts/nfr_metric.py evaluate api_latency --threshold 200 --statistic p95
```

`evaluate` prints the verdict (p50/p95/max/mean vs threshold) and exits 1 on a
missed budget, so it can sit inside a verification gate (exit 2 means no
samples yet -- cold start, not a miss). Copy the verdict into
evidence or the plan log, then `purge` the metric; retention also ages out
samples beyond `FOUNDATION_NFR_MAX_SAMPLES` (default 1000) per metric.
`make nfr-summary` prints all current distributions.

## Code Quality Budgets

Beyond types: ruff enforces cyclomatic complexity (`C901`, max 10) and
simplification (`SIM`); `tests/test_code_quality.py` bounds function length
(60 lines) and nesting depth (4). Legacy heavy-contract checkers are
grandfathered by explicit list -- the lists only shrink.

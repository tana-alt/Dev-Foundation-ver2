# Harness Observability And Quantitative Eval Reference

Open this only for hook-based monitoring, the metrics store, issue surfacing,
quantitative NFR evaluation, benchmark comparison, or the AB evaluation
pipeline (abrun -> verdict -> check -> gate).

## Observe-Mode Pipeline

Wire local hook settings outside the active template surface to turn a normal
agent session into a recorded run:

- `SessionStart` -> `scripts/hook_session_start.py` prints a bounded task
  context summary from existing harness artifacts, then replays open issues
  into the session context.
- `PostToolUse` -> `scripts/hook_post_tool_use.py` appends one normalized
  `TrajectoryEvent` per tool call to
  `artifact/<project>/trajectory/<session>.jsonl`.
- `Stop` -> `scripts/hook_stop.py` observes submitted work and delegates
  `./harness dispatch <task_id>` with `HARNESS_ROLE=integrator`. It is
  fail-open: dispatch failures are reported, but they do not block stop.

Gating is plan-based: a project loops when `Plan/<project>/plans/` holds an
active `Plan_N000X.md` record (status from `index.yaml`; see
`src/workflow_core/plans.py`). A legacy `Plan/<project>/spec.md` file still
gates as a fallback (`scripts/hook_stop.py`). `FOUNDATION_SPEC_PRESENT=1`
forces gating; unplanned work stays single-pass.

Hook robustness contract: hooks run under plain `python3` (no venv). The
SessionStart context summary, PostToolUse recorder, and Stop hook decision are
stdlib-only
(`workflow_core.hook_events.event_dict_from_post_tool_use`,
`workflow_core.plans`; the package `__init__` resolves exports lazily so
those imports never pull pydantic). The Stop hook's dispatch path also fails
open when the harness is missing, the runtime root cannot be discovered, or the
dispatch exceeds `FOUNDATION_GATE_TIMEOUT_S` (default 900); it prints a stderr
or JSON diagnostic and exits 0 so an environment problem never traps the
session.

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

The SessionStart hook prints these after the task context at the start of every
session, so problems recur until a fresh `make measure && make issues` clears
them. Schedule that pair (cron or a recurring agent) for periodic surfacing.

## Quantitative NFR Evaluation (scripts/nfr_metric.py)

Non-functional budgets become measurements: record samples into the temporary
store `artifact/<project>/metrics/nfr.db`, then evaluate the distribution.

```sh
python3 scripts/nfr_metric.py record api_latency 142.5 --unit ms
python3 scripts/nfr_metric.py evaluate api_latency --threshold 200 --statistic p95
```

`evaluate` prints the verdict (p50/p95/max/mean vs threshold) and exits 1 on a
missed budget, so it can sit inside a verification gate (exit 3 means no
samples yet -- a tool error, not a miss; see
`docs/reference/exit-codes-reference.md`). Copy the verdict into
evidence or the plan log, then `purge` the metric; retention also ages out
samples beyond `FOUNDATION_NFR_MAX_SAMPLES` (default 1000) per metric.
`make nfr-summary` prints all current distributions.

## Benchmark Comparison (scripts/bench_compare.py)

Speed-ups become measurements: capture a pre-change distribution under a
baseline label, re-capture after the change, then compare the two on one
statistic. Samples are namespaced by `(benchmark, label)` in
`artifact/<project>/metrics/bench.db`; unlike `nfr.db` the store persists
across sessions so a baseline recorded before an optimization stays
comparable.

```sh
python3 scripts/bench_compare.py run api_smoke --label baseline -- make test-fast
# ... implement the optimization ...
python3 scripts/bench_compare.py run api_smoke --label candidate -- make test-fast
python3 scripts/bench_compare.py compare api_smoke --statistic p50
```

`run` times the command (default 5 repeats after 1 discarded warmup) and
records wall-clock milliseconds; nothing is recorded unless every iteration
exits 0. `record` ingests externally measured values instead. `compare`
prints delta, improvement percent, and a noise-banded verdict
(improved/regressed/unchanged; changes under `--min-change-pct`, default 3,
count as unchanged) and exits 1 on a regression -- or when
`--min-improvement-pct` is not met -- so it can sit inside a verification
gate (exit 3 means a side has no samples yet). Copy the comparison into
evidence or the plan log, then `purge` stale labels; retention also ages out
samples beyond `FOUNDATION_BENCH_MAX_SAMPLES` (default 1000) per
benchmark/label. `make bench-summary` prints all current distributions.

## AB Evaluation Pipeline (abrun -> verdict -> check -> gate)

Statistically grounded baseline-vs-candidate comparison. Runs, samples,
verdicts, checks, and gate decisions live in sqlite at
`artifact/<project>/metrics/runs.db` (`workflow_core.runstore`). All four
CLIs follow `docs/reference/exit-codes-reference.md`.

- `scripts/abrun.py run --config ab.json [--repo PATH]` measures baseline and
  candidate ABAB-interleaved in detached git worktrees. Worktree paths come
  from the config and must resolve outside the measured repo; a
  `.abrun-worktree` marker guards reuse and `abrun clean`. Each iteration
  runs the configured command and takes the value from wall-clock ms or the
  last stdout line. Runs are cached by
  `(commit_sha, config_hash, env_fingerprint)`; `--no-cache` forces a fresh
  measurement. An optional `server` block starts a process per side and
  polls a healthcheck before measuring.
- `scripts/check_runner.py run --run-id ID --worktree PATH --cmd name=cmd`
  runs functional checks in the candidate worktree and records pass/fail per
  check (exit 1 when any check fails).
- `scripts/verdict.py compare --baseline-run A --candidate-run B --metric M
  --policy FILE` judges one metric: MAD outlier filter, then a seeded
  percentile-bootstrap CI of the delta vs the policy threshold. An
  inconclusive verdict prints `suggested_additional_iterations` and a
  `repro` command line.
- `scripts/quality_gate.py evaluate --policy FILE --baseline-run A
  --candidate-run B` evaluates every policy condition (check + verdict),
  records the decision, and applies `on_inconclusive`
  (`fail` / `pass_with_warning` / `retry_then_fail` with `max_retries`).

Thresholds are never CLI flags: policies are JSON files that must live inside
`.agents/policies/` (`FOUNDATION_POLICY_DIR` overrides the directory), and
every decision records the policy hash. `.agents/policies/default.json`
shows the shape. Set `FOUNDATION_TRACE_PATH` (and `FOUNDATION_SESSION_ID`)
to append trace events (`workflow_core.tracelog`) for abrun samples and gate
decisions.

## Code Quality Budgets

Beyond types: ruff enforces cyclomatic complexity (`C901`, max 10) and
simplification (`SIM`); `tests/test_code_quality.py` bounds function length
(60 lines) and nesting depth (4). Legacy heavy-contract checkers are
grandfathered by explicit list -- the lists only shrink.

# Hypothesis-Driven Harness Refactor (Plan_N0003, 2026-06-11)

Method: four delegated subagent surveys (workflow_core / scripts+hooks /
tests+docs / Plan+config) produced candidate findings; each was re-verified
against source before classification. Two classes, per the goal:

- **Defect** -- the harness is wrong today (broken invariant, contract drift,
  silent failure path, stale state).
- **Improvement** -- works today but violates the repo's principles
  (goal-first, verify-over-record, smallest surface) or robust-harness
  engineering judgment (fail-open hooks, single source of truth, bounded
  blast radius for operator error).

## Verified Defects (fixed)

| # | Finding | Fix |
| - | ------- | --- |
| D1 | Hooks claimed "plain python3" but `workflow_core/__init__.py` eagerly imported pydantic via every submodule import; `hook_stop.py` / `hook_post_tool_use.py` crash without pydantic in the system interpreter | PEP 562 lazy package exports; `hook_events.event_dict_from_post_tool_use` (stdlib) feeds the PostToolUse hook; Stop hook fails open on ImportError |
| D2 | Stop hook ran `make <tier>` with no timeout -- a hung check traps the user's session forever | `FOUNDATION_GATE_TIMEOUT_S` (default 900) + 60s on `git diff`; timeout fails open with a stderr note; template hook entries got `timeout` fields |
| D3 | `run_completion_gate` scanned the same diff twice (locally and inside `build_verdict`) -- wasted work with silent-divergence risk | `build_verdict` accepts precomputed `findings` |
| D4 | `checks.check_transition` / `check_execution_ready` let bare `ValueError` escape past callers' `WorkflowCheckError` boundary on unknown status strings | `_parse_status` wraps into `WorkflowCheckError` |
| D5 | `run_eval.py` built `created_at=f"...0{idx}"` -- malformed ISO timestamps from the 10th case on, breaking retention ordering | minute/second formatting |
| D6 | `run-approved-work-contract.py` imported `src.workflow_adapters` with no path shim -- crashed unless invoked from repo root | module-level `sys.path` shim |
| D7 | `check-workflow-state.py` / `check-lane-map.py` crashed with tracebacks on malformed YAML or out-of-root paths instead of reporting structured errors | `yaml.YAMLError`/`OSError` handling; `add_issue` uses the guarded `issue_path` |
| D8 | Plan_N0001 (foundation-subagent-spec-workflow) stale `active` despite all items Done -- kept the Stop gate on; `codex-operationalization-implementation` used `status: complete` (typo) | closed N0001 with log note; typo fixed |
| D9 | `nfr_metric.py evaluate` exited 1 both for "budget missed" and "no samples yet" -- CI cold start indistinguishable from a miss | exit 2 for no samples; documented |

## Verified Improvements (applied)

- Sqlite lifecycle duplication: `SqliteStore` base (connect, schema bootstrap,
  close, context-manager) shared by `MetricsStore` and `NfrStore`; CLI
  scripts now use `with` so connections close on error paths too.
- Operator-input robustness: `workflow_core/env.py` (`env_int`/`env_float`,
  stdlib) -- malformed `FOUNDATION_*` values warn and fall back to defaults
  instead of crashing; applied across measure/issues/nfr/run_eval/hook_stop.
- Single source of truth: `SKILL_TOOL_NAMES` now lives in `hook_events`
  (stdlib-safe) and is re-exported by `evaluation`; duplicate frozensets
  removed.
- `NfrStore.record` rejects non-finite values (NaN/inf would silently poison
  percentiles).
- Typed `measure_eval.py` internals (was `Any`-typed at the ingestion core).
- Plan/README.md now documents allowed status values
  (draft/active/completed), the gating consequence of a stale `active`, the
  `plan_ref`/`log_ref` vs legacy `plan_path`/`log_path` key split, and that
  notes-only dirs (like this one) need no index.
- Subprocess-level tests for all three hooks, parity test pinning the
  stdlib event dict to `TrajectoryEvent.model_dump()`, a regression test
  pinning the no-pydantic import guarantee, and first coverage for
  `check_workflow_document` / unknown-status paths.

## Recorded, deliberately not changed

- `evaluation.score_run` counts a single event twice when it is both an
  unexpected tool and an out-of-envelope write -- judged correct (two distinct
  violations), revisit if it skews `runs_with_unexpected`.
- `plans.active_plan_ids` drops a `plan_id` line that is never followed by a
  `status` line (conservative: such plans do not gate).
- `metrics()` vs `_scores()` return different projections of `run_metrics`
  with no shared type; `loop.py`'s static `diff` handoff parameter.
- Older Plan projects keep `plan_path`/`log_path` keys (do-not-revert: prior
  session products; the gating parser reads neither).
- `templates/approved-spec-freeze.yaml` has zero consumers; left for a
  deliberate template-pruning pass.
- Heavy-contract checkers stay C901-grandfathered (rewrite risk > value).

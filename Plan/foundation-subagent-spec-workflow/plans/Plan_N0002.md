---
plan_id: Plan_N0002
project_id: foundation-subagent-spec-workflow
status: completed
log_ref: Plan/foundation-subagent-spec-workflow/logs/Plan_N0002.log.md
---

# Harness Observability And Quantitative Eval Completion

## Source Refs

- AGENTS.md
- docs/01-agent-operating-contract.md
- docs/02-output-verification-contract.md
- docs/03-repo-boundary-and-storage-contract.md
- Plan/harness-review/spec-gating-and-eval-pipeline.md

## Allowed Write Targets

- src/workflow_core/{plans,issues,nfr,evaluation,metrics_store,measure}.py
- scripts/{hook_stop,hook_session_start,measure_eval,run_eval,surface_issues,nfr_metric}.py
- scripts/agent_operational_checks.py (quality-rule compliance only)
- templates/claude-hooks-settings.json
- Makefile, pyproject.toml, AGENTS.md
- docs/reference/harness-observability-reference.md
- tests/ (new suites + integrity-constant updates)
- Plan/foundation-subagent-spec-workflow/

## Work Plan

1. Move the Stop-hook gate from `spec.md` detection to active `Plan_N000X.md`
   records (`workflow_core/plans.py`). Done.
2. Complete raw-data DB storage: ingest raw trajectory JSONL into the store's
   purgeable tier, purge by `created_at`, and prune ingested files beyond
   `FOUNDATION_TRAJ_MAX_FILES`. Done.
3. Record per-tool/skill usage and failure tallies (`tool_usage` table,
   `tool_stats` aggregation) and surface threshold breaches as recurring
   issues (`make issues` + SessionStart hook). Done.
4. Add the temporary NFR sample store and CLI for quantitative latency-style
   budgets (`workflow_core/nfr.py`, `scripts/nfr_metric.py`,
   `make nfr-summary`). Done.
5. Add code-quality budgets beyond types: ruff `C901`/`SIM` and the
   function-length / nesting-depth test (`tests/test_code_quality.py`). Done.
6. Route the new observability reference from AGENTS.md and update integrity
   constants. Done.

## Human Gates

- Merge remains human-only.
- Activating the hook settings template in a live `.claude/settings.json` is a
  user decision (self-gating side effect).

## Residual Risks

- Issue thresholds are static defaults (env-tunable); no per-project
  threshold file yet.
- `tool_usage` failure detection relies on `exit_code` in PostToolUse
  payloads; runtimes that omit it under-report failures.

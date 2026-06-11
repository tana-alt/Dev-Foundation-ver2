---
plan_id: Plan_N0003
project_id: foundation-subagent-spec-workflow
status: active
log_ref: Plan/foundation-subagent-spec-workflow/logs/Plan_N0003.log.md
---

# Harness-Wide Hypothesis-Driven Refactor

## Source Refs

- AGENTS.md
- docs/01-agent-operating-contract.md
- docs/02-output-verification-contract.md
- docs/03-repo-boundary-and-storage-contract.md
- docs/reference/harness-observability-reference.md
- Plan/foundation-subagent-spec-workflow/plans/Plan_N0002.md

## Goal

Survey the whole harness with delegated subagent reads, then extract and act on
two distinct finding classes via hypothesis verification:

1. Improvements: gaps between the repo's stated principles (goal-first,
   verify-over-record, smallest surface) plus robust-harness engineering
   judgment and the current implementation.
2. Defects: places where the harness is already wrong today (stale state,
   contract drift, silent failure paths, broken conventions).

## Method

- Fan out haiku/sonnet Explore agents across `src/workflow_core`, `scripts/`,
  `tests/` + `docs/`, and `Plan/` + `templates/` + build config.
- Each candidate finding becomes a hypothesis; verify by direct read or by
  running the code before classifying or fixing.
- Fix verified defects and high-value improvements directly; record the rest
  with rationale.

## Allowed Write Targets

- src/workflow_core/, scripts/, tests/, app/
- docs/, AGENTS.md, Makefile, pyproject.toml, templates/
- Plan/foundation-subagent-spec-workflow/

## Human Gates

- Merge remains human-only.
- No dependency, CI/infra, or external-write changes without approval.

## Status

- In progress (2026-06-11).

---
name: log-monitor-rollup
summary: >
  Aggregate repeated harness and coordination signals from runtime notes into a
  dated improvement rollup with promotion candidates and target surfaces.
version: 0.1
status: draft
data_model_version: 0.1
description: >
  Use when stewardship or harness work needs a structured rollup of repeated
  issues from `10-log.md`, `11-agent-map.md`, `12-agent-evals.md`, and
  `artifacts/improvement/current-signals.yaml`. This is a stewardship skill,
  not an app-delivery agent.
---

# Skill: log-monitor-rollup

## Purpose
Produce an `ImprovementRollup` that turns repeated coordination and contract
signals into a dated rollup with promotion candidates and target surfaces.

## Non-goals
- Changing specs or packets directly without a follow-up decision.
- Replacing runtime notes as the short-horizon source of truth.
- Promoting one-off incidents into permanent harness changes.
- Hiding source links behind prose-only summaries.

## Inputs

### Required
- `10-log.md`
- `11-agent-map.md`
- `12-agent-evals.md`
- `artifacts/improvement/current-signals.yaml`

### Optional
- `13-storage-map.md`
- latest dated rollup in `artifacts/improvement/rollups/`
- explicit cadence or aggregation threshold

## Outputs

### Primary
- Format: `markdown`
- Type: `ImprovementRollup`
- Required fields:
  - `signals_reviewed`
  - `aggregation_decisions`
  - `changes_recommended`
  - `promotion_candidates`
  - `target_surfaces`
  - `next_aggregation_trigger`

### Secondary
- Status update in `artifacts/improvement/current-signals.yaml`
- dated rollup in `artifacts/improvement/rollups/`
- short note in `10-log.md`

## Procedure
1. Start from `artifacts/improvement/current-signals.yaml`.
2. Read the latest relevant runtime entries only as needed to confirm recurrence,
   persistence, and scope.
3. Group signals by repeated contract drift, read-path drift, expected-answer
   drift, storage drift, or packet ambiguity.
4. Decide whether each signal should:
   - stay in current signals
   - be promoted into the dated rollup
   - be closed as resolved
5. Write a rollup that names target surfaces instead of only restating the
   symptoms.
6. Update `current-signals.yaml` status and record the aggregation event in
   `10-log.md`.

## Completion Criteria
- A dated rollup exists when promotion happens.
- Every promoted signal keeps source refs back to runtime notes.
- `current-signals.yaml` status is updated in the same slice.
- `target_surfaces` are explicit enough for a future harness change.
- `next_aggregation_trigger` is recorded.

## Failure Modes
- **Rollup replaces runtime notes**
  - Cause: the rollup becomes the only source of operational detail.
  - Countermeasure: keep source refs to `10-log.md`, `11-agent-map.md`,
    `12-agent-evals.md`, and `current-signals.yaml`.
- **One-off issue is promoted**
  - Cause: the threshold for recurrence is not checked.
  - Countermeasure: require occurrence and persistence before promotion.
- **Recommendations have no landing surface**
  - Cause: improvement ideas are written as prose only.
  - Countermeasure: require `target_surfaces`.
- **Signals are aggregated without status updates**
  - Cause: rollups are written but the live snapshot remains stale.
  - Countermeasure: update `current-signals.yaml` in the same slice.

## References
- `docs/specs/app-agentic-flow.md`
- `obsidian-vault/Apps/agentic-flow-app-flow/13-storage-map.md`
- `docs/tasks/active/WORKFLOW-gap-consult-loop/skill-contract-minimums-report-2026-04-23.md`

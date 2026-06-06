---
name: subagent-workflow-governance
description: "Use when coordinating a multi-phase subagent workflow from goal intake through spec drafting/review, human spec approval, lane mapping, build/review integration, inconsistency rework, convergence, or final handoff. Keeps subagents behind main_lane and record refs."
---

# Subagent Workflow Governance

## Purpose

Coordinate subagent-oriented specification workflow without expanding active docs,
repo context, or runtime state.

## Effect

When this skill fires, convert the task into phase-specific records, keep
subagents behind `main_lane`, separate behavior specification from
implementation policy, and make convergence depend on evidence, verification,
and `INC-*` closure.

## Use When

- A human goal must become an approved behavior specification before build.
- Multiple subagents or lanes must be coordinated through records.
- Specification review, lane mapping, integration review, inconsistency
  tracking, rework, convergence, or final handoff is in scope.
- The task names `main_lane`, `spec_drafter`, `spec_reviewer`, `lane_mapper`,
  `build_worker`, `review_worker`, `integration_reviewer`, `rework_worker`, or
  `convergence_checker`.

## Do Not Use When

- The task is an ordinary local implementation with a complete work contract.
- The task only needs current commands, branch/worktree mechanics, security
  review, or release readiness.
- A single-file edit has no spec ambiguity, lane split, or subagent handoff.
- The user asks for a runtime scheduler, queue, lock ledger, heartbeat, or
  dashboard; return rework against repository boundaries.

## Required References

Open `docs/reference/specification-workflow-reference.md` when this skill
materially shapes the task. Use packet/evidence, git/worktree, repo-boundary,
and verification references only when their specific fields or commands are
needed.

## Success Conditions

- Human-facing communication flows only through `main_lane`.
- Subagents communicate through result records, not sibling chat.
- Specs contain observable behavior only.
- Implementation policy stays in implementation-policy records or lane
  contracts.
- Lane work receives only its approved spec slice and relevant refs.
- Inconsistencies are tracked as `INC-*` items with evidence and status.
- Convergence checks trace all `REQ-*` and `AC-*` items to evidence, blocked
  reason, or residual risk.

## Stop Conditions

Return `rework` when source refs, human approval, allowed write targets,
observable requirements, verification expectations, record refs, or `INC-*`
closure are missing.

Return `blocked` when required human decision, side-effect approval, protected
branch/merge action, secret handling, or external write authority is missing.

## Constraints

- Do not create runtime queues, locks, heartbeats, polling loops, dashboards, or
  broad logs.
- Do not add role-per-subagent skills unless skill-authoring governance later
  proves one compact skill is insufficient.
- Do not let implementation policy redefine behavior authority.
- Do not claim verification that did not run.

## Output

- `workflow_verdict`: proceed / rework / blocked / human_review_required.
- `phase`: current workflow phase and next action.
- `records`: workflow, spec, review, lane-map, evidence, verification, rework,
  and inconsistency refs used or required.
- `subagent_contracts`: roles or modes to invoke, with scoped inputs and
  outputs.
- `open_inconsistencies`: `INC-*` IDs, severity, owner lane or human decision
  path.
- `verification`: checks run or blocked reason.
- `residual_risk`: remaining uncertainty and review focus.

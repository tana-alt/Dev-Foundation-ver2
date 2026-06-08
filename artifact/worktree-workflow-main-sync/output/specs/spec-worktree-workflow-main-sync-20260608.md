# Specification: Worktree Workflow Main Sync

## Identity

- `project_id`: `worktree-workflow-main-sync`
- `spec_id`: `spec-worktree-workflow-main-sync-20260608`
- `goal_ref`: `artifact/worktree-workflow-main-sync/output/goals/goal-worktree-workflow-main-sync-20260608.md`
- `created_at`: `2026-06-08`
- `status`: `draft`

## Scope

This specification defines observable repository workflow behavior for canonical primary branch freshness, PR handoff freshness, and the correspondence between workflow records, lane ownership, branches, and worktree targets.

## Freshness States

Canonical primary branch freshness must be reported using one of these states:

- `current`: the local primary ref equals its intended remote tracking ref after refresh evidence is recorded.
- `stale_fast_forwardable`: the local primary ref is behind its intended remote tracking ref and has no local-only commits or dirty working tree blocking a fast-forward update.
- `blocked_dirty_primary`: the canonical primary worktree has uncommitted changes.
- `blocked_detached_primary`: the canonical primary worktree is detached or not on the configured primary branch.
- `blocked_missing_primary`: the canonical primary branch or its intended tracking ref cannot be identified.
- `blocked_diverged_primary`: the local primary ref and its intended tracking ref both contain commits not reachable from the other.
- `explicit_base_not_primary`: the lane uses an explicit base ref other than canonical local primary and records why this is acceptable for the scoped work.
- `not_applicable`: the scoped work does not create or update a local write worktree, branch, or PR handoff.

## Requirements

### REQ-001: Canonical Primary Freshness Before Worktree Creation

Before an agent-owned worktree or lane branch is created for local write work, the canonical repository primary branch state must be checked against the intended base and merge target. Work may continue only when the freshness state is `current`, `stale_fast_forwardable` with post-update evidence, `explicit_base_not_primary`, or `not_applicable`. Other states require rework before worktree creation or reuse.

Observable outcome: worktree creation evidence records exactly one freshness state and the refs supporting that state.

Acceptance criteria:

- `AC-001`: The pre-worktree evidence records the canonical repo root, primary branch name, intended base ref, intended merge target, local primary ref, and remote tracking ref when available.
- `AC-002`: If freshness is `blocked_dirty_primary`, `blocked_detached_primary`, `blocked_missing_primary`, or `blocked_diverged_primary`, the workflow returns rework instead of silently creating or reusing an agent worktree.
- `AC-003`: If freshness is `stale_fast_forwardable`, post-update evidence records the resulting primary ref used to derive or validate the worktree base.
- `AC-004`: If worktree creation does not use the canonical primary branch directly, the evidence records the explicit base ref that was used and why canonical primary freshness remains safe or not applicable.

### REQ-002: PR Handoff Freshness

When an agent-owned branch is prepared for PR creation or PR update, the handoff must state the freshness relationship between the review branch, intended base ref, merge target, and canonical primary branch.

Observable outcome: PR handoff evidence makes stale base risk visible before human review or merge.

Acceptance criteria:

- `AC-005`: PR or review handoff evidence records the owned source branch, intended target branch, base ref, merge target, branch/worktree ownership, and canonical primary freshness result.
- `AC-006`: If the intended merge target advanced after the worktree or branch was created, the handoff records whether the review branch was checked against the newer target, requires rework, or carries an explicit residual risk.
- `AC-007`: Opening or updating a PR does not mark a lane or workflow complete by itself; completion requires accepted review or final handoff evidence.
- `AC-008`: The workflow preserves the existing human gate: agents may create or update owned review PRs when evidence is clear, but direct pushes to `main` or `master` and merges remain prohibited for agents.

### REQ-003: Workflow Record To Worktree Correspondence

For scoped workflow work that uses lanes, each lane must have a traceable relationship among requirement IDs, lane status, allowed write targets, branch ownership, worktree target, and workflow-run record refs. Local worktree existence is not repo truth; durable records capture intended targets and evidence refs.

Observable outcome: a reviewer can determine which lane owns which branch and worktree target, which requirements it covers, and which workflow phase it is in, without reading unrelated runtime state.

Acceptance criteria:

- `AC-009`: A workflow-run record references the active goal, reviewed specification, specification review record, and lane map or work contract refs when those records exist.
- `AC-010`: Each lane or work contract records requirement IDs, allowed write targets, branch target, worktree target, verification expectations, and handoff evidence expectations.
- `AC-011`: Lane status distinguishes at least planned, assigned, in progress, ready for review, rework, blocked, and complete states without using the lane map as a runtime queue, lock ledger, scheduler, worker heartbeat, or dashboard.
- `AC-012`: PR-open or review-requested state maps to ready for review or equivalent handoff state, not complete.
- `AC-013`: Completion requires evidence that changed paths stayed within allowed write targets, relevant verification was attempted and honestly reported, and unresolved critical or high inconsistencies are absent or explicitly blocked.

## Interfaces

### Public Contracts

- Agent final outputs, PR handoffs, work contracts, workflow-run records, and lane maps that report branch, worktree, base, merge target, changed paths, verification, and human-gate status.

### Data Contracts

- Requirement IDs use stable `REQ-*` identifiers.
- Acceptance criteria use stable `AC-*` identifiers.
- Workflow state is carried by project-scoped record refs, not conversation-only state.

### Trust Boundaries

- Human approval is required before approved-spec freeze.
- Merge remains human-only.
- Direct agent writes to protected primary branches remain prohibited.

### Side Effects

- Allowed side effects are limited to local repository records and, after approval, owned agent review branches or PRs when evidence is clear.
- Protected branch writes, merges, branch deletion, worktree deletion, CI/CD changes, dependency changes, release, deployment, secrets, auth, database, infrastructure, and external writes outside the owned review branch or PR require explicit human approval.

## Non-Goals

- Automatic merge, release, or deployment.
- Branch or worktree deletion.
- Runtime queue, lock ledger, heartbeat, scheduler, or dashboard.
- Storage of local runtime state, secrets, raw logs, browser sessions, or cache data.
- Broad repo scans as a default source of truth.

## Implementation Boundary

The implementation may choose local command shapes, helper functions, validation scripts, and lane slicing only after this specification is approved. Those choices must not redefine any `REQ-*` or `AC-*` behavior.

## Unresolved Questions

None.

## Verification Expectation

Review must confirm requirement traceability, observable acceptance criteria, explicit non-goals, human-gate clarity, and absence of implementation-policy leakage. Implementation verification must be selected from current repo-backed checks after lane mapping.

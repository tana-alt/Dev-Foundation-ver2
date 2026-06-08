# Goal: Worktree Workflow Main Sync

## Problem

Two repository workflow problems need resolution:

- After creating worktrees and PRs, canonical local `main` can remain on an older version.
- Current workflow records do not make the relationship between worktrees, branch ownership, lane ownership, and workflow state explicit enough for reliable handoff and review.

## Desired Outcome

The repository has an approved behavior specification that makes canonical main freshness and worktree/workflow correspondence observable, reviewable, and enforceable without turning `Plan/` or `artifact/` into runtime state.

## Success Criteria

- Worktree creation cannot proceed from a stale or unsafe canonical primary branch state without evidence or rework.
- PR handoff records include freshness evidence for the base and merge target.
- Lane/worktree/branch ownership is traceable from workflow records without treating local worktree existence as repo truth.
- Human gates remain intact: approved-spec freeze and merge are human-only.
- Implementation and review can be delegated to scoped subagents after approval.

## Non-Goals

- No automatic PR merge.
- No direct push to `main` or `master`.
- No branch or worktree deletion.
- No runtime queue, lock ledger, worker heartbeat, scheduler, or dashboard.
- No secret-bearing or local runtime state in repo records.

## Constraints

- Follow active contracts in `docs/01-agent-operating-contract.md`, `docs/02-output-verification-contract.md`, and `docs/03-repo-boundary-and-storage-contract.md`.
- Follow specification workflow in `docs/reference/specification-workflow-reference.md`.
- Keep durable records project-scoped under `Plan/worktree-workflow-main-sync/` and `artifact/worktree-workflow-main-sync/`.
- Build work must wait for human approval of the reviewed specification.

## Source Refs

- AGENTS.md
- docs/01-agent-operating-contract.md
- docs/02-output-verification-contract.md
- docs/03-repo-boundary-and-storage-contract.md
- docs/reference/specification-workflow-reference.md
- docs/reference/git-worktree-and-branch-reference.md
- docs/reference/repo-boundary-and-storage-reference.md
- docs/reference/verification-ci-and-pr-reference.md

## Denied Context

- Broad repo history
- Past-source material
- Runtime queues or local lock state
- Secrets, credentials, browser sessions, caches, and raw logs

## Next Action

Draft and review the behavior specification, then request human approval before approved-spec freeze and implementation.

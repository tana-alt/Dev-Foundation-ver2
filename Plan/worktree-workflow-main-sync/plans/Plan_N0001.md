---
plan_id: Plan_N0001
project_id: worktree-workflow-main-sync
status: active
log_ref: Plan/worktree-workflow-main-sync/logs/Plan_N0001.log.md
---

# Worktree Workflow Main Sync Specification

## Source Refs

- AGENTS.md
- docs/01-agent-operating-contract.md
- docs/02-output-verification-contract.md
- docs/03-repo-boundary-and-storage-contract.md
- docs/reference/specification-workflow-reference.md
- docs/reference/git-worktree-and-branch-reference.md
- docs/reference/repo-boundary-and-storage-reference.md
- docs/reference/verification-ci-and-pr-reference.md
- templates/specification-packet.yaml
- templates/specification-review-record.yaml
- templates/workflow-run-record.yaml

## Allowed Write Targets

- Plan/worktree-workflow-main-sync/
- artifact/worktree-workflow-main-sync/

## Work Plan

1. Create durable goal, workflow-run, and specification records. Done.
2. Run specification review against observable requirements and WHAT/HOW separation. In progress.
3. If the specification review approves it for human review, request human approval for approved-spec freeze.
4. After human approval, create approved-spec freeze and lane mapping.
5. Delegate implementation and review to subagents using scoped lane contracts. Pending human approval.

## Human Gates

- Human approval is required before approved-spec freeze.
- Merge remains human-only.
- Branch or worktree deletion, direct writes to main, CI/CD changes, dependency changes, release, deployment, secrets, auth, database, infrastructure, and external writes outside an owned review branch or PR remain out of scope unless explicitly approved.

## Residual Risk

- Implementation has not started because specification freeze requires human approval after review.

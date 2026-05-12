---
name: project-worktree-scope
description: Use before local writes that need project-scoped worktree, branch, or cross-project multi mode setup in this foundation repo.
---

# Project Worktree Scope

Use this before writing when work touches project-scoped storage or needs a
branch/worktree scope decision.

## Choose Scope

Single-project work:

```sh
export FOUNDATION_PROJECT_ID=<project_id>
```

Use a branch/worktree whose `work_id` and path include `<project_id>`.

Cross-project work:

```sh
export FOUNDATION_PROJECT_SCOPE=multi
export FOUNDATION_ALLOWED_PROJECT_IDS=projectA,projectB
export FOUNDATION_PROJECT_SCOPE_REASON="<why this branch touches multiple projects>"
```

Multi mode is branch/task scoped, not worktree scoped. Reuse a single local
`multi` worktree across cross-project branches, but declare allowed project IDs
and reason for each branch before editing.

## Guardrails

- Do not use `main`, `master`, or the canonical root as an escape hatch.
- Do not expand `FOUNDATION_ALLOWED_PROJECT_IDS` mid-task unless scope is
  explicitly updated and recorded in PR or handoff evidence.
- Run `scripts/check-agent-worktree-policy.sh` before committing.
- Run `scripts/check-project-scoped-changes.sh` before committing if the branch
  may touch `Plan/`, `artifact/`, or `src/`.

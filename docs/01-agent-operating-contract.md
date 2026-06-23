# Agent Operating Contract

## Purpose

Keep agent work focused on the user's goal, with enough scope control to avoid
unsafe or unrelated edits.

## Goal First

Start from the current user request, task packet, or named scope. Identify:

goal, Done criteria, source refs, allowed write targets, denied context,
verification command or method, and next action.

If details are missing but a safe local assumption is obvious, state the
assumption and proceed. Ask for clarification only when a wrong assumption would
cause unsafe work, broad rewrites, external side effects, or destructive
actions.

## Context Boundary

Read named refs first. Inspect nearby files only when needed for a safe local
change or verification. Do not read broad logs, archives, unrelated history,
secrets, runtime state, caches, or past-source material by default.

If context expands, explain why.

For coding work, apply `AGENTS.md` Coding Principles; load narrower skills or
references only when the task needs their detail.

## Write Preconditions

Before local writes, confirm:

- current file contents or absence
- repo root
- relevant VCS status
- conflict risk with existing user changes

For parallel write work, require explicit branch and worktree ownership. Do not
create worktrees by default; use them only when the user requests parallel work
or the task truly needs separate write lanes.

## Side Effects

Classify side effects before acting:

- local read
- local write
- external read
- external write
- dependency/tooling change
- deploy/release/infra change
- secret-bearing action
- destructive or irreversible action

The canonical human-gate list and result states live in
`docs/02-output-verification-contract.md`. Missing approval blocks only that
action; keep approved local work moving.

## Records

Records are optional tools, not the product. Avoid final handoff, convergence,
traceability, source snapshot, or scorecard records unless explicitly requested.
Do not treat records-only work, mocks, or `complete_with_residual_risk` as
finished implementation.

## Valid Output

For implementation work, report changed paths, verification, unverified
surfaces, remaining risk, and next action.

For casual brainstorming or read-only answers, answer directly.

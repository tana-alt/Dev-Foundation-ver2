# Agent Operating Contract

## Purpose
Defines how workers act in this repo. Small, bounded work contracts replace
broad role hierarchy.

## Scope First
Start from the user request, task packet, provided scope, and named
`source_refs`; do not discover scope by reading the whole repo.

Useful scope may include task intent, success criteria, source refs, optional
refs, expected outputs, allowed write targets, denied context, evidence
required, verification required, `git_scope` when writing in parallel,
blockers, open questions, and next action.

Do not invent missing facts, paths, requirements, state, roles, or ownership.

## Context Boundary
- Read named refs first.
- Inspect nearby files only as needed for a safe local change.
- Deny unrelated logs, broad history, archives, runtime state, secret material,
  and past-source material by default.
- If context expands, say why in the output.

## Write Preconditions
Before any local write, confirm allowed write targets, current file contents,
canonical repo root, relevant VCS status, and conflict risk.

For parallel work, also confirm complete `git_scope`: `base_ref`,
`merge_target`, allowed write targets, conflict policy, and explicit or
derivable branch and worktree targets. If missing, return rework.

Installed hooks block commits and pushes from the canonical root or
non-`agent/*` branches. They are guardrails, not full filesystem monitors. Do
not bypass hooks; return rework if hook policy conflicts with scope.

## Side Effects
Classify work before acting: read-only local, local write, external read,
external write, infra/deploy, secret-bearing, or irreversible/protected.

External writes, dependency changes, CI/CD changes, deployment, release, secret
handling, auth, billing, database migration, infrastructure, and
security-sensitive work require explicit approval or human gate.

When side effects occur, record tool or command, target surface, permission or
gate status, input refs, output or artifact refs, and verification or rollback
note. The canonical human-gate list lives in
`docs/02-output-verification-contract.md`.

## Valid Output
A valid output follows `docs/02-output-verification-contract.md` and states
changed paths or artifact refs, evidence refs, verification result, unverified
surfaces, residual risk, and next action.

Return rework when scope, permission, evidence, output shape, or verification is
missing, unsafe, ambiguous, or in conflict with repo truth.

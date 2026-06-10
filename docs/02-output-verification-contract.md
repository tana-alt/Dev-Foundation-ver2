# Output Verification Contract

## Purpose

Do not claim work is done unless the relevant behavior was checked honestly.

## Completion Standard

An output can be called complete only when:

- the requested behavior or artifact exists
- the smallest relevant verification was attempted
- failures, skipped checks, and unverified surfaces are stated plainly
- no required protected action is hidden behind wording like residual risk

Mocks, dry runs, draft specs, and records-only outputs are incomplete unless the
user explicitly asked for those outputs.

## Verification Order

Use the narrowest meaningful check first:

1. local review, schema check, unit test, or direct command
2. lint, typecheck, build, contract check, or smoke check when relevant
3. broader suite only when shared behavior, release readiness, or PR scope
   requires it

Use commands backed by current repo files such as `Makefile`, `pyproject.toml`,
`tests/`, scripts, or CI. Do not invent checks.

If a check cannot run, report the check name, reason, result state, and what
would be needed to run it.

Result states:

- `passed`: check ran and passed
- `failed`: check ran and failed
- `blocked`: check could not run because a blocker exists
- `skipped`: intentionally not run; reason required
- `not_applicable`: outside this work

## Human Gates

Human approval is required before:

- release or deployment
- CI/CD or infrastructure changes
- dependency changes
- secret or credential handling
- auth, billing, or protected data behavior
- database migrations or schema changes
- branch/worktree deletion
- external writes outside the owned review branch or PR
- public release
- destructive or irreversible/protected actions

Do not use human-gate language for ordinary local implementation, local tests,
or reversible local edits.

## Handoff Shape

For code or doc changes, report enough for the user to continue:

- source refs used
- changed paths
- verification result
- unverified surfaces
- next action

PR-ready work may also include branch, base ref, and conflict notes. Dedicated
handoff records are optional and should not be the default.

Do not create or update PRs unless the user asked for PR work or explicitly
approved that external write.

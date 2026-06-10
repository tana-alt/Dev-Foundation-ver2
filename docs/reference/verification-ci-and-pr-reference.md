---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
updated_at: 2026-06-10
---

# Verification, CI, And PR Reference

Use this reference to choose current repo-backed verification commands. Do not
use verification records as a substitute for working behavior.

## Trigger

Open this reference when:

- deciding which local command proves a change;
- preparing PR-ready evidence;
- a check cannot run and needs an honest status;
- Makefile, tests, hooks, CI, or CD surfaces are changed.

## Command Order

Start narrow:

1. closest unit, schema, script, local review, or direct command
2. lint, typecheck, build, smoke, or contract check when relevant
3. full suite only for shared behavior, release readiness, or broad PR scope

Do not invent checks. Use current repo files.

## Current Commands

- `make format-check`
- `make lint`
- `make typecheck`
- `make test-fast`
- `make test`
- `make check-hooks`
- `make check-shell`
- `make check-hygiene`
- `make check-secrets`
- `make check-lanes` only when lane maps are relevant
- `make check-fast` for local fast confidence
- `make check-required` for broader local readiness
- `make check-ci` for CI-equivalent checks
- `make check-cd` for deployment-readiness guard
- `make check-legacy-contracts` only for archived heavy-contract compatibility
- `make doctor` for local toolchain and hook setup inspection

Legacy heavy-contract checks may still exist for migration or archive audit, but
they are not default proof of goal completion.

## Fast And Full Gate Mapping

`make test`: aggregate gate over `tests/test_*.py`.

`make check-contracts`, `make check-doc-consistency`, and `make check-cd` are
targeted shortcuts, not automatic test classification.

Use `make test-fast` as the curated fast pytest smoke set and `make check-fast`
for the local edit loop. Use `make check-required` or `make check-ci` for PR
handoff or high-risk change. `make check-push` runs the configured pre-push
gate. `make check-foundation` remains the full foundation gate.

PR handoff or high-risk change should use `make check-required` or
`make check-ci`.

`make check-lanes` performs parallel lane-map validation only when lane maps are
part of the work. `make check-legacy-contracts` runs archived heavy-contract
compatibility checks when explicitly requested.

Set `core.hooksPath=hooks` through the setup script when using tracked hooks.

## Result States

- `passed`: ran and passed
- `failed`: ran and failed
- `blocked`: could not run due to blocker
- `skipped`: intentionally not run; reason required
- `not_applicable`: not relevant

## Reporting

Report:

- command or method
- result
- important output summary
- unverified surfaces
- next action

For PR-ready work, also report branch/base/conflict notes when relevant.

## Human Gates

Do not perform protected side effects without explicit approval:

- release/deploy
- CI/CD or infrastructure mutation
- dependency changes
- secrets or credentials
- database migrations
- protected branch writes or merges
- branch/worktree deletion
- external writes outside the owned review branch or PR
- irreversible/protected action

Direct pushes to `main` or `master` are prohibited.

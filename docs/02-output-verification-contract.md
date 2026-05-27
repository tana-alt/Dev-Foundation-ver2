# Output Verification Contract

## Complete Output
Every meaningful output states source refs used, changed paths or artifact
refs, evidence or why none exists, verification attempted, result
(`passed`, `failed`, `blocked`, `skipped`, or `not_applicable`), unverified
surfaces, residual risk, and human gate status when relevant.

Do not claim verification that did not run. Evidence and verification records
must stay schema-valid, source-ref based, and free of secrets or runtime
ledger state.

## Verification Order
Start with the smallest relevant check and widen only when required:

1. closest local review, schema check, unit, or command
2. lint, typecheck, build, contract check, or smoke check when applicable
3. broader suite only when scope, shared behavior, or PR readiness requires it

Use commands backed by current repo files such as `Makefile`, `pyproject.toml`,
`tests/`, scripts, or CI. Current commands and fast/full gate mapping live in
`docs/reference/verification-ci-and-pr-reference.md`.

If a check cannot run, record check name, reason, result state, residual risk,
and next action.

## PR Or Handoff Evidence
PRs, handoffs, and review packets should include intent, scope, changed paths
or artifacts, verifier results, docs impact, risks, follow-up, and human
review focus.

For write work, include branch, worktree, base ref, changed paths,
allowed-write-target check, and conflict-check status when applicable. For side
effects, include command, target surface, gate status, input refs, output refs,
and verification or rollback note.

## Human Gate
Agents may push owned `agent/*` review branches and create or update PRs when
scope, branch/worktree ownership, verification, and evidence are clear.

Do not push directly to `main` or `master`. Do not merge; merge is human-only.

Release, deployment, CI/CD or GitHub Actions change, dependency change, secret
or credential handling, auth, billing, database migration or schema change,
infrastructure change, branch/worktree deletion, external write outside the
owned review branch or PR, public release, protected data change,
irreversible/protected action, or security-sensitive behavior requires explicit
human approval unless scope explicitly approves it.

# AGENTS.md

## Operating Rule

The goal is the product. Plans, specs, packets, reviews, and logs are tools only
when they help ship the goal.

Default flow: Goal -> Scope -> Done -> Plan -> Implement -> Verify -> Log
result. Use lightweight `Plan/<project_id>/` records only for substantial,
multi-file, or resumable work.

## Coding Principles

For non-trivial coding, implementation follows evidence. Read only enough local
truth to decide correctness: the request, named refs, target files, nearby
tests, current contents, relevant VCS status, and existing patterns. If allowed
writes are none, do not write.

State protected invariants before changing behavior: user-visible rules,
data/API shape, security, accessibility, performance, persistence, and
compatibility. Design behavior examples before implementation when practical:
Given local state/input, When the user/API/CLI/job acts, Then the observable
result. Name the proof vehicle: focused test, fixture, probe, smoke command,
runtime run, screenshot, protocol trace, benchmark, or audit check.

For bugfixes and regressions, prefer fail-before/passed-after proof when
practical; otherwise state the closest substitute. Implement the smallest
compatible runnable slice that can satisfy the example, then verify on the
closest real path. If proof fails, classify the failure layer before patching.
Report changed paths, verification, skipped or blocked proof with reasons,
unverified surfaces, remaining risk, and next action.

## Hard Rules

- Start from the provided goal, scope, and named refs.
- Prefer implementing and verifying over producing records.
- A mock, draft, or records-only output is incomplete unless the user only asked
  for that artifact.
- Before local writes, inspect current contents and relevant VCS status.
- Do not revert user changes.
- Use explicit branch/worktree ownership only when parallelism is actually
  needed.

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

## Records

Records are optional tools, not the product. Avoid final handoff, convergence,
traceability, source snapshot, or scorecard records unless explicitly requested.
Do not treat records-only work, mocks as finished implemention.

## Valid Output

For implementation work, report changed paths, verification, unverified
surfaces, remaining risk, and next action.

For casual brainstorming or read-only answers, answer directly.

# Output Verification Contract

## Completion Standard

An output can be called complete only when:

the requested behavior or artifact exists, the smallest relevant verification
was attempted, failures or skips are stated plainly, and protected actions are
not hidden behind residual-risk wording.

Mocks, dry runs, draft specs, and records-only outputs are incomplete unless the
user explicitly asked for those outputs.

## Verification Order

Use the narrowest meaningful check first: local/direct check; then lint,
typecheck, build, contract, or smoke when relevant; then broader suites only
for shared behavior, release readiness, or PR scope.

Use commands backed by current repo files such as `Makefile`, `pyproject.toml`,
`tests/`, scripts, or CI. Do not invent checks.

For user-visible deliverables, prefer the closest runnable path over build-only
proof; change observation layer before retrying failures.

For proof vehicle examples and fail-before/passed-after guidance, see
`AGENTS.md` Coding Principles.

If a check cannot run, report the check name, reason, result state, and what
would be needed to run it.

Result states: `passed`, `failed`, `blocked`, `skipped`, `not_applicable`.
Skipped or blocked checks require a reason.

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

For code or doc changes, report enough for the user to continue: source refs,
changed paths, verification, unverified surfaces, and next action.

PR-ready work may also include branch, base ref, and conflict notes. Dedicated
handoff records are optional and should not be the default.

Do not create or update PRs unless the user asked for PR work or explicitly
approved that external write.

# Repo Boundary And Storage Contract

## Repo Truth

Repo truth is the tracked product, docs, tooling, templates, tests, plans,
artifacts, source roots, hooks, plugins, `.agents/`, and `.github/`.


## Placement

- Use `Plan/<project_id>/` for lightweight plans and logs.
- Use `artifact/<project_id>/` only for durable, useful outputs or evidence.
- Use `src/<project_id>/` or existing shared source paths for implementation.
- Keep `docs/` for repo-wide rules and references.
- Use `templates/` only for compact blank formats that are still active.

Optional durable lane-map records may live under
`Plan/<project_id>/lane-maps/` for real parallel write work. They are not a
runtime scheduler, queue, lock ledger, heartbeat, dashboard, or completion
claim.

## Storage Rules

Prefer small records that help the next action: plan, log, task packet,
verification note, or optional spec.

Do not store raw bodies, credentials, local runtime ledgers, browser sessions,
secret-bearing metadata, or unrelated context in docs, plans, artifacts,
templates, or prompts.

## Skills And Plugins

Skills are compact routing helpers. They do not override the user request,
active contracts, allowed write targets, human gates, verification, or storage
rules.

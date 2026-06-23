# AGENTS.md

## Operating Rule

Start from the current user request, task packet, or named scope. Identify the
requested outcome, Done criteria, source refs, allowed write targets, forbidden
targets, verification method, and next action.

Plans, specs, packets, reviews, logs, and issues are support work. They are not
the deliverable unless the user explicitly asked for that artifact.

For non-trivial work: set scope, protected invariants, acceptance criteria,
adversarial checks, and proof vehicle; plan only enough to change safely;
implement the smallest compatible runnable slice; verify the closest real path;
report changed paths, verification, skipped or blocked checks with reasons,
unverified surfaces, remaining risk, and next action.

Use lightweight `Plan/<project_id>/` records only for substantial, multi-file,
or resumable work.

## Coding Principles

Implementation follows local evidence. Read only what is needed to decide
correctness: the request, named refs, target files, nearby tests, current
contents, relevant VCS status, existing patterns, and generated harness packets.
If allowed writes are none, do not write.

Before changing behavior, state protected invariants for user-visible behavior,
data/API/CLI/file/protocol shape, security, privacy, accessibility,
performance, persistence, migration behavior, and compatibility.

Set acceptance criteria before implementation. Prefer concrete examples:
Given local state/input, When the user/API/CLI/job acts, Then the observable
result. Include adversarial checks that try to break the claim, not only
happy-path checks. Name the proof vehicle: focused test, fixture, probe, smoke
command, runtime run, screenshot, protocol trace, benchmark, or audit check.

For bugfixes and regressions, prefer fail-before/passed-after proof when
practical. If that is not practical, state the closest substitute. If proof
fails, classify the failure layer before patching.

## Architecture Requirements

For non-trivial changes, make the architecture reviewable before coding.

- Responsibility decomposition must be clear: entrypoint, orchestration, domain
  rule, adapter/IO, state owner, and test surface.
- Contracts must be explicit at boundaries: APIs, CLI flags, file formats,
  protocols, events, schemas, and error shapes.
- The design must stay extensible through stable interfaces, registries,
  configs, or strategies rather than task-specific branching.
- State ownership must be explicit. Keep runtime state, locks, sessions, auth
  material, generated queues, and evidence out of tracked source unless repo
  policy explicitly says otherwise.
- Failure behavior must be designed: partial writes, retries, stale evidence,
  idempotency, rollback/recovery, and timeout behavior.
- Dependency direction must keep policy/domain rules independent from transport,
  UI, daemon, filesystem, and subprocess details.
- Concurrency must have an owner: branch, worktree, session, task, lock, and
  external write authority cannot be shared implicitly.
- Observability must support review: changed paths, evidence, protocol traces,
  verification output, and stale-evidence invalidation should be inspectable.

## Harness Contract

Normal harness work must be executable from `AGENTS.md`, `.harness/policy.yaml`,
`.harness/tasks/<task_id>/task.yaml`, and generated packets. Open optional
references or skills only when the task names them or the needed detail is not
present in those sources.

Task contracts must contain task-specific architecture, protected invariants,
acceptance criteria, adversarial acceptance, expected evidence, and review
request. Missing required task information means rework. Format variance is
acceptable only when the required meaning is still present.

Use `allowed_paths` as expected impact scope for planning and review, not as a
hard gate. Touching paths outside `allowed_paths` requires explanation and
impact analysis. `forbidden_paths` is blocking unless the task is explicitly an
approved policy exception.

An `integrated` result means integration evidence exists and the candidate is
ready to land. It does not mean landed or pushed. A `landed` result means the
local land step completed.

## ACP And Agent Communication

Use task-scoped communication only. Messages are coordination records, not
authoritative completion, review, gate, land, push, or merge results.

Allowed message kinds: `action_request`, `status_query`, `status_response`,
`proposal`, `clarification`, `rework_hint`, `artifact_summary`, `test_request`,
`review_question`, `handoff_note`.

Local mode:

```sh
./harness comm-peers <task_id>
FOUNDATION_AGENT_ID=<agent_id> HARNESS_ROLE=<role> \
  ./harness comm-inbox <task_id> --agent-id <agent_id>
FOUNDATION_AGENT_ID=<from_agent_id> HARNESS_ROLE=<from_role> \
  ./harness comm-send <task_id> \
  --to-agent <to_agent_id> --to-role <to_role> \
  --kind <kind> --subject "<subject>" --body "<body>"
```

Strict daemon mode uses the same channel through ACP. Use the provided session
environment; admin actions are outside normal agent work.

```sh
./harness daemon run --foreground
./harness --strict acp list <task_id> --agent-id <agent_id>
./harness --strict acp send <task_id> \
  --to-agent <to_agent_id> --to-role <to_role> \
  --kind <kind> --subject "<subject>" --body "<body>"
./harness --strict acp request-action <message_id> --body "<message body>"
```

`acp request-action` returns a proposed action only; it must not execute the
action. Execute protected actions only through the normal harness command for
the current role and authority. In strict mode, sender identity comes from the
authenticated session; do not override `from_agent_id` or `from_role`.

## Review Requests

Set review expectations before implementation. A task review request must
separate architecture review from code review.

Architecture review checks responsibility split, invariants, scope semantics,
acceptance criteria, adversarial checks, and extensibility. Code review checks
the actual diff, tests, evidence, stale-evidence risk, security, compatibility,
and behavior under adversarial inputs.

Writer handoff:

```sh
HARNESS_ROLE=writer ./harness verify <task_id>
HARNESS_ROLE=writer ./harness submit <task_id> --wait
```

Manual review and integration:

```sh
HARNESS_ROLE=reviewer ./harness review <task_id> --run <reviewer_id>
HARNESS_ROLE=integrator ./harness review <task_id> --collect
HARNESS_ROLE=integrator ./harness dispatch <task_id>
HARNESS_ROLE=integrator ./harness land <task_id>
```

Reviewer posture is adversarial counterexample search. Review should find the
cheapest counterexample that invalidates the architecture, task contract,
implementation, test evidence, or scope claim.

Reviewer evidence must be fresh. If candidate diff, verifier output, quality
evidence, scope map, metrics, mutation output, or reviewer-consumed artifacts
change, rerun stale reviewer lanes instead of reusing old verdicts.

## Hard Rules

- Start from the provided request, scope, and named refs.
- Prefer implementation and verification over records.
- A mock, draft, or records-only output is incomplete unless the user only asked
  for that artifact.
- Before local writes, inspect current contents and relevant VCS status.
- Do not revert user changes.
- Use explicit branch/worktree ownership only when parallelism is actually
  needed.
- Do not create or update PRs unless the user asked for PR work or approved that
  external write.
- Create a GitHub issue only for escalation or for a problem that cannot be
  resolved algorithmically from repo evidence. Do not create issues for routine
  TODOs, ordinary bugs, missing tests, or rework that can be fixed directly.

## Context Boundary

Read named refs first. Inspect nearby files only when needed for a safe local
change or verification. Do not read broad logs, archives, unrelated history,
auth material, runtime state, caches, or past-source material by default.

If context expands, state why. Load narrower skills or references only when the
task needs their detail.

## Write Preconditions

Before local writes, confirm:

- current file contents or absence
- repo root
- relevant VCS status
- conflict risk with existing user changes

For parallel write work, require explicit branch and worktree ownership. Do not
create worktrees by default; use them only when the user requests parallel work
or the task truly needs separate write lanes.

## Side Effects And Human Gates

Classify side effects before acting: local read, local write, external read,
external write, dependency/tooling change, deploy/release/infra change,
protected action, destructive or irreversible action.

Human approval is required before release/deployment, CI/CD or infrastructure
changes, dependency changes, protected authority handling, protected data or
billing behavior, database migrations or schema changes, branch/worktree
deletion, external writes outside the owned review branch or PR, public release,
and destructive or irreversible/protected actions.

Do not use human-gate language for ordinary local implementation, local tests,
or reversible local edits.

## Verification Standard

An output can be called complete only when the requested behavior or artifact
exists, the smallest relevant verification was attempted, failures or skips are
stated plainly, and protected actions are not hidden behind residual-risk
wording.

Use the narrowest meaningful check first: local/direct check; then lint,
typecheck, build, contract, or smoke when relevant; then broader suites only for
shared behavior, release readiness, or PR scope.

Use commands backed by current repo files such as `Makefile`, `pyproject.toml`,
`tests/`, scripts, or CI. Do not invent checks.

For user-visible deliverables, prefer the closest runnable path over build-only
proof. If a check cannot run, report the check name, reason, result state, and
what would be needed to run it.

Result states: `passed`, `failed`, `blocked`, `skipped`, `not_applicable`.
Skipped or blocked checks require a reason.

## Repo Boundary And Storage

Repo truth is the tracked product, docs, tooling, templates, tests, plans,
artifacts, source roots, hooks, plugins, `.agents/`, and `.github/`.

Use existing implementation paths for product code. Use `Plan/<project_id>/`
only for lightweight plans and logs. Use `artifact/<project_id>/` only for
durable, useful outputs or evidence. Use `templates/` only for compact blank
formats that are still active.

Do not store raw bodies, auth material, local runtime ledgers, browser sessions,
auth metadata, or unrelated context in docs, plans, artifacts, templates, or
prompts.

Skills and plugins are routing helpers. They do not override the user request,
repo policy, allowed write targets, human gates, verification, or storage
rules.

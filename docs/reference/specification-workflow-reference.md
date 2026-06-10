---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-06-05
updated_at: 2026-06-10
---

# Goal, Spec, And Subagent Reference

Use this reference when a goal needs more structure than a direct edit, or when
subagents must split work. The purpose is to help ship the goal, not to produce
records.

## Trigger

Open this reference when:

- the goal is ambiguous enough that a short spec would prevent rework;
- behavior, non-goals, or Done criteria need to be made explicit before build;
- multiple agents will work in parallel or review separate surfaces;
- implementation details risk redefining desired behavior;
- the user asks for a spec or subagent workflow.

Do not open it for ordinary local implementation with clear source refs and Done
criteria.

## Default Flow

```text
Goal
  -> Scope
  -> Done criteria
  -> Direct implementation or mini-spec
  -> Verify
  -> Log result
```

Use subagents only when they materially reduce risk or cycle time:

```text
main agent
  -> scoped subtask
  -> subagent result
  -> main agent integrates
  -> verification
```

The main agent owns user communication, integration, and final judgment. If an
older workflow says `main_lane`, read it as this main-agent coordinator role,
not as a reason to create a separate record chain.

## Goal Brief

Before implementation, be able to state:

- Problem
- Desired outcome
- Done criteria
- Non-goals
- Source refs
- Allowed write targets
- Denied context
- Human gates, if any
- Verification method
- Next action

Write this into `Plan/<project_id>/plans/Plan_N0001.md` only when the work is
substantial or resumable. For small work, state it in the assistant response and
continue.

## Mini-Spec

Use a mini-spec when the goal needs design clarity. Keep it short:

```text
Goal:
Done when:
Out of scope:
Constraints:
Human gates:
Source refs:
Open questions:
```

For larger behavior work, add requirements as plain bullets. Use `REQ-*` and
`AC-*` IDs only when another person or agent must trace many items across
multiple changes. Do not create traceability matrices by default.

## WHAT/HOW Separation

Specs define WHAT must be true:

- user-visible behavior
- public/data contracts
- trust boundaries
- side effects and safety constraints
- acceptance or Done criteria
- non-goals and invariants

Implementation plans define HOW:

- file layout
- function/class/module names
- library choices
- branch/worktree strategy
- exact test commands
- refactor order

An implementation detail belongs in a spec only when it is itself an external
contract, persistence/trust-boundary requirement, safety constraint, or
irreversible behavior.

## Subagent Use

Subagents are optional. Use them for independent work, parallel review, or
bounded exploration. Do not create role-per-phase agents by default.

Each subagent receives:

```text
Task slice:
Source refs:
Allowed writes:
Denied context:
Done criteria:
Verification expected:
Return:
```

Subagents should not talk to the user directly. They return findings or patches
to the main agent, and the main agent decides what to integrate.

## Rework

Use a plain issue list first:

```text
1. Issue
   Impact:
   Owner:
   Fix:
   Verification:
```

Promote to formal IDs only for multi-lane conflicts where a plain list is not
enough.

## Human Gates

Human approval is needed for protected actions only:

- secrets or credentials
- external writes
- deploy/release
- dependency, CI, or infrastructure changes
- database migrations
- destructive Git or worktree deletion
- irreversible or protected actions

Do not require human approval merely because a spec exists.

## Artifacts

Default durable memory:

- `Plan/<project_id>/plans/Plan_N0001.md`
- `Plan/<project_id>/logs/Plan_N0001.log.md`

Optional artifacts only when useful:

- mini-spec
- task packet
- verification note
- optional lane map for real parallel work

Archived heavy-contract patterns are not defaults. They are not a runtime
scheduler. In short: not a runtime scheduler, worker heartbeat, queue, or
completion claim.

- approved spec freeze
- final handoff
- convergence decision
- traceability matrix
- source snapshot lock
- operational scorecard
- residual-risk carryover record

## Completion

Do not call work complete because records exist. Completion requires the
requested behavior or artifact plus honest verification. If the result is a
mock, draft, dry run, or records-only artifact, say so plainly.

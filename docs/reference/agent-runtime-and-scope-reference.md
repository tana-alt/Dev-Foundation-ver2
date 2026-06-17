---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
updated_at: 2026-06-10
---

# Runtime And Scope Reference

Use this reference when runtime-supplied scope, retries, generated output, or
optional parallel lanes need more detail than `AGENTS.md`.

## Trigger

Open this reference when:

- a task packet, scheduler, or prior output supplies scope;
- context boundaries are unclear;
- a retry may duplicate work or overwrite changed output;
- parallel lanes need scope before concrete branch/worktree operations.

Do not open it for ordinary implementation with named source refs.

## Scope Model

Useful scope:

- goal
- Done criteria
- source refs
- optional refs
- expected outputs
- allowed write targets
- denied context
- verification
- blockers
- open questions
- next action

Required context is the smallest set of refs needed to do the work safely.
Optional context is not default reading material.

## Context Expansion

Expand context only when:

- a named ref points to a required schema, template, or nearby implementation;
- verification requires a nearby command source;
- the task cannot be completed safely without a missing ref;
- security, privacy, or data sensitivity requires review.

State why context expanded. If scope remains unsafe or too broad, ask for a
scoped repair.

## Runtime Boundary

This repo does not define a scheduler, runtime queue, lock system, heartbeat, or
dashboard. External runtime scope is just input; it does not override
`AGENTS.md`, allowed writes, verification, storage boundaries, or human gates.

## Optional Parallel Lanes

Use lane maps for real parallel write work only.

Use `templates/parallel-lane-map.yaml` only when there is real parallel write
work. If a durable map exists, pass workers only the relevant lane slice plus
`lane_map_ref`. Each lane should carry only:

- lane task
- source refs
- allowed write targets
- denied context
- Done criteria
- verification
- branch/worktree ownership when needed

Do not give workers broad lane maps unless they manage the split. Most workers
need only their task slice.

## Retry And Output Safety

Retries must be idempotent or explicitly scoped. A retry must not duplicate
records, repeat irreversible side effects, or overwrite changed work without a
fresh conflict check.

For generated artifacts, prefer:

```text
generate temporary output -> validate -> replace target
```

Do not leave partial generated output as project truth.

## Continuation Notes

When one step feeds another, carry only what the next step needs:

- goal
- changed paths or artifacts
- evidence or command result
- blockers/open questions
- next action

Formal handoff records are not required by default.

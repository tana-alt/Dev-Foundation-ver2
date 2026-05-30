---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
---

# Agent Runtime And Scope Reference

Use this reference only when runtime, scope, handoff, or conceptual
parallel-lane boundaries need detail beyond the active contracts.

## Trigger

Open this reference when:

- a task packet, handoff, scheduler, monitor, selected skill, or external
  runtime supplies scope and you need to decide what context to open, decline,
  or request as rework;
- the task involves handoff compatibility, output-to-input boundaries,
  idempotent retry, duplicate output prevention, partial generated output, or
  atomic artifact replacement, even when the retry mentions artifact output or
  project truth but asks no repo-layout or storage-placement question;
- parallel lanes need conceptual input, scope, ownership, and handoff boundaries
  before any concrete branch or worktree operation;
- a human, lead agent, or scheduler needs a lane map without reading the repo.

Do not open this reference when:

- the task is a small scoped edit with named files and no runtime, handoff,
  retry, or context-boundary question;
- the only need is a packet, evidence, verification, or rework record schema;
- the only need is repo placement, storage, branch/worktree setup, conflict
  checks, PR evidence, migration acceptance, or verification command choice.

Adjacent references:

- Use `packet-evidence-and-rework-reference.md` for structured work contracts,
  evidence records, verification records, and rework record fields.
- Use `git-worktree-and-branch-reference.md` for concrete branch/worktree
  setup, local-write conflict checks, and PR preparation.
- Use `repo-boundary-and-storage-reference.md` only for repo layout, durable
  path placement, ignored local state, and storage-boundary decisions.

Expected effect after opening:

- Keep required context minimal, name any context-expansion reason, decline
  denied or broad context, return rework or scoped clarification for missing
  scope, check handoff compatibility, and make retry or generated-output
  decisions idempotent.

## Scope Model

Workers start from the user request, handoff, task packet, selected skill, or
provided scope. They do not begin by reading the repo, broad runtime maps, or
unrelated history.

A useful scope may include:

- `task_intent`
- `success_criteria`
- `source_refs`
- `optional_refs`
- `lane_map_ref`
- `expected_outputs`
- `allowed_write_targets`
- `denied_context`
- `evidence_required`
- `verification_required`
- `git_scope` or branch/worktree target when parallel write work is involved
- `blockers`
- `open_questions`
- `next_action`

Required context is the smallest set of refs needed to perform the work safely.
Optional context may improve quality, but it is not default reading material.

## Context Expansion

Expand context only when:

- a named ref points to a required schema, template, or nearby implementation;
- verification requires a nearby file or command source;
- the contract cannot be satisfied without a missing source ref;
- security, compliance, privacy, or data sensitivity requires review.

When context expands, record why. If context is still insufficient, return
rework or ask for the smallest scoped repair.

## Runtime And Scheduler Boundary

Scope may be supplied by a human, handoff, runtime, scheduler, monitor signal,
or selected skill. This foundation repo does not define a scheduler, runtime
queue, lock system, or plan ledger unless a current repo file explicitly adds
one.

A parallel lane map is a scoped planning artifact, not a scheduler, queue, lock
system, or claim source of truth. Use it to keep lane ownership, refs, write
targets, branch/worktree targets, and handoff shape explicit before deriving
per-lane work contracts.

If an external runtime or scheduler supplies scope, workers still follow the
same active contracts: bounded inputs, allowed write targets, evidence,
verification, storage boundaries, and human gates.

## Parallel Lane Map

Use `templates/parallel-lane-map.yaml` when parallel work must be split by a
human, lead agent, scheduler, or reviewer before worker sessions start. Store
instantiated maps under `Plan/<project_id>/lane-maps/` only when durable handoff
or review needs them.

Each lane carries the minimum worker input:

- lane name, owner/status, and task intent
- `source_refs` within the lane context budget
- `allowed_write_targets` and `denied_context`
- expected outputs and verification requirements
- branch and worktree target derived from `work_id` and `lane`

Do not give a worker the full lane map unless it is managing the split. Normal
worker input is the lane slice, named refs, and any required work-contract
fields. Run `make check-lanes` when lane maps are tracked.

## Retry And Atomic Output

Retries must be idempotent or explicitly scoped. A retry must not duplicate
records, repeat irreversible side effects, or overwrite changed work without a
fresh source ref or conflict policy.

Generated artifacts should use a safe write pattern when practical: produce
temporary output, validate it, then replace the target or emit an artifact ref.
Do not leave partial generated output as project truth.

## Handoff Compatibility

Workflow is output-to-input compatibility, not role hierarchy.

```text
prior output artifact
  -> next input requirement
  -> next bounded work unit
```

A handoff should carry source refs, artifact refs, evidence refs, verification
refs, blockers or open questions, and `next_action`. If the prior output does
not satisfy the next input contract, the next step is rework or scoped
clarification.

## Worker Limits

Specialist workers receive scoped input docs, output targets, local skill docs,
templates named by the handoff, and identity or runtime refs only when provided.
They do not self-expand into broad maps, root history, past-source material, or
unrelated project context.

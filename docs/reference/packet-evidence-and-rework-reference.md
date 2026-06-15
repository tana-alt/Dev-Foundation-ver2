---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
updated_at: 2026-06-10
---

# Task Packet, Evidence, And Rework Reference

Use this reference when a task needs a compact packet, evidence note,
verification note, or rework statement. Do not use it to create record-heavy
workflows.

Use `specification-workflow-reference.md` when the packet needs a mini-spec or
goal/spec/subagent split before work is delegated.

## Trigger

Open this reference when:

- a separate worker needs bounded task input;
- evidence must distinguish facts from inference;
- verification needs to be recorded outside the final answer;
- work is incomplete and needs a clear rework note.

Do not open it for a small direct edit or answer.

## Lightweight Task Packet

Use `templates/task-packet.yaml` or inline text:

```yaml
task:
  goal: ""
  done_when: []
  source_refs: []
  allowed_write_targets: []
  denied_context: []
  human_gates: []
  verification: []
  next_action: ""
```

Add branch/worktree fields only when parallel write work is actually happening.

## Evidence

Evidence should help another engineer reproduce a decision.

Keep:

- source refs
- observed facts
- inference clearly labeled as inference
- commands or methods used
- result
- missing evidence
- next action

Avoid:

- raw bodies
- credentials
- tokens
- browser sessions
- broad logs
- unrelated history
- local runtime state

## Verification Note

Use `templates/verification-note.md` or inline text:

```text
Check:
Command or method:
Result:
What passed:
What failed:
Not verified:
Next action:
```

Allowed result states:

- `passed`: check ran and passed
- `failed`: check ran and failed
- `blocked`: check could not run because a blocker exists
- `skipped`: intentionally not run; reason required
- `not_applicable`: not relevant to this work

## Rework

Use rework when the work is incomplete, unsafe, unverifiable, or mismatched with
the goal but has a clear next fix.

Simple shape:

```text
Rework:
Why:
Fix:
Verification:
Do not change:
```

Use `blocked` instead of rework only when progress requires user input,
external state, protected approval, or a missing dependency that cannot be
worked around locally.

## Optional Parallel Lane Map

Use `templates/parallel-lane-map.yaml` only when multiple agents have disjoint
write scopes or sibling branch risk. Lane maps are planning aids, not runtime
queues or completion evidence.

Durable lane maps, when truly needed, live under
`Plan/<project_id>/lane-maps/`.

## Legacy Work Contract Boundaries

`templates/work-contract.yaml` remains available for legacy worker packets, but
ordinary work should prefer the lightweight task packet above. When a work
contract is used, keep work contract boundaries explicit: goal, source refs,
allowed writes, denied context, branch/worktree scope when relevant, expected
outputs, and verification.

## Archived Record Families

Final handoff, convergence, traceability, residual-risk carryover, source
snapshot, operational scorecard, approved-spec freeze, and similar heavy
records are archived patterns. Do not create them unless the user explicitly asks for heavy-contract
archive migration or audit.

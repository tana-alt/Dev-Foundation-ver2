---
name: subagent-workflow-governance
description: Coordinate goal-first subagent work only when parallel or independent subtasks materially help; avoid record-heavy phase workflows.
---

# Subagent Workflow Governance

## Purpose

Use subagents to advance the goal, not to manufacture workflow records.

## Use When

- The user explicitly asks to use subagents or parallel agents.
- Work can be split into independent slices with clear source refs and allowed
  writes.
- A focused explorer can answer a bounded question while the main agent keeps
  implementing.
- A reviewer can inspect a separate risk surface in parallel.

## Do Not Use When

- A direct local implementation is faster.
- The next step is blocked on the delegated result.
- The split would require broad repo context or overlapping writes.
- The task only needs a spec, handoff, traceability, convergence, or residual
  risk record.

## Read First

- `docs/reference/specification-workflow-reference.md` only when the split needs
  goal/spec structure.

## Method

1. State the goal and immediate main-agent task.
2. Delegate only non-blocking, bounded slices.
3. Give each subagent source refs, allowed writes, denied context, Done
   criteria, and expected return shape.
4. Keep user communication and final integration in the main agent.
5. Integrate results into working changes and verification, not record bundles.

## Subagent Packet

```text
Task slice:
Source refs:
Allowed writes:
Denied context:
Done criteria:
Verification expected:
Return:
```

## Stop Conditions

Do not delegate if the subtask lacks source refs, has overlapping writes, needs
protected side effects, or would slow the critical path.

## Output

- delegated slices and why they matter
- main-agent work kept local
- integrated result
- verification
- remaining risk that affects goal completion

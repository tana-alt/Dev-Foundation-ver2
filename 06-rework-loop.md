---
status: draft
owner: foundation
source_of_truth_level: primary
created_at: 2026-05-02
---

# Rework Loop

## Purpose

Rework records keep failed or incomplete work small, explicit, and repairable.
They prevent workers from guessing when context is missing or validation fails.

## When To Use Rework

Use a rework record when:

- required context is missing
- the task intent is ambiguous
- expected output format cannot be satisfied
- verification fails
- evidence is insufficient
- a safety, privacy, compliance, or security issue appears
- the requested change conflicts with existing project truth

## Rework Principles

- Return the smallest useful correction request.
- Name the blocking condition.
- Cite the source or verification that exposed the issue.
- Describe what is needed next.
- Avoid broad restarts when a local repair is enough.

## Rework Types

- `missing_context`
- `ambiguous_instruction`
- `contract_mismatch`
- `verification_failed`
- `evidence_gap`
- `unsafe_assumption`
- `blocked_dependency`
- `scope_conflict`

## Rework Output

A useful rework record includes:

- work id
- project id
- rework type
- blocker summary
- evidence refs
- failed or missing requirement
- requested repair
- suggested next action

## Closing Rework

Rework is closed when:

- the missing input is supplied
- the contract is updated
- verification passes
- the risky assumption is removed
- the work is intentionally abandoned with a recorded reason

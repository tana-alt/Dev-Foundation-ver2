---
name: harness-ai-review
description: Use when explicitly running Harness AI review modes from a review command or writing/certifying reviewer verdicts against current candidate evidence.
---

# Harness AI Review

AI review is explicit. Default dispatch and gate run machine validation and
configured machine reviewers only.

## When

- `/review` maps to the `normal` AI mode: semantic and aggressive review.
- `/review arch` maps to the `arch` AI mode: architecture review.
- `/review full` maps to all configured AI review lanes.
- Do not call AI reviewers for ordinary machine verification, dispatch, gate,
  land, push, or PR status checks.

## How

- Run `HARNESS_ROLE=reviewer ./harness review <task_id> --mode normal` for
  semantic plus aggressive review.
- Run `HARNESS_ROLE=reviewer ./harness review <task_id> --mode arch` for
  architecture review.
- Run `HARNESS_ROLE=reviewer ./harness review <task_id> --mode full` when both
  normal and architecture AI review were explicitly requested.
- Verdicts must bind to the current candidate diff and machine evidence hashes.
- Certify only a fresh harness-owned approve verdict.

## What

- Semantic review checks meaning, task fit, evidence quality, and gate gaming.
- Aggressive review searches for counterexamples, hidden fragility, vulnerable
  design, and materially better simplifications or optimizations.
- Architecture review checks responsibility boundaries, state ownership,
  dependency direction, placement policy, extensibility, failure behavior, and
  evidence structure.

---
name: harness-evidence-journal
description: Use when writing or updating a Harness task evidence.md for compact-resume continuity, human readout, architecture/coding rationale, review authority, or ACP-only operation notes.
---

# Harness Evidence Journal

`evidence.md` preserves decisions that cannot be recovered from the diff,
verifier output, or generated artifacts alone. Keep it compact enough to survive
context compaction and useful enough for a human final readout.

## When

- Write evidence after material architecture, coding, review, ACP, land, push,
  or PR decisions.
- Prefer rationale, rejected alternatives, and authority hashes over copied
  command output.
- Do not store secrets, raw transcripts, auth material, or bulky logs.

## How

- Place task evidence beside the task contract when the project layout supports
  it: `.harness/<project>/tasks/<task_id>/evidence.md`.
- For legacy tasks, use `.harness/tasks/<task_id>/evidence.md` when tracked
  task evidence is appropriate, or `artifact/<task_id>/evidence/` for durable
  untracked run evidence.
- Record only decisions that future compacted context cannot infer from the
  source tree or runtime JSON.

## What

```md
# Evidence

## Architecture Judge

## Coding Judge

## Review Authority

## ACP-Only Operation Notes

## Final Human Readout
```

`Architecture Judge` explains responsibility boundaries, placement policy,
state ownership, failure behavior, and rejected designs.

`Coding Judge` explains implementation strategy, dead-code/test-speed choices,
coverage preservation, and why alternatives were rejected.

`Review Authority` records reviewer lanes, verdicts, certified hashes, consumed
evidence, and stale-evidence reasoning.

`ACP-Only Operation Notes` records important coordination decisions made without
human monitoring.

`Final Human Readout` summarizes final state, residual risk, skipped checks, and
the next human decision.

---
name: architecture-check
description: Use machine architecture_gate evidence without expanding context.
---

# Architecture Check

Use this skill only when existing harness evidence includes an
`architecture_gate` advisory, block, local significance, or significant
significance. The gate result is machine evidence, not an interpretation task.

## Read

- `verify-result.json`
- `candidate.diff` only when it is already in the reviewer packet
- named source refs already allowed by the task

## Do Not

- infer or override `architecture_gate.status`
- use writer-reported `architecture_significance`
- scan the whole repo
- create architecture docs or architecture artifacts
- treat `scope-map-reverse.json` as a hard gate
- use architecture health scores, DSM, drift, or smell counts as authority

## Output

Return one of: `approve`, `block`, or `needs_human_review`.
Include the reason code and the required next action in one short line.

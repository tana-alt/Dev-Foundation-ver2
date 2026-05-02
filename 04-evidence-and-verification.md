---
status: draft
owner: foundation
source_of_truth_level: primary
created_at: 2026-05-02
---

# Evidence And Verification

## Purpose

Evidence and verification make work auditable. They let another person or tool
understand what happened, why it happened, and how much confidence to place in
the result.

## Evidence

Evidence records should separate observed facts from inferences.

### Evidence Sources

- local files
- tests and command output
- screenshots or visual inspection
- product requirements
- user decisions
- external references
- prior project records

### Evidence Rules

- Cite source refs, not vague memory.
- Mark inferred conclusions as inference.
- Do not include secrets or credential material.
- Keep evidence compact and relevant.
- Preserve enough detail for a reviewer to reproduce the reasoning.

## Verification

Verification records describe what was checked.

Examples:

- lint
- typecheck
- unit tests
- integration tests
- runtime smoke test
- visual QA
- schema validation
- manual review

## Verification Result States

- `passed`: check ran and passed.
- `failed`: check ran and failed.
- `blocked`: check could not run because of a blocker.
- `skipped`: check was intentionally not run.
- `not_applicable`: check does not apply to this work unit.

## Residual Risk

Every non-trivial output should state residual risk. This can be short, but it
should be explicit.

Examples:

- "No browser QA was run because this was a docs-only change."
- "Unit tests passed, but no production-like API smoke test was available."
- "The plan depends on market research that has not been refreshed."

## Output Rule

An output is not complete until it includes:

- evidence refs
- verification attempted
- verification result
- unverified surfaces
- residual risk

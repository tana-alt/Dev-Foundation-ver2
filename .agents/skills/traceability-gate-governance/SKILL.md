---
name: traceability-gate-governance
description: Map requirements and acceptance criteria to implementation, tests, reviews, evidence, verification, and residual risk.
---

# Traceability Gate Governance

## Purpose

Ensure REQ/AC/NFR/EXC/SEC/DATA/API items are covered, verified, reviewed, or
explicitly carried as risk.

## Use When

- Requirement traceability matrix is in scope.
- Final handoff or convergence evidence is in scope.
- Requirements need coverage validation.

## Do Not Use When

- Task only selects context or changes hook wiring.
- No requirement IDs or final decision are involved.

## Read First

- `templates/requirement-traceability-matrix.yaml`
- `templates/final-handoff-record.yaml`
- `scripts/check-review-convergence.py` if present

## Context Budget

```yaml
max_selected_skills: 2
max_source_refs: 6
max_reference_docs: 1
broad_repo_scan_allowed: false
```

## Method

1. Gather requirement IDs from approved spec or lane contract.
2. Map each item to implementation, test, review, and evidence refs.
3. Mark each item as covered, gap, or carried_risk.
4. Link each gap to `INC-*` or `RISK-*`.
5. Ensure final handoff cites matrix and verification.

## Output

- traceability coverage verdict
- matrix update
- residual risk carryover items

## Stop / Carryover Conditions

Do not claim complete if critical/high gaps remain unresolved. Carry unverified
surfaces with source refs and next-flow seed.

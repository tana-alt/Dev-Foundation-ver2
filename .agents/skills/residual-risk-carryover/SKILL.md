---
name: residual-risk-carryover
description: Carry human gates, unverified surfaces, and deferred implementation into next workflow refs instead of terminal blocked status.
---

# Residual Risk Carryover

## Purpose

Convert pending human gates, unverified surfaces, and difficult implementation
areas into explicit residual risk and next-flow source refs.

## Use When

- Human gate is pending.
- Hard surface is deferred.
- Final handoff has unclosed risk.
- Next-flow seed is needed.

## Do Not Use When

- Immediate unsafe action requires hard stop.
- Missing permission prevents safe patch creation.
- Repository corruption prevents safe work.

## Read First

- `templates/residual-risk-carryover-record.yaml`
- `templates/final-handoff-record.yaml`
- `templates/inconsistency-register.yaml`

## Context Budget

```yaml
max_selected_skills: 2
max_source_refs: 6
max_reference_docs: 1
broad_repo_scan_allowed: false
```

## Method

1. Classify item as `INC-*` or `RISK-*`.
2. Assign severity.
3. Add source refs and affected requirement IDs when relevant.
4. Add owner lane or human decision path for high/critical risk.
5. Add `next_flow_seed`.
6. Update final handoff carryover.

## Output

- residual risk record
- final handoff carryover
- recommended next action

## Stop / Carryover Conditions

Use `blocked` only for immediate unsafe action, missing permission for an
attempted protected action, or repo corruption.

---
name: hook-validation-governance
description: Add or review deterministic local hooks, Make targets, and validation scripts.
---

# Hook Validation Governance

## Purpose

Add or review deterministic local hooks and Make targets without introducing
runtime monitoring or network-dependent checks.

## Use When

- `hooks/pre-commit` or `hooks/pre-push` changes.
- Makefile check targets change.
- Validation scripts are added or modified.
- Hook behavior or false-positive risk is reviewed.

## Do Not Use When

- Task is purely spec freeze, traceability, or review record content.
- Hook/check files are not in scope.

## Read First

- `hooks/pre-commit`
- `hooks/pre-push`
- `Makefile`
- `docs/reference/agent-operationalization-reference.md`
- `docs/reference/verification-ci-and-pr-reference.md` only for commands.

## Context Budget

```yaml
max_selected_skills: 2
max_source_refs: 6
max_reference_docs: 1
broad_repo_scan_allowed: false
```

## Method

1. Confirm each script exists before adding Make or hook targets.
2. Keep pre-commit fast and local.
3. Keep pre-push broader but offline.
4. Treat missing optional PR/lane context as `not_applicable`.
5. Do not add CI changes without explicit human approval.
6. Verify with targeted tests.

## Output

- hook changes
- check mapping
- Make targets
- verification refs
- residual risk for unverified hook surfaces

## Stop / Carryover Conditions

Stop or carry risk if requested hook requires network, external write, CI
mutation, or protected action.

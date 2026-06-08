---
name: spec-authority-governance
description: Govern approved specification authority, amendment, and WHAT/HOW separation.
---

# Spec Authority Governance

## Purpose

Implement or review approved specification authority without allowing
implementation policy to redefine behavior.

## Use When

- An approved specification packet, review, or freeze is added or changed.
- Frozen behavior may need amendment.
- Implementation policy risks redefining behavior.
- Behavior authority and amendment flow are in scope.

## Do Not Use When

- The task only changes hook wiring, context manifests, or residual-risk records.
- No spec authority, freeze, or amendment behavior is involved.

## Read First

- `templates/specification-packet.yaml`
- `templates/specification-review-record.yaml`
- `templates/implementation-policy-record.yaml`
- `docs/reference/specification-workflow-reference.md` only when named.

## Context Budget

```yaml
max_selected_skills: 2
max_source_refs: 6
max_reference_docs: 1
broad_repo_scan_allowed: false
```

## Method

1. Identify behavior authority source.
2. Confirm frozen WHAT is not changed through implementation docs.
3. Route behavior changes through explicit review or amendment records.
4. Ensure traceability IDs remain stable or are amended explicitly.
5. Record verification and residual risk.

## Output

- specification authority verdict
- review or amendment refs
- verification refs
- residual risk if behavior authority is unresolved

## Stop / Carryover Conditions

Stop if behavior is changed without spec authority. Carry unresolved human
approval as residual risk; do not mark behavior authority complete.

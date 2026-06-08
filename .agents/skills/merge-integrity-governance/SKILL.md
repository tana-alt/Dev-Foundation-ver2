---
name: merge-integrity-governance
description: Validate lane, branch, changed-path, sibling, and semantic-risk boundaries for parallel work.
---

# Merge Integrity Governance

## Purpose

Validate parallel lane changes against lane map, branch/worktree ownership,
changed paths, sibling refs, and traceability.

## Use When

- Parallel lanes or sibling branches are named.
- Merge integrity records or checks are added or run.
- PR/lane context is available.
- Changed-path declarations need validation.

## Do Not Use When

- No lane, branch, or merge context exists.
- Task is only skill routing or residual-risk record shaping.

## Read First

- `templates/parallel-lane-map.yaml`
- `scripts/check-lane-map.py`
- `docs/reference/git-worktree-and-branch-reference.md` only for Git mechanics.

## Context Budget

```yaml
max_selected_skills: 2
max_source_refs: 6
max_reference_docs: 1
broad_repo_scan_allowed: false
```

## Method

1. Validate lane map structure.
2. Compare declared changed paths with actual changed paths when available.
3. Check sibling path overlap when sibling refs are provided.
4. Flag shared interface, schema, config, or test-helper changes as semantic
   risk.
5. Route semantic risk to wide review or residual risk.

## Output

- merge-integrity check result
- unverified sibling refs
- semantic risk flags
- residual risk items if needed

## Stop / Carryover Conditions

No PR/lane context means `not_applicable`, not pass. Do not run a broad repo
scan to infer missing context.

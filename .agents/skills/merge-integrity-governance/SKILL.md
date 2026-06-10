---
name: merge-integrity-governance
description: Check branch, worktree, changed-path, and sibling-risk boundaries only for real parallel write work.
---

# Merge Integrity Governance

## Purpose

Prevent parallel agents from clobbering each other.

## Use When

- Parallel branches or worktrees are actually in use.
- Sibling branches may touch overlapping paths.
- Changed paths must be compared to an assigned scope.

## Do Not Use When

- Work is single-agent or read-only.
- The task only needs a plan, spec, or ordinary review.

## Read First

- `docs/reference/git-worktree-and-branch-reference.md`
- `scripts/check-lane-map.py` only when lane maps are still involved.

## Method

1. Identify branch/worktree ownership.
2. Compare changed paths with assigned write targets.
3. Flag path overlap and shared-interface risk.
4. Recommend rebase, rework, or human merge review when conflict risk is real.

## Output

- merge risk verdict
- overlapping paths or sibling refs
- required next action

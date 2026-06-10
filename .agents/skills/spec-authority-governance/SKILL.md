---
name: spec-authority-governance
description: Keep lightweight specs focused on observable WHAT and prevent implementation details from redefining the user's goal.
---

# Spec Authority Governance

## Purpose

Preserve the user's intended behavior while keeping specs small.

## Use When

- A spec, mini-spec, or requirement list is being written or revised.
- Implementation choices may change the intended behavior.
- A behavior change needs explicit user approval.

## Do Not Use When

- The task is ordinary implementation with clear Done criteria.
- The work only changes records, traceability, convergence, or handoff files.

## Method

1. Identify the current goal and Done criteria.
2. Separate WHAT from HOW.
3. Keep non-goals and human gates explicit.
4. Treat behavior changes as user-visible decisions, not implementation drift.
5. Prefer plain bullets over IDs unless many agents must trace many items.

## Output

- spec authority verdict
- behavior changes that need user decision
- implementation details that should move out of the spec
- verification needed to prove the goal

---
name: goal-completion-governance
description: Decide whether the user's goal is achieved, partially achieved, needs rework, or is blocked; records never count as completion by themselves.
---

# Goal Completion Governance

## Purpose

Keep completion tied to the requested outcome.

## Use When

- A task is nearing final response, handoff, or cleanup.
- Prior work produced records, mocks, specs, or dry runs and completion status
  needs a hard judgment.
- Review findings, unresolved checks, or deferred surfaces may affect whether
  the goal is actually done.

## Do Not Use When

- The task is only a small direct answer.
- A domain skill already defines a clearer completion test.

## Completion States

- `achieved`: requested behavior or artifact exists and relevant verification
  was attempted.
- `partially_achieved`: useful work exists, but requested behavior is not fully
  done.
- `rework`: implementation can continue locally with a clear fix.
- `blocked`: a protected action, missing external state, or missing user input
  prevents meaningful progress.
- `not_applicable`: no completion claim is being made.

## Method

1. Restate the goal.
2. Compare actual result to Done criteria.
3. Separate working behavior from records, mocks, specs, dry runs, and plans.
4. Check verification honestly.
5. State unverified surfaces and next action.

## Output

- goal result
- changed paths or artifact refs
- verification result
- unverified surfaces
- rework or blocker
- next action

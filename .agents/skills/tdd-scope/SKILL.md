---
name: tdd-scope
description: "Use when a bug fix, regression-prone logic change, API behavior change, or behaviorally significant reusable component has clear expected behavior and should be pinned with example-first proof, preferably fail-before when practical."
---


## Purpose

Use this skill for clear, narrow behavior that needs example-first proof beyond
the `AGENTS.md` Coding Principles baseline. Turn one important rule or
regression into the smallest repo-backed proof, preferably fail-before when
practical.

## Effect

When this skill fires, capture expected behavior as the smallest useful
behavior example before implementation when practical. Select only examples
that define the changed behavior or regression boundary: canonical path,
boundary/error case, or previously failing case. Name the observable evidence
and proof vehicle; use a focused failing test when it is the closest proof of
externally visible behavior, regression prevention, or API contract behavior.

## Use when

- Fixing a bug with clear reproduction.
- Adding important domain logic.
- Changing API behavior.
- Adding reusable components or utilities.
- Preventing a regression from returning.

## Do not use when

- The change is trivial styling, copy, formatting, renaming, mechanical
  migration, or dependency-only work.
- The task is only to add tests after an already-complete implementation.
- Expected behavior is ambiguous and needs `system-design`, `api-contract`, or
  user clarification first.
- The main need is release verification; use `release-check`.

## Success conditions

- A behavior-level example exists first when practical.
- The proof vehicle observes the behavior rather than implementation trivia.
- A focused failing test exists first when it is the closest proof.
- The implementation is the smallest change that passes the proof.
- Edge/error cases are covered when they define the behavior.
- Existing relevant tests still pass.

## Constraints

- Do not force TDD or example mapping for trivial styling or mechanical
  renames.
- Do not add broad snapshot tests when behavior tests are better.
- Do not leave skipped, disabled, or brittle tests.
- Do not overfit tests to implementation details unless necessary.

## Stop guidance

Stop before implementation if behavior is ambiguous, requires contract/design
decisions, or no repo-backed proof vehicle can observe the behavior. When the
behavior is clear but fail-before proof is impractical, use the closest
repo-backed substitute such as a fixture, reproduction command, log capture,
state dump, protocol trace, or local smoke, and state why. Stop expanding
examples once the changed behavior or regression boundary is covered.

## Output

- Behavior example being protected.
- Proof vehicle and why it observes the behavior, including fail-before result
  or closest substitute when practical.
- Minimal implementation change made to pass it.
- Verification command/result.
- Any behavior intentionally left untested.

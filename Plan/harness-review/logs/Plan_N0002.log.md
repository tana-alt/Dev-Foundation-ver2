# Plan_N0002 Log

Date: 2026-06-17

## Context

User requested a redo of the previous docs-oriented response. The corrected
instruction is to assume the loop and branch problem will be mechanically
managed by the harness, inspect the actual repository state, and create only a
proposal.

## Inputs Inspected

- Uploaded `merge-oracle-build-plan.md`.
- Uploaded `test_merge_serialization_race.py`.
- Current harness implementation files:
  - `runtime_paths.py`
  - `worktree.py`
  - `verify.py`
  - `submission.py`
  - `gate.py`
  - `integration.py`
  - `affected.py`
  - `land.py`
  - `push.py`
  - `review.py`
  - `mutation.py`
  - `scripts/check-frozen-paths.py`
  - `hooks/pre-commit`
  - `Makefile`

## Result

Created `Plan/harness-review/plans/Plan_N0002.md` as a proposal-only record.

The proposal keeps the implementation direction centered on harness-managed
runtime state and machine transitions:

- single-candidate merge oracle;
- push-time `remote_changed` oracle retry;
- N-candidate compose and leave-one-out localization;
- later certified-test interface;
- later mutation adequacy;
- later reviewer-authored test freezing.

## Important Boundary

This slice does not implement code and does not intentionally expand active docs
or routed reference docs. The proposal is intended for review before any
implementation slice.

## Verification

Not run. Proposal-only change.

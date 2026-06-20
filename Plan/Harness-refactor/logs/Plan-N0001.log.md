# Plan-N0001 execution log

Date: 2026-06-20

## Implemented slice

- Added contract harness domain / ports / adapters / application packages.
- Added SQLite StateStore with append-only event hash chain and integrity verification.
- Added filesystem content-addressed Evidence Store under harness runtime.
- Bound prepare / verify / submit / review verdict / gate / land / push authority artifacts to Evidence Store and StateStore events.
- Added compatibility `authority-manifest.json`.
- Changed scope handling so `allowed_paths` is treated as expected/advisory paths and only `forbidden_paths` creates hard violations.
- Added `impact_result` to verify evidence and kept legacy `scope.violation_count` as forbidden-only.
- Added `reader-impact` behavior while preserving `reader-scope` as an alias.
- Added local PR commands:
  - `harness pr create <task_id>`
  - `harness pr checks <task_id>`
  using `refs/harness/pr/<task_id>/<candidate_id>`.
- Added `state_store` summary to `harness status`.
- Added Make targets:
  - `make check-harness-architecture`
  - `make check-harness-state`

## Verification

- `uv run pytest -q tests/workflow_core/contract_harness`: passed, 10 tests.
- `make check-harness-state`: passed, 2 tests.
- `make check-harness-architecture`: passed, 10 tests.
- `uv run ruff check src/workflow_core/contract_harness tests/workflow_core/contract_harness`: passed.
- `uv run mypy tests/workflow_core/contract_harness`: passed.
- `uv run pytest -q tests/workflow_core/test_contract_harness.py -k "verify_rejects_forbidden or scope_map_evidence_mismatch_blocks_gate or status_query_returns_partial or reader_scope or submit_writes"`: passed, 3 tests.
- Existing broader harness acceptance run:
  - `uv run pytest -q tests/workflow_core/test_contract_harness.py tests/workflow_core/test_contract_harness_policy_acceptance.py tests/workflow_core/test_contract_harness_land_push_acceptance.py`
  - Result: 156 passed, 2 failed.
  - Failure 1: `test_context_audit_quantifies_role_context_without_budget_escape` due missing `skill_path:release-check`; `.agents/skills/release-check/SKILL.md` was already deleted in the dirty worktree before this implementation.
  - Failure 2: `test_plan_n0003_saved_under_plan_harness_review_plans` due missing `Plan/harness-review/plans/Plan_N0003.md`; `Plan/harness-review/` was already deleted in the dirty worktree before this implementation.

## Remaining risk

- Full Plan-N0001 is intentionally large. This execution shipped the runnable v0.2 foundation slice and compatibility hooks, not a destructive complete rewrite of every existing harness module into services.
- Existing unrelated dirty worktree deletions still block the full legacy harness acceptance suite.

## Subagent review follow-up

Date: 2026-06-20

Addressed review findings:

- `status` no longer treats `push-result.json` alone as completion authority. It requires StateStore integrity, current phase `complete`, a COMPLETE event payload, and referenced Git commit objects.
- `pr checks` now validates the current Git ref head under `refs/harness/pr/<task_id>/<candidate_id>` and recomputes `base_sha..head` diff hash before running verifiers.
- `land` remains compatible with non-PR legacy flow, but if a local PR was created, it requires a fresh `PR_CHECKED` StateStore event bound to the current Git ref and candidate hash.
- StateStore integrity now checks event payload `artifact_sha256` references against artifact rows and rehashes Evidence Store bytes.
- StateStore append and artifact writes now use `BEGIN IMMEDIATE` to serialize event-chain writes.

Additional verification:

- `uv run pytest -q tests/workflow_core/contract_harness`: passed, 15 tests.
- `make check-harness-state`: passed, 4 tests.
- `make check-harness-architecture`: passed, 15 tests.
- `uv run ruff check src/workflow_core/contract_harness tests/workflow_core/contract_harness`: passed.
- `uv run mypy tests/workflow_core/contract_harness`: passed.
- `uv run pytest -q tests/workflow_core/test_contract_harness.py -k "status_query_returns_partial or land_before_gate or land_with_nonmergeable or local_pr" tests/workflow_core/test_contract_harness_land_push_acceptance.py -k "land_before_gate or land_with_nonmergeable or push_before_land"`: passed, 3 tests.

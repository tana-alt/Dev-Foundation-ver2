---
plan_id: Plan_N0001
project_id: contract-lightening-20260610
plan_ref: Plan/contract-lightening-20260610/plans/Plan_N0001.md
---

# Contract Lightening Log

## 2026-06-10

- Confirmed current branch is
  `agent/foundation-subagent-spec-workflow/main/spec-workflow`.
- Existing unrelated dirty changes were present before this pass and were left
  untouched.
- Selected `scope-routing-governance`, `skill-authoring-governance`,
  `subagent-workflow-governance`, and hook/check routing because the task
  covers contract archival, skill lifecycle, and default verification behavior.
- Created archive snapshot under `archive/heavy-contracts-20260610/snapshot/`.
- Snapshot contains heavy contract references, templates, governance skills,
  operational check scripts, and related tests.
- Rewrote active contract docs around goal-first delivery, honest verification,
  and lightweight storage.
- Rewrote subagent/spec/merge/hook governance toward goal completion and
  explicit parallel-work risk only.
- Added `goal-completion-governance` and lightweight templates:
  `goal-brief.md`, `mini-spec.md`, `task-packet.yaml`, and
  `verification-note.md`.
- Retired traceability, residual-risk carryover, and review/fix/convergence
  skills from default routing while preserving them for archive audit.
- Changed `pre-push` so legacy heavy-contract checks run only when
  `FOUNDATION_LEGACY_CONTRACT_CHECKS=1`.
- Changed Makefile defaults so `check-fast`, `check-push`, and
  `check-required` do not force lane/heavy-contract checks; added
  `check-legacy-contracts`.
- Updated foundation tests and clean-checkout tests to match the lightweight
  default workflow.
- Verification:
  - `make check-fast`: passed.
  - `make check-push`: passed.
  - `make check-legacy-contracts`: passed.
  - `uv run pytest -q tests/test_clean_checkout_reproducibility.py tests/test_foundation_integrity.py tests/test_contract_models.py`: passed.
  - `make check-required`: failed only at `check-secrets`; gitleaks reports one
    pre-existing Git-history finding in commit `31c3995034b11ca999f6028107806ff8895c49ee`, not in the current worktree or index.

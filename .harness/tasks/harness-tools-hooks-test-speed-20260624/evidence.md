# Harness Tools Hooks Test Speed Evidence

## Scope And Archive Notes

- Source refs used: `AGENTS.md`, `docs/01-agent-operating-contract.md`, `.harness/policy.yaml`, this task `task.yaml`, generated runtime packets under the task state directory, and current writer worktree diff/status.
- Allowed write targets used: task scope/config, harness hook/tool code, focused tests, pytest config/lockfile, docs reference, this evidence note, and one archive location under `.harness/tasks/harness-tools-hooks-test-speed-20260624/archive/`.
- Denied context honored: no broad runtime log review, no secret/auth paths, no main worktree mutation, no PR, no push, no release/deploy action.
- Archived: `refactor.md` and `Plan/Harness-refactor/**` moved to `.harness/tasks/harness-tools-hooks-test-speed-20260624/archive/original-paths/`; `.harness/tasks/harness-tools-hooks-test-speed-20260624/archive/INDEX.md` preserves restore mapping.
- Archive placement: the archive is task-local because Harness candidate snapshots intentionally exclude `artifact/` paths for task candidates; task-local placement keeps the restore files in `candidate.diff`.
- Not archived: `.harness/bottleneck.yaml` is required Harness config for `./harness prepare`; `.agents/skills/**` is active repo-truth routing material per `AGENTS.md` and `.agents/skills/SKILL_INDEX.md`.
- Evidence placement: this tracked note moved from `Plan/harness-tools-hooks-test-speed-20260624/evidence.md` to `.harness/tasks/harness-tools-hooks-test-speed-20260624/evidence.md` to keep legacy task evidence beside the task contract.

## Authority And Judge Notes

- Architecture Judge: previous machine `verify-result.json` classified the candidate as `advisory` with significant routing/role/verification boundary changes and no hard architecture reason codes.
- Coding Judge: previous `quality-result.json` had no hard failures; it recorded review-only complexity/length flags in existing Harness code and tests.
- Review Authority: `.harness/review.yaml` requires quorum 3 from `reader-correctness`, `reader-scope`, and `semantic-ai`; previous gate evidence had all three fresh approves.
- ACP-only/operator notes: operator asked for reversible archive instead of deletion, required Harness config kept in place, stale scope/task/evidence placement fixed, and no external writes.

## Design Judgments

- Hook timing: `hook_stop.py` now checks only submitted evidence before dispatch. Plan-gate detection was dead code because both submitted and unsubmitted branches returned allow, and importing plan helpers added context and failure surface to every Stop event.
- Hook context: lifecycle hooks prefer `.harness-worktree.json` task identity over inherited `FOUNDATION_PROJECT_ID` or `FOUNDATION_TASK_ID`. This prevents a parent agent session from sending linked-worktree observations to the wrong task.
- Role tools: writer default tools are limited to the hot implementation path: `scope-map-forward`, `explain`, `context-audit`, `verify`, and `submit`. Coordination/report commands moved to the explicit `coordination` optional profile; measurement tools remain in the existing `measurement` profile.
- Rejected alternative: keeping every coordination tool in the default writer capsule preserved convenience but inflated launch/resume/handoff context for every writer, including the common verify/submit path.
- Test coverage reduction: rejected after semantic review. Default pytest now preserves full coverage and uses pytest-xdist parallel execution instead of deselecting long-running harness paths.

## Baseline

- `uv run pytest --durations=25 --durations-min=0.1` was stopped after more than 10 minutes with the suite still around 62% complete.
- `uv run pytest -q tests/workflow_core/test_contract_harness.py --durations=25 --durations-min=0.01` took 310.29 seconds and exposed repeated 5-24 second e2e tests.
- `uv run pytest -q tests/workflow_core/contract_harness -k strict --durations=20 --durations-min=0.01` took 63.44 seconds.

## Verification Log

- `uv run pytest -q tests/test_hook_scripts.py`: passed, 13 passed in 1.52 seconds, including wrong inherited `FOUNDATION_PROJECT_ID`/`FOUNDATION_TASK_ID` values for marker-based hook identity.
- `uv run pytest -q tests/test_hook_scripts.py tests/workflow_core/test_hook_events.py tests/workflow_core/test_contract_harness.py -k 'hook or prepare_capsule or explain_lists_agent_tools or active_harness_surface'`: passed, 26 passed in 24.86 seconds under xdist.
- `uv run ruff check src/workflow_core/contract_harness scripts tests`: passed.
- `uv run pytest -q --durations=15 --durations-min=0.5`: earlier slow-marker approach passed 471 tests with 134 deselected in 123.62 seconds, but was rejected as a coverage reduction.
- `uv run pytest -q -o addopts=''`: earlier full serial coverage passed, 605 passed in 646.68 seconds, proving coverage health before switching to parallel full coverage.
- `uv run pytest -q`: passed, 605 passed in 170.94 seconds with pytest-xdist `-n auto` and no slow deselection. Submit rework exposed daemon startup contention under review load, so final config uses fixed worker count.
- `uv run pytest -q` with `-n 4`: passed, 605 passed in 290.70 seconds; stable but too close to the 300-second verifier timeout.
- `uv run pytest -q` with `-n 6`: passed, 605 passed in 211.77 seconds; this is the final full-coverage default pytest setting.
- `uv run pytest -q tests/test_foundation_integrity.py -k 'pytest_collection_is_aggregate_foundation_gate or verification_reference_documents_pytest_aggregate_gate or worktree_policy_behavior'`: passed, 3 passed in 2.15 seconds.
- `uv run pytest -q tests/test_foundation_integrity.py -k 'artifact_project_records_have_manifest_and_allowed_sections'`: passed, 1 passed in 0.67 seconds for the rejected artifact placement. The archive later moved to task-local storage so Harness candidate snapshots include it.
- `HARNESS_ROLE=writer /Users/yamamotokaito/dev/Dev-Foundation-ver2/harness verify harness-tools-hooks-test-speed-20260624`: passed. Full pytest verifier passed with 605 tests in 201.13 seconds; ruff and policy verifiers passed. The canonical prepared scope still reports advisory warnings for archive/evidence/lockfile paths, while this candidate task scope and evidence note document those paths as the intended cleanup surface.

## Final Human Readout

- Archive decisions: `refactor.md` and `Plan/Harness-refactor/**` are archived under `.harness/tasks/harness-tools-hooks-test-speed-20260624/archive/original-paths/`; `.harness/bottleneck.yaml` and `.agents/skills/**` remain in place.
- Verification readout: focused hook/manifest tests, focused integrity tests, ruff, and Harness verify passed.
- Submit readout: the submit command is run after the final verify so the sealed candidate hash remains current; the runtime submission/dispatch artifacts and final assistant response carry the post-submit result.

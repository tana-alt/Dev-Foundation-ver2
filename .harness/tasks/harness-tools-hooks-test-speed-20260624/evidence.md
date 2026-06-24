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

## Operator And Harness Operations Addendum

- Director command intervention: the controlling worktree could not run `./harness prepare harness-tools-hooks-test-speed-20260624` while `.harness/bottleneck.yaml` was missing, so the director restored the required config from `HEAD` before spawning writer. This was a Harness bootstrap fix, not writer implementation work.
- Director launch friction: the first noninteractive writer launch failed because the director passed unsupported `codex exec --ask-for-approval never`. The corrected launch removed that option. Task comm `sha256:ee8b1520acd5110fc48ee821a3ea524df02db52c1f10cf038252517bfed29ada` and the writer launch log record this.
- Director process hygiene: an aborted broad pytest command remained running after user interruption, so the director killed the leftover verifier process before delegating to writer to avoid confusing Harness state.
- Director integration handoff: after writer reached `status: integrated`, the director ran `HARNESS_ROLE=integrator ./harness land harness-tools-hooks-test-speed-20260624` once to check whether the mechanical land path was clear. It failed with `candidate_apply_failed`, then the director delegated land recovery to an integrator agent.
- Director external-write attempt: after Harness local PR ref creation, the director attempted to push the owned review branch, not `main`. Pre-push hooks blocked before any remote write because `scripts/hook_stop.py` needed formatting, so the director delegated formatter recovery and PR creation to an integrator agent.
- Integrator land recovery: the integrator found two Harness land-path issues: an ignored integrator task packet blocked candidate apply, and ignored `.harness/tasks/.../archive/**` files were not staged by the land commit path. The integrator backed up the ignored packet under runtime state, adjusted local exclude state, and used a temporary in-worktree `land_core.py` patch so the running land process force-added candidate paths listed in `candidate.diff`. The temporary patch was not part of the landed source diff.
- Integrator hook-scope recovery: inherited `FOUNDATION_REPO_ROOT=/Users/yamamotokaito/dev/Dev-Foundation-ver2` caused hooks/checks in the integrator worktree to inspect the controlling main worktree. The integrator reran hooks/checks with `FOUNDATION_REPO_ROOT="$PWD"` so validation applied to the branch under preparation.
- PR creation recovery: Harness `pr create` produced a local Harness PR ref and runtime `pr-result.json`, but no GitHub URL. The integrator pushed the owned review branch and created GitHub PR 37 with `gh pr create`; no push to `main` was performed.

## Harness Improvement Candidates

- Make `status`, `land-result.json`, and `push-result.json` hash-aware. Stale results from older candidates repeatedly made the next action look like `push` even when the current candidate still needed land recovery.
- Make `spawn --role integrator` safe after land. Re-spawning the integrator reset the active integrator worktree to `origin/main`, so the landed commit had to be recovered from `land-result.json`.
- Make land staging force-add paths from `candidate.diff`, or explicitly reject ignored candidate paths before review. The reversible archive was valid only after `.harness/tasks/.../archive/**` made it into the landed commit.
- Avoid inherited `FOUNDATION_REPO_ROOT` for worktree-local hooks, or make hooks prefer `.harness-worktree.json`/`pwd` when running inside Harness worktrees. This prevents checks from reading a dirty controlling worktree.
- Separate local Harness PR refs from external GitHub PR creation in command names and result fields. `pr-result.json status=created` did not mean a GitHub PR URL existed.
- Include formatter checks in the land verifier plan when pre-push requires them. The land gate passed, but the first review-branch push was blocked by `ruff format --check`.
- Teach archive placement policy directly: `artifact/**` is durable evidence but excluded from candidate snapshots, while task-local archive under `.harness/tasks/<task_id>/archive/**` is landable.
- Preserve operator-friction records in a structured task event file. The comm note worked, but final human readout had to merge launch logs, comms, and integrator logs manually.

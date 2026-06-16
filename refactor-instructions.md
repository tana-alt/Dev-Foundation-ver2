# Refactor Instructions

Use this file as the implementation task packet:

```text
/goal refactor-instructions.md に書かれたことを完遂しろ
```

## Objective

Reduce concrete technical debt without changing existing behavior. Keep the
foundation's current contracts, harness evidence model, role boundaries, and
verification semantics intact while making future changes easier and safer.

This is not a rewrite request. The goal is small, evidence-backed refactoring in
safe phases.

## Approved Product Decisions

The following product decisions are already approved by the user and should not
be treated as open questions:

- Add schema versioning and migration handling for local SQLite stores that are
  durable across sessions, especially `runs.db` and `bench.db`.
- Move archived/heavy-contract compatibility checks behind an explicit legacy
  target instead of keeping them in the required default path.
- Add a default timeout to `bench_compare.py run`; include an override path, but
  do not leave automated benchmark runs unbounded.
- Replace implicit sorted-first integration target selection with an explicit
  policy schema.
- Classify hooks by whether they guard major/irreversible behavior or are
  auxiliary/observational. If a hook mixes these responsibilities, split the
  behavior so strict enforcement and observation are not coupled.
- Create a migration policy for harness worktree ownership markers and enforce
  safe reuse rules.

## Project Understanding

This repository is a Python-based agent workflow foundation. Its active behavior
is intentionally concentrated in `AGENTS.md`, `docs/01-agent-operating-contract.md`,
`docs/02-output-verification-contract.md`, and
`docs/03-repo-boundary-and-storage-contract.md`. Detailed material is routed
through `docs/reference/` and should be opened only when needed.

The project uses `uv`, Python `>=3.12,<3.15`, Ruff, pytest, strict mypy, and a
Makefile-driven verification surface. There is no packaged app build command:
`pyproject.toml` has `package = false`.

Primary user and agent workflows:

- Human/agent workflow governance through active docs and templates.
- Hook-based observation: SessionStart/PostToolUse/Stop scripts record or gate
  planned work.
- Quantitative evaluation: trajectory measurement, NFR samples, benchmark
  comparison, AB runs, verdicts, check results, and quality gate decisions.
- Contract harness workflow: writer prepares and verifies a task candidate,
  reviewers consume machine evidence and optional semantic review packets, and
  the integrator gates, lands, and optionally pushes through policy checks.
- A deterministic mock console renders sanitized workflow fixtures for local UI
  inspection.

Major entrypoints:

- `harness` -> `workflow_core.contract_harness.cli.main`
- `scripts/hook_post_tool_use.py`, `scripts/hook_stop.py`,
  `scripts/hook_session_start.py`
- `scripts/nfr_metric.py`, `scripts/bench_compare.py`, `scripts/abrun.py`,
  `scripts/check_runner.py`, `scripts/verdict.py`, `scripts/quality_gate.py`
- `scripts/measure_eval.py`, `scripts/surface_issues.py`,
  `scripts/completion_gate.py`
- `app/workflow_console/__main__.py`
- Make targets in `Makefile`

Major modules and responsibilities:

- `src/workflow_core/contracts.py`: Pydantic workflow records,
  `ApprovedWorkContract`, `GitScope`, transitions.
- `src/workflow_core/runtime.py`: runtime-agnostic port:
  `TrajectoryEvent`, `HandoffPacket`, `GateVerdict`, `AgentRuntime`.
- `src/workflow_core/completion.py` and `src/workflow_core/gate.py`:
  completion evidence and escape-pattern gate.
- `src/workflow_core/evaluation.py`, `measure.py`, `metrics_store.py`:
  trajectory scoring and retained/purgeable eval metrics.
- `src/workflow_core/runstore.py`, `nfr.py`, `bench.py`, `abrun.py`,
  `checkrun.py`, `verdict.py`, `quality_gate.py`: SQLite-backed measurement,
  statistical verdict, and policy aggregation surfaces.
- `src/workflow_core/contract_harness/`: task contract compilation, evidence
  hashes, scope maps, role enforcement, verify/submit/review/gate/land/push,
  worktree handling, policy, mutation, quality, and reviewer packet handling.
- `src/workflow_adapters/`: bounded Codex SDK, app-server, CommonDB, and mock
  adapters. Core must not import these.
- `src/workflow_ui/`: sanitized mock console rendering only.

Data flow:

1. `.harness/tasks/<task_id>/task.yaml` plus `.harness/*.yaml` inputs compile
   into runtime artifacts under Git common dir `harness-runtime`.
2. `prepare` writes `contract.lock.json`, `verifier-plan.json`, `capsule.json`,
   `agent-tools.json`, and `scope-map-forward.json`.
3. `verify` snapshots the current diff against `prepared_base_sha`, writes
   `candidate.diff`, `scope-map-reverse.json`, `quality-result.json`,
   `tool-candidates.json`, verifier results, and `verify-result.json`.
4. `submit` checks fresh evidence hashes, optionally runs mutation checks, and
   writes `submission.json`.
5. reviewers write harness-owned verdict JSON under the task runtime directory.
   Semantic reviewers receive the diff, test interpretation, quality/tool/
   metric/mutation/scope-map evidence, and reviewer policy anchors.
6. integrator `dispatch`/`integrate` runs missing reviewers and gate.
7. `land` creates an integrator worktree and commit after gate passes.
8. `push` policy-checks external writes, creates rescue refs and remote locks,
   updates the remote branch, and syncs local target branch state.

External dependencies and side effects:

- Local filesystem writes to runtime task JSON, SQLite DBs, traces, and
  artifacts.
- Local subprocess execution for verifiers, Make targets, benchmark commands,
  checks, mutation commands, and semantic reviewer commands.
- Git operations: status, diff, fetch, worktree add/reset/clean, apply, commit,
  push, refs.
- External writes are only Git remote pushes and are policy-gated.
- Local network use appears only in AB server health checks on `127.0.0.1`.
- No application auth, billing, notifications, queue system, cloud storage, or
  service API runtime was found. Secret handling is hygiene/scanning only.

## Behaviors To Preserve

- `workflow_core` must remain runtime-agnostic. Do not import concrete Codex,
  Claude, app-server, CommonDB, UI, or adapter modules into `workflow_core`.
- Role enforcement via `HARNESS_ROLE` must preserve writer/reviewer/integrator
  command boundaries.
- Evidence freshness must remain hash-bound. Do not replace hash validation
  with manual claims.
- Runtime state must stay under `HARNESS_RUNTIME_ROOT` or Git common dir
  `harness-runtime`; never move runtime state under tracked `.harness/state`.
- `prepare`, `verify`, `submit`, `review`, `gate`, `dispatch`, `integrate`,
  `worktree`, `affected`, `land`, `push`, `scope-map`, and `tools` CLI output
  shapes must remain compatible with existing tests unless a human approves a
  contract change.
- `candidate.diff`, `verify-result.json`, `submission.json`, reviewer verdicts,
  `gate-result.json`, `land-result.json`, `push-result.json`, and sync evidence
  must keep their current meaning.
- Scope maps are advisory evidence, not hard implementation constraints.
  The observed implementation scope is the diff.
- Quality metrics are routing evidence. Hard machine failures cover objective
  artifact breakage; semantic reviewer judgement handles grey-zone readability,
  extension, and anti-gaming concerns.
- Tool candidates must remain durable and reusable: no task-specific or
  check-gaming tools should be treated as accepted evidence.
- Mutation checks must not mutate the candidate; if they do, they must fail.
- `make check-foundation` must remain CI's Foundation Robustness Gate.
- R6 exit-code convention must be preserved:
  `0=pass`, `1=quality fail/regression`, `2=inconclusive`, `3=tool error`.
- Hooks must not trap sessions on environment failures unless the existing
  fail-open contract is deliberately changed with human approval.
- Sanitized UI/adapters must not store raw thread bodies, raw terminal logs,
  credentials, browser sessions, local runtime state, secrets, or raw private
  context.
- AB worktrees must stay outside the measured repo and cleanup must remain
  ownership-safe.
- External pushes must remain policy-gated, rescue-ref backed, lock protected,
  and followed by local target branch sync.

## Non-Negotiables

- Do not mix existing uncommitted changes with new changes. Record the initial
  `git status --short` before editing and treat pre-existing changes as owned
  by someone else.
- Do not revert user changes.
- Do not do broad formatting, whole-repo rewrites, or incidental cleanup.
- Do not change behavior just because a refactor makes it convenient.
- Do not loosen tests, roles, evidence checks, secret checks, or CI gates.
- Do not delete archives, legacy templates, or heavy-contract checks unless the
  user explicitly approves that product decision.
- Do not add runtime queues, dashboards, lock ledgers, broad logs, memory DBs,
  vector stores, plugin systems, or scheduler behavior.
- Do not perform protected actions without explicit approval: release,
  deployment, CI/CD mutation, dependency changes, secret handling, DB schema
  migration, protected branch write, worktree deletion, or external writes.
  Approval is granted only for the local SQLite schema-versioning and migration
  refactor described in this file; unrelated DB or external-store changes still
  require approval.
- Each phase must end with relevant verification and a short report of changed
  files plus command results.

## Stop And Ask Conditions

Stop and ask before implementing if any of these arise:

- Correct behavior cannot be inferred from tests and active docs.
- Tests and implementation contradict each other.
- A proposed deletion may remove an active CLI, template, check, or evidence
  surface.
- A change affects public CLI command names, output JSON fields, exit codes, or
  environment variables.
- A SQLite change drops or rewrites retained data without a tested migration
  path, or changes durable DB semantics beyond schema versioning/migration.
- A change affects protected Git remote write behavior, push locking, rescue
  refs, rollback semantics, or local branch sync.
- A change affects secrets, auth-like boundaries, external integrations,
  network behavior, or human-gated SDK/app-server execution.
- A change would convert advisory scope maps or quality flags into hard policy
  without an existing test or explicit approval.
- A hook change silently makes auxiliary/observational hooks strict, or mixes
  irreversible enforcement with observation without a split and tests.
- A migration path for existing runtime worktrees or SQLite stores cannot be
  made safe and testable.
- Multiple reasonable product designs exist and tests do not decide between
  them.

## Baseline Commands

Before editing, record:

```sh
git status --short
git rev-parse --show-toplevel
git branch --show-current
```

Then run the narrowest meaningful baseline for the intended phase. Do not claim
full readiness if broad checks are skipped due to dirty worktree or missing
tools.

Core baseline options:

```sh
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q tests/workflow_core
uv run pytest -q tests/test_hook_scripts.py tests/test_metric_cli_exit_codes.py tests/test_code_quality.py
```

Contract harness focused baseline:

```sh
uv run pytest -q tests/workflow_core/test_contract_harness.py \
  tests/workflow_core/test_contract_harness_policy_acceptance.py \
  tests/workflow_core/test_contract_harness_land_push_acceptance.py
```

Broader gates when appropriate and toolchain is available:

```sh
make check-fast
make check-required
make check-ci
make check-foundation
```

`make check-required` and above require local shell/static/secret tooling such
as `shellcheck` and `gitleaks`.

## Debt Map

### D1. Existing dirty and untracked implementation surface

- Evidence: `git status --short` shows many modified files and untracked
  `src/workflow_core/contract_harness/`, `harness`, and harness tests.
- Why debt: implementation ownership is unclear; future refactors can easily
  blend baseline changes with new edits.
- Impact: high for any refactor touching harness, docs, scripts, or tests.
- Change risk: high if diffs are reviewed as one blob.
- Improvement: begin with a status snapshot; keep refactor commits/patches
  narrow; do not normalize unrelated existing changes.
- Verification: report changed files from this task separately from baseline
  dirty files.
- Implement now: yes, as process discipline only.

### D2. Duplicate contract schemas

- Evidence: `src/workflow_core/contracts.py` defines Pydantic
  `ApprovedWorkContract` and `GitScope`; `src/workflow_adapters/codex_sdk_adapter.py`
  defines dataclass versions with parallel validation.
- Why debt: schema drift can let adapter behavior diverge from core contract
  behavior.
- Impact: adapters, work-contract validation, headless Codex prompt building,
  tests under `tests/workflow_adapters/`.
- Change risk: medium. Constructor APIs and tests depend on current dataclass
  shapes.
- Improvement: first add tests that prove equivalent validation. Then extract
  shared validation helpers or make adapter conversion depend on the core model
  while preserving public adapter return types.
- Verification: `uv run pytest -q tests/workflow_adapters tests/workflow_core/test_approved_work_contract.py`.
- Implement now: yes only as a compatibility-preserving refactor. Stop if the
  core and adapter schemas disagree on product semantics.

### D3. Contract harness artifacts are generic dicts

- Evidence: `contract_harness/verify.py`, `review.py`, `semantic_review.py`,
  `gate.py`, `submission.py`, `land.py`, and `push.py` read/write many JSON
  objects as `dict[str, Any]`.
- Why debt: field names such as evidence hashes are repeated manually, making
  stale checks and review freshness easy to break.
- Impact: verify, submit, review freshness, semantic reviewer packets, gate,
  land, push.
- Change risk: high if JSON output changes.
- Improvement: introduce small typed helpers or dataclasses for evidence hash
  bundles first. Do not convert every artifact in one pass.
- Verification: focused harness tests plus mypy and Ruff.
- Implement now: yes in a narrow slice. Preserve JSON output exactly.

### D4. Evidence-hash construction is duplicated

- Evidence: freshness fields are assembled in `verify.py`, `review.py`,
  `semantic_review.py`, `submission.py`, and `gate.py`.
- Why debt: adding or changing one evidence artifact can stale the wrong
  reviewer lane or fail to block stale submissions.
- Impact: semantic reviewer stale behavior, gate preflight, submit validation,
  evidence mismatch failures.
- Change risk: high because tests assert exact stale/fresh behavior.
- Improvement: create one `contract_harness/evidence.py` helper that computes
  machine, semantic, submission, and gate evidence hashes from current runtime
  artifacts.
- Verification: `test_scope_map_reverse_reaches_semantic_reviewer_and_stales_only_semantic`,
  `test_quality_evidence_stales_only_semantic_reviewer_and_recovers_minimally`,
  `test_missing_quality_evidence_blocks_gate`, `test_scope_map_evidence_mismatch_blocks_gate`,
  and full harness focused baseline.
- Implement now: yes, test-first and no output-shape change.

### D5. CLI parser and dispatch responsibilities are concentrated

- Evidence: `src/workflow_core/contract_harness/cli.py` handles argument
  parsing, role dispatch, command handlers, JSON output, and deferred command
  behavior in one file.
- Why debt: adding commands or changing role boundaries risks accidental output
  or permission changes.
- Impact: all `./harness` commands and role tests.
- Change risk: medium.
- Improvement: split parser construction from handler dispatch only after
  preserving current command names, flags, JSON output, and exit codes.
- Verification: `test_role_boundaries_reject_disallowed_commands`, explain/tool
  tests, and harness focused baseline.
- Implement now: yes after evidence helper slice, if still small.

### D6. `quality.py` mixes quality metrics, tool-candidate detection, durable
checks, script probing, and policy anchors

- Evidence: `src/workflow_core/contract_harness/quality.py` contains AST
  inspection, candidate classification, subprocess help probing, status
  synthesis, and artifact payload creation.
- Why debt: subjective readability flags and mechanical durable checks are
  different concerns; mixing them makes gaming/threshold changes risky.
- Impact: verify, submit, semantic review, tool candidate acceptance.
- Change risk: medium to high.
- Improvement: split into internal modules or helper sections:
  `quality_metrics`, `tool_candidates`, and `quality_artifacts`. Keep policy
  anchors abstract and avoid changing thresholds.
- Verification: quality/tool candidate tests in `test_contract_harness.py`,
  `tests/test_code_quality.py`, Ruff C90.
- Implement now: yes in small pure-refactor slices. Do not change thresholds
  or hard-vs-review-required semantics without approval.

### D7. Contract harness worktree ownership proof is weaker than AB worktrees

- Evidence: `contract_harness/worktree.py` reuses a path when `.git` exists,
  then runs `checkout --detach`, `reset --hard`, and `clean -fd`; `abrun.py`
  uses marker protection for owned worktrees.
- Why debt: a wrong path with `.git` can be destructively cleaned.
- Impact: writer/reviewer/integrator worktree creation and reuse.
- Change risk: high because this changes safety behavior for existing worktree
  directories.
- Improvement: add a harness-owned marker for newly-created worktrees and
  require marker match before reuse. Create an explicit migration policy for
  pre-existing unmarked worktrees so safe reuse is possible only when ownership
  is proven.
- Verification: land/push acceptance tests plus new tests for refusing foreign
  worktree paths, reusing marked harness worktrees, and migrating or rejecting
  unmarked worktrees according to the policy.
- Implement now: yes. Include the migration policy and tests.

### D8. Integration target selection is implicit

- Evidence: `contract_harness/policy.py::integration_target` selects the first
  sorted remote and first sorted branch from `policy.yaml`.
- Why debt: multiple remotes/branches become ambiguous, and sorted order is not
  a product decision.
- Impact: affected-set, worktree base, land, push.
- Change risk: medium to high if any config currently relies on sorted first.
- Improvement: add an explicit integration target schema in `policy.yaml`.
  Replace sorted-first target selection with validated target lookup and clear
  errors for ambiguous or missing policy.
- Verification: policy acceptance tests plus multi-remote and missing-target
  policy tests.
- Implement now: yes. The explicit schema decision is approved.

### D9. Subprocess stdout/stderr may be stored too broadly

- Evidence: `contract_harness/mutation.py` writes stdout/stderr in error
  results; semantic reviewer and verifier paths also consume subprocess output.
- Why debt: repo policy forbids broad logs/secrets in durable records. Runtime
  JSON is not tracked, but it can still become evidence material.
- Impact: mutation failure artifacts, reviewer failure reasons, debugging.
- Change risk: medium. Tests may assert reason content.
- Improvement: bound and redact persisted output. Keep enough tail for
  diagnosis, but do not store raw unbounded logs.
- Verification: mutation handoff tests plus new test proving long/secret-like
  output is bounded/redacted.
- Implement now: yes if output field names remain and tests define bounds.

### D10. `bench_compare.py run` lacks command timeout

- Evidence: `_measure_command` in `scripts/bench_compare.py` calls
  `subprocess.run(command, capture_output=True, text=True)` without timeout.
- Why debt: automated gates can hang indefinitely.
- Impact: benchmark CLI and any harness packet exposing it as a tool.
- Change risk: medium if callers expect no timeout.
- Improvement: add a default timeout for benchmark command iterations, with a
  CLI/env override for intentionally long benchmarks.
- Verification: metric CLI exit-code tests plus new tests for default timeout,
  timeout override, and timeout exit code.
- Implement now: yes. Default timeout enforcement is approved.

### D11. SQLite stores have bootstrap schemas but no migration/version story

- Evidence: `SqliteStore` executes `CREATE TABLE IF NOT EXISTS`; `runs.db`,
  `eval.db`, `nfr.db`, and `bench.db` schemas do not use `PRAGMA user_version`
  or migrations.
- Why debt: `runs.db` and `bench.db` are described as durable enough to persist
  across sessions, so future schema changes can silently drift.
- Impact: AB pipeline, benchmark baselines, quality gate history.
- Change risk: high because existing DB files may already exist.
- Improvement: implement schema versioning and migration policy. Prefer a small
  `schema_meta` or `PRAGMA user_version` strategy, fixture old DBs in tests,
  and keep bootstrap behavior for fresh stores.
- Verification: migration tests with old fixture DBs.
- Implement now: yes. The durability/versioning decision is approved.

### D12. Large legacy validators are grandfathered

- Evidence: `tests/test_code_quality.py` exempts
  `scripts/agent_operational_checks.py` and `scripts/check-lane-map.py`;
  current file sizes are roughly 798 and 1537 lines.
- Why debt: they are harder to review and outside new readability budgets.
- Impact: legacy heavy-contract compatibility checks and lane validation.
- Change risk: high because these are validator scripts with broad fixture
  coverage.
- Improvement: split only by behavior-preserving extraction, one validator at a
  time, backed by current tests. Do not remove the grandfather entry until the
  test proves the file is under budget.
- Verification: `uv run pytest -q tests/test_lane_map_check.py tests/test_agent_operational_helpers.py tests/test_code_quality.py`.
- Implement now: only if explicitly assigned. Otherwise leave as lower
  priority.

### D13. Duplicate scratch Git/test harness helpers

- Evidence: helper functions for `git`, temporary repos, harness invocation,
  and config writing repeat across contract harness, policy, land/push, AB, and
  CLI tests.
- Why debt: fixtures drift and test timeouts/role env behavior can diverge.
- Impact: tests only, but many high-risk acceptance tests depend on them.
- Change risk: medium. Bad fixture refactors can hide behavioral coverage.
- Improvement: extract shared test helpers into one test support module in a
  small slice, preserving each test's observable scenario.
- Verification: all affected tests before and after extraction.
- Implement now: yes, after functional refactors or as an initial test-only
  cleanup.

### D14. Hook Stop fail-open is an intentional enforcement gap

- Evidence: `scripts/hook_stop.py` documents fail-open behavior when pydantic,
  harness, or timeout problems occur.
- Why debt: strict completion enforcement cannot rely solely on hooks.
- Impact: user sessions and planned work gating.
- Change risk: high. Changing fail-open can trap sessions if observational
  behavior is made strict.
- Improvement: classify each hook responsibility as major/irreversible
  enforcement or auxiliary/observational. If mixed, split strict enforcement
  from observation so hook policy is explicit.
- Verification: hook script tests proving observational paths still fail open
  and strict enforcement paths are isolated and intentional.
- Implement now: yes for classification and responsibility split. Do not make
  every hook strict by default.

### D15. Heavy-contract archive compatibility remains wired

- Evidence: Makefile includes legacy/heavy-contract checks and templates remain
  present; active docs say heavy records are archived patterns, not defaults.
- Why debt: default gates may carry old workflow cost and obscure current
  goal-first behavior.
- Impact: CI/local verification and template inventory.
- Change risk: high because Make targets and foundation integrity tests assert
  current wiring.
- Improvement: move archived/heavy-contract compatibility checks behind an
  explicit legacy target. Keep the checks available; remove them from required
  default gates only with tests and docs updated.
- Verification: foundation integrity tests, Make target tests, and CI workflow
  checks.
- Implement now: yes. The legacy-target decision is approved.

## Implementation Phases

### Phase 0. Baseline and ownership

1. Record `git status --short`, repo root, branch, and relevant worktree state.
2. Identify which files are pre-existing dirty/untracked. Do not clean or
   revert them.
3. Run the narrow baseline for the first intended slice.
4. If baseline fails, decide whether the failure is pre-existing. Do not hide
   it; report it before changing code.

### Phase 1. Add or confirm safety tests

Before refactoring a behavior, ensure there is a test or direct reproduction for
that behavior. Prioritize tests around:

- evidence hash freshness and stale recovery,
- role command boundaries,
- semantic reviewer packet contents,
- quality/tool/mutation/metric/scope-map artifacts,
- land/push rescue refs, locks, and local sync,
- worktree reuse safety if touching worktree code,
- CLI exit-code compatibility if touching scripts.

### Phase 2. Safe test-helper cleanup

If the implementation task needs test edits, extract duplicated scratch Git and
harness helper setup carefully. Keep test names and scenarios readable. Do not
merge unrelated tests or reduce coverage.

Recommended verification:

```sh
uv run pytest -q tests/workflow_core/test_contract_harness.py \
  tests/workflow_core/test_contract_harness_policy_acceptance.py \
  tests/workflow_core/test_contract_harness_land_push_acceptance.py \
  tests/test_ab_pipeline_acceptance.py
```

### Phase 3. Centralize evidence hash helpers

Create a narrow helper for evidence bundle calculation. Move repeated evidence
hash assembly into it without changing artifact JSON shapes.

Do this before larger harness refactors so later edits use one source of truth.

Recommended verification:

```sh
uv run pytest -q tests/workflow_core/test_contract_harness.py
uv run pytest -q tests/workflow_core/test_contract_harness_policy_acceptance.py
```

### Phase 4. Split quality/tool-candidate internals

Separate mechanical quality inspection from tool-candidate durability checks.
Keep thresholds, statuses, policy anchors, and reviewer packet semantics
unchanged.

Recommended verification:

```sh
uv run pytest -q tests/workflow_core/test_contract_harness.py -k "quality or tool_candidate or semantic"
uv run pytest -q tests/test_code_quality.py
uv run ruff check src/workflow_core/contract_harness tests/workflow_core/test_contract_harness.py
```

### Phase 5. Slim contract harness CLI structure

Only after Phase 3, split parser construction and command handlers if it
reduces complexity. Preserve command names, flags, roles, stdout JSON/text, and
exit codes.

Recommended verification:

```sh
uv run pytest -q tests/workflow_core/test_contract_harness.py -k "role_boundaries or explain or tool"
uv run pytest -q tests/workflow_core/test_contract_harness_land_push_acceptance.py
```

### Phase 6. Add worktree ownership safety only with tests

Add marker-based ownership proof for newly-created contract harness worktrees.
Create the approved migration policy for pre-existing unmarked worktrees and
enforce it before any destructive checkout/reset/clean reuse.

Recommended verification:

```sh
uv run pytest -q tests/workflow_core/test_contract_harness_land_push_acceptance.py
uv run pytest -q tests/workflow_core/test_abrun.py
```

### Phase 7. SQLite schema versioning and migrations

Add version tracking for durable local SQLite stores, starting with `runs.db`
and `bench.db`. Keep fresh-store bootstrap simple, but make existing-store
upgrade behavior explicit and tested.

Recommended verification:

```sh
uv run pytest -q tests/workflow_core/test_runstore.py tests/workflow_core/test_bench.py
uv run pytest -q tests/test_ab_pipeline_acceptance.py tests/test_metric_cli_exit_codes.py
```

### Phase 8. Policy integration target schema

Replace sorted-first integration target selection with an explicit policy
schema. Update tests and docs/templates that create harness policy fixtures.
Use clear errors for missing or ambiguous targets.

Recommended verification:

```sh
uv run pytest -q tests/workflow_core/test_contract_harness_policy_acceptance.py
uv run pytest -q tests/workflow_core/test_contract_harness_land_push_acceptance.py
```

### Phase 9. Legacy gate routing

Move archived/heavy-contract compatibility checks out of required default gates
and behind an explicit legacy target. Keep the checks callable. Update active
docs and tests so default verification reflects current goal-first behavior.

Recommended verification:

```sh
uv run pytest -q tests/test_foundation_integrity.py tests/test_clean_checkout_reproducibility.py
make check-fast
```

### Phase 10. Hook responsibility split

Classify hook paths into major/irreversible enforcement and
auxiliary/observational behavior. If a hook mixes the two, split it so
observability cannot unexpectedly block a session and strict enforcement has a
clear, tested boundary.

Recommended verification:

```sh
uv run pytest -q tests/test_hook_scripts.py tests/workflow_core/test_hook_events.py
```

### Phase 11. CLI hardening

Small, compatible hardening is allowed and should include the approved default
benchmark timeout:

- default timeout for `bench_compare.py run` plus override,
- bounded/redacted persisted subprocess output,
- shared env/store path helpers for script CLIs.

Recommended verification:

```sh
uv run pytest -q tests/test_metric_cli_exit_codes.py tests/workflow_core/test_bench.py
uv run pytest -q tests/workflow_core/test_contract_harness.py -k "mutation or semantic"
```

### Phase 12. Proposal-only design items

Do not implement these without human decision:

- RFC/multi-writer orchestration,
- changing quality thresholds or hard/review-required semantics,
- changing public JSON artifact contracts.

## Verification Requirements

For every phase:

1. Run the closest focused tests first.
2. Run Ruff and mypy for touched Python surfaces.
3. Run broader tests only when the change touches shared behavior.
4. Report skipped checks with reasons.
5. If a test fails, do not continue to unrelated phases until the failure is
   understood.

Minimum final verification for a harness-focused refactor:

```sh
uv run ruff format --check src scripts tests
uv run ruff check src scripts tests
uv run mypy
uv run pytest -q tests/workflow_core
uv run pytest -q tests/test_hook_scripts.py tests/test_metric_cli_exit_codes.py tests/test_code_quality.py
```

Run `make check-required` when the dirty worktree and local toolchain make it
honest to do so. If not run, state exactly why.

## Reporting Format

End with:

- Initial baseline status: command, result, and notable pre-existing failures.
- Changed files: list only files changed by this task.
- Behavior preserved: short bullets tied to tests.
- Verification: command -> passed/failed/skipped.
- Open questions or stopped items.
- Residual risk: only concrete risk that remains after verification.

Do not claim completion from records, plans, or explanations alone. Completion
requires the refactor to exist and relevant checks to have been attempted.

## Out-of-scope Items

- Broad product redesign or whole-repo rewrite.
- Implementing RFC decision processing.
- Implementing multi-writer orchestration.
- Adding dashboards, queues, memory DBs, vector stores, or provider SDK
  orchestration.
- Changing external push behavior without explicit approval.
- Changing DB schemas outside the approved local SQLite migration/versioning
  scope.
- Removing archived or legacy compatibility surfaces instead of routing them to
  explicit legacy checks.
- Changing public CLI contracts or JSON artifact fields without approval.
- Replacing semantic reviewer judgement with purely mechanical metrics.
- Making scope maps hard constraints.

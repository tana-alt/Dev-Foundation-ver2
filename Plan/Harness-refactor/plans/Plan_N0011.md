---
plan_id: Plan_N0011
project_id: Harness-refactor
status: review_rework_applied
log_ref: Plan/Harness-refactor/logs/Plan_N0011.log.md
---

# Harness Director Automation And Command Surface Corrections

## Goal

Record the corrected Harness operating policy from the director run so a later
subagent review can evaluate it before implementation.

This note is policy input, not an implementation result.

## Human-Corrected Policy

- Archive work is local/recoverability-oriented and is not pushed to the remote
  by default.
- `harness pr create` must mean external GitHub pull request creation, not only
  a local Harness PR/runtime record.
- After review approval, the mechanical pre-push CI/gate path should be a
  Harness automation candidate, not a recurring director manual step. If it
  passes and the candidate has an approved certified hash, PR creation should be
  mechanical and should not call an AI reviewer.
- Integrator delegation is for conflicts, candidate hash/id mismatches, stale
  evidence, candidate apply failures, target drift, pre-push hook failures, or
  other non-mechanical blockers.
- The operator/director decision should be limited to whether the final
  candidate matches the implementation plan and whether it carries the certified
  approved hash id.
- Role agents should not investigate PR creation, land staging, hook root
  ownership, or Harness fallback behavior unless that is their assigned task.
  Those are director/integrator/Harness responsibilities.
- Agent command, sandbox, approval, and agent runtime behavior controls belong
  in an explicit runtime command policy, not in task-specific improvisation.
- Aborted command and residual process detection should be handled by Harness
  so the director does not need to manually kill leftover verification jobs.
- Required bootstrap config is `.harness/policy.yaml` plus
  `.harness/tasks/<task_id>/task.yaml`. Any legacy dependency beyond those files
  is migration debt.

## Archive Placement Policy

The phrase "archive placement policy" should mean:

- each task declares one expected local archive location when archive output is
  part of the task;
- archive output must not scatter across unrelated source, docs, runtime, or
  artifact directories;
- local archives are excluded from remote push unless the task explicitly asks
  to publish archive metadata or a manifest;
- reviewers check placement and scope, but remote publication is not implied by
  the word archive.

## Mechanical Flow Target

1. Writer works in an owned worktree and submits a candidate.
2. Review AI runs only through explicit review commands:
   `review` for semantic/aggressive code review and `architecture review` for
   architecture review.
3. Machine verification remains separate from AI review.
4. If review passes, the certified hash id is recorded.
5. Harness/integrator automation runs pre-push CI or the closest local
   mechanical gate; the director observes the result rather than executing the
   same check manually every time.
6. If the certified hash and implementation plan still match, create the
   external GitHub PR mechanically.
7. If candidate application, conflict resolution, hook root, id mismatch, stale
   evidence, or pre-push checks fail, delegate to the integrator rather than
   asking the writer to reason about Harness operations.

## Evidence Format Requirement

For task-level continuity, `evidence.md` should preserve decisions that cannot
be inferred from the diff or verifier output:

```md
# Evidence

## Architecture Judge

## Coding Judge

## Review Authority

## ACP-Only Operation Notes

## Final Human Readout
```

The expected content is rationale, rejected alternatives, authority hashes,
freshness/staleness reasoning, ACP-only decisions, and final residual risk. Do
not copy bulky logs, raw transcripts, credentials, auth material, browser state,
or runtime ledgers.

## Codex Command Surface

Current local `codex --help` shows commands other than `codex exec`, but they
do not all mean "spawn a fresh noninteractive writer/integrator agent."

- Fresh unmonitored implementation/rework agent: `codex exec`.
- Continue a known noninteractive session: `codex exec resume`.
- AI review surface: `codex review` or `codex exec review`, only when the
  Harness review command explicitly asks for an AI review.
- Interactive human/TUI session: `codex` without a subcommand, or
  `codex resume`; not suitable for ACP-only unmonitored Harness operation.
- Service/control surfaces: `codex mcp-server`, `codex app-server`,
  `codex remote-control`, and `codex exec-server`; possible future Harness
  integration points, but not a direct replacement for `codex exec`.
- Shell sandbox runner: `codex sandbox`; this runs commands under Codex
  sandboxing and is not an agent role runner.

Important command-generator correction: top-level `codex` supports
`--ask-for-approval`, but the current local `codex exec --help` does not list
that option. Harness must not append `--ask-for-approval never` to
`codex exec`.

## Review Questions For Subagent

- What does worktree-local hook root resolution currently trust:
  `FOUNDATION_REPO_ROOT`, `PWD`, `.harness-worktree.json`, `git rev-parse
  --show-toplevel`, or git common-dir state?
- Should hook scripts always derive repo root from the current worktree unless
  an explicit trusted override is present?
- Does the task packet provide enough role boundary information to prevent
  writer/reviewer agents from investigating PR creation, land staging, and
  hook-root fallback behavior?
- Is the post-review mechanical verification path sufficiently automated, and
  is the mechanical PR path sufficiently separated from AI review and
  integrator fallback?
- Are command, sandbox, approval, and runtime behavior controls represented as
  policy rather than agent prompt text?

## Acceptance For Next Implementation

- The director no longer manually repairs missing bootstrap config for a normal
  prepared task.
- A failed or interrupted command leaves detectable Harness evidence, and
  residual processes are surfaced or cleaned by Harness.
- Pre-push CI/gate runs before PR creation through a Harness-owned mechanical
  path, not a repeated director manual step.
- Passing mechanical verification plus an approved certified hash can create a
  GitHub PR without AI invocation.
- Integrator is called only for defined fallback classes.
- Hook root checks run against the owned worktree, not an inherited main
  worktree root.
- Role prompts/manifests keep PR creation, land staging, and Harness fallback
  internals out of writer/reviewer responsibility unless assigned.

## Implemented Slice 2026-06-25

The accepted design was implemented as a deterministic `post-review-gate`
Harness lifecycle command.

### Implemented Acceptance

- `HARNESS_ROLE=integrator ./harness post-review-gate <task_id>` runs after
  review pass and before PR creation.
- The command writes `post-review-gate-result.json` with machine-readable
  `status`, `classification`, `reason`, `review`, `gate`, and `next_action`.
- `pr create` now reruns and records a fresh passed post-review gate before it
  can create PR evidence.
- `dispatch`/`integrate` route through the post-review gate so the mechanical
  gate is Harness-owned rather than a recurring director manual step.
- Strict ACP exposes the same operation as `gate.post_review`, guarded by the
  existing integrator gate capability.
- Integrator tools include `post-review-gate` with a tool-specific skill:
  `harness-tool-post-review-gate`.

### Invariant Axis

Expected input should pass in the ordinary direction:

- Given a verified and submitted candidate, fresh required reviewer approvals,
  matching candidate hash, and passing machine verification, when integrator
  runs `post-review-gate`, then the result is `status: passed`,
  `classification: mechanical_gate_passed`, `reason: ok`, and the next action
  is mechanical PR creation.
- Given a writer or reviewer role, when the role calls `post-review-gate`, then
  Harness rejects it before writing gate evidence.
- Given an existing passed `post-review-gate-result.json`, Harness does not use
  the artifact as standalone authority for PR creation; `pr create` reruns the
  post-review gate against current review, gate, candidate, and StateStore
  evidence.

### Adversarial Axis

Error input should stop safely and stay classified:

- Missing review quorum before PR creation returns `classification:
  integrator_required`, `reason: review_quorum_unmet`, and does not create PR
  evidence.
- Tampered `candidate.diff` after review returns `classification:
  integrator_required`, `reason: candidate_hash_mismatch`, and keeps the
  fallback in the integrator boundary.
- Corrupt runtime JSON returns `classification: harness_error`, `reason:
  invalid_runtime_state`, and still writes readable
  `post-review-gate-result.json`.
- Failed machine gate/review reasons are mapped into writer rework, integrator
  fallback, or Harness error before any external write path.

### Verification Evidence

- `uv run pytest -q tests/workflow_core/test_contract_harness.py -k 'post_review_gate or role_boundaries_reject_disallowed_commands'`:
  `4 passed`.
- `uv run pytest -q tests/workflow_core/contract_harness/test_local_pr_service.py`:
  `5 passed`.
- `uv run pytest -q tests/workflow_core/contract_harness/test_strict_capabilities.py`:
  `9 passed`.
- `uv run pytest -q tests/workflow_core/contract_harness/test_local_pr_service.py tests/workflow_core/contract_harness/test_strict_outbox_recovery.py tests/workflow_core/contract_harness/test_strict_happy_path.py`:
  `8 passed`.
- `uv run pytest -q tests/workflow_core/test_contract_harness.py tests/workflow_core/contract_harness/test_local_pr_service.py tests/workflow_core/contract_harness/test_strict_capabilities.py tests/workflow_core/contract_harness/test_strict_outbox_recovery.py tests/workflow_core/contract_harness/test_strict_happy_path.py`:
  `131 passed in 427.38s`.

The broad related test run exceeding five minutes is recorded as remaining
Harness test-runtime evidence. It is not a correctness failure for this slice,
but it is relevant to the CI-speed objective.

## Subagent Review 2026-06-25

Two read-only subagents reviewed the implemented slice:

- architecture/authority reviewer
- adversarial/testing reviewer

Verdict: blocked. The reviewers independently found overlapping P1/High
issues.

### Blocking Findings

- `post-review-gate-result.json` pass currently maps status to `integrated`,
  so `./harness status` can recommend `land` instead of `pr create`. Since
  land currently treats missing local PR evidence as `not_required`, PR creation
  and PR checks can be skipped after a post-review gate pass.
- `ensure_post_review_gate_passed` can trust an existing
  `post-review-gate-result.json` when candidate and machine hashes match and
  embedded `review.review_pass` is true. It does not re-run review collection,
  check for newer blocking reviews, verify the embedded gate status/reason, or
  require StateStore authority. A stale or forged runtime pass can therefore
  unblock `pr create`.

### Additional Findings

- `pr create` still creates a local Harness PR ref and runtime evidence rather
  than an external GitHub PR. This remains inconsistent with the corrected
  policy that Harness PR creation should mean external GitHub PR creation.
- `post-review-gate` calls `gate_task`, and `gate_task` may auto-run missing
  non-AI reviewers when quorum is already satisfied but not every configured
  reviewer is fresh. This means the hook is not purely mechanical under all
  review configurations.
- Strict outbox recovery can observe a tampered successful `pr-result.json`
  without executing `create_local_pr`, so it can bypass the new post-review gate
  guard unless observation verifies the PR ref, diff hash, authority event, and
  post-review gate.
- One reviewer observed portability friction: some fixture verifiers use
  `python`, which was absent in that agent environment. A temporary
  `python -> python3` shim made the focused suite pass.

### Required Fix Direction

- Add an explicit post-review-passed/pre-PR phase instead of treating
  `post-review-gate-result.json` as `integrated`.
- Make `status` recommend `pr create` after post-review gate pass and before PR
  evidence exists.
- Make land block when post-review gate passed but PR creation/check evidence
  is missing, according to the ACP-only operating policy.
- Tighten `ensure_post_review_gate_passed` so it revalidates current review
  collection, gate mergeability/reason, candidate and machine evidence, and
  authority before trusting existing pass evidence.
- Ensure PR creation semantics either create an external GitHub PR or clearly
  split local PR-ref creation from external PR creation.
- Harden strict outbox observation so a tampered `pr-result.json` cannot be
  treated as successful PR creation.

## Review Rework Applied 2026-06-25

The P1/High reviewer findings were fixed in the local implementation slice.

- `status` now exposes explicit post-review and PR phases:
  `post_review_gated` recommends `HARNESS_ROLE=integrator ./harness pr create
  <task_id>`, and `pr_created` recommends `HARNESS_ROLE=integrator ./harness pr
  checks <task_id>`.
- `land` now blocks with `reason: pr_not_created` when the current candidate has
  passed post-review gate but PR evidence is missing, and it still requires
  `PR_CHECKED` freshness before landing.
- `ensure_post_review_gate_passed` reruns the mechanical post-review gate
  instead of trusting a pre-existing pass artifact.
- `post-review-gate` calls `gate_task(..., auto_review=False)`, so the
  post-review hook path collects existing review verdicts and does not auto-run
  missing reviewers.
- Strict outbox recovery validates local PR observation against the StateStore
  `PR_CREATED` event, ref head, candidate id, base sha, and candidate diff hash
  before treating an existing `pr-result.json` as recovered.
- PR creation worktrees switch to an owned
  `agent/<task_id>/integrator/pr-<candidate_id>` branch before committing, so
  worktree-local hooks that reject detached HEADs do not block the mechanical PR
  ref path.

Remaining explicit policy gap:

- `harness pr create` still creates a local Harness PR ref/runtime record, not
  an external GitHub pull request URL. That was already identified as a larger
  command-semantics split and remains outside this focused blocker fix.

### Rework Verification

- `uv run pytest -q tests/workflow_core/contract_harness/test_local_pr_service.py -q`:
  `8 passed`.
- `uv run pytest -q tests/workflow_core/contract_harness/test_strict_outbox_recovery.py -q`:
  `3 passed`.
- `uv run pytest -q tests/workflow_core/test_contract_harness.py -k 'e2e_integrator_dispatch_land_then_push_blocks_under_dry_run or land_default_gate_reruns_task_verifiers_not_broad_make or land_explicit_gate_tier_blocks_and_records_gate_result or land_commits_on_agent_branch_when_hooks_reject_detached_head or post_review_gate'`:
  `7 passed, 106 deselected`.
- `uv run pytest -q tests/workflow_core/contract_harness/test_local_pr_service.py tests/workflow_core/contract_harness/test_strict_outbox_recovery.py tests/workflow_core/contract_harness/test_strict_happy_path.py -q`:
  `13 passed`.
- `uv run ruff check` and `uv run ruff format --check` over changed
  Harness/PR/status/test files: passed.

# Harness Operational Issue Register

Date: 2026-06-18

This register is the single collection point for currently known contract
harness operational issues. It consolidates the existing harness review docs,
runtime verification records, stop-condition audit, and the 2026-06-18 E2E
context-access audit.

The harness is a verification machine. It should keep correctness gates strict
while giving each agent enough task-responsibility context to do its actual
job. Do not fix these issues by adding silent fallbacks that turn missing,
stale, timed-out, or blocked evidence into success.

## Source Document Set

- `refactor-instructions.md`
- `Plan/harness-runtime-verification-20260618/plans/Plan_N0003.md`
- `Plan/harness-runtime-verification-20260618/logs/Plan_N0003.log.md`
- `Plan/harness-runtime-verification-20260618/plans/Plan_N0004.md`
- `Plan/harness-runtime-verification-20260618/logs/Plan_N0004.log.md`
- `Plan/harness-runtime-verification-20260618/plans/Plan_N0005.md`
- `Plan/harness-runtime-verification-20260618/logs/Plan_N0005.log.md`
- `Plan/harness-review/plans/dev-foundation-harness-docs-integrated.md`
- `docs/reference/harness-observability-reference.md`
- `docs/reference/exit-codes-reference.md`
- `tests/workflow_core/test_contract_harness.py`
- `tests/workflow_core/test_contract_harness_policy_acceptance.py`
- `tests/workflow_core/test_contract_harness_land_push_acceptance.py`
- `tests/test_hook_scripts.py`

## Operating Principles

- Preserve rational stops: missing reviewer evidence, stale submission,
  verifier failure, semantic block, protected external write, lock contention,
  and human approval gates must not become pass states.
- Convert excessive stops into earlier health/preflight diagnostics where
  possible.
- Convert ambiguous failures into typed `blocked`, `rework_required`,
  `escalated`, or diagnostic artifacts with clear next actions.
- Keep the Stop hook fail-open. It may observe and record, but must not trap the
  user's session.
- Keep scope maps advisory. They are evidence for discovery and review, not a
  hard implementation contract.
- Keep `budget` and heavy context-manifest contracts out of ordinary agent
  packets unless a future product decision explicitly reintroduces them.
- Prefer freshness checks, hashes, typed artifacts, and runbook guidance over
  automatic fallback behavior.

## Current Top Risks

1. Stale prepared runtime artifacts can give agents outdated tool, skill, or
   capsule context even when fresh command output shows the current definitions.
2. Writer launch context can omit the task intent, causing path/verifier
   contracts to dominate the model's responsibility context.
3. `context-audit` currently checks packet size and tool/skill visibility, but
   not responsibility-context completeness or artifact freshness.
4. Recoverable harness states are still easy to misread as fatal stops because
   many commands expose generic non-zero exits without a strong next-action
   layer.
5. Completion, push, and protected external write semantics remain policy
   sensitive and must not be loosened without approval.

## Issue Register

### HIR-001. Prepared Agent Context Artifacts Can Go Stale

Classification: operational blocker risk; missing freshness stop.

Evidence:

- `src/workflow_core/contract_harness/contract.py:52-56` returns existing
  `contract.lock.json` from `ensure_prepared` without regenerating derived
  `capsule.json`, `agent-tools.json`, `agent-skills.json`, or scope artifacts.
- Current task inspection showed generated writer tools included
  `context-audit`, `status`, and `spawn-writer`, while stored `capsule.json`
  still listed only the older six-tool writer set.
- Stored `submission.json` and `reviews/semantic-ai.review-packet.json` also
  carried older writer/reviewer tool sets.

Impact:

Agents can be launched or handed review packets that omit current operational
tools such as `status`, `spawn-writer`, or `certify`. This creates confusing
runtime behavior and can make an otherwise recoverable continuation look
blocked.

Recommended action:

Add a freshness/version mechanism for role tools, role skills, capsule, and
review packet inputs. Regenerate or mark derived artifacts stale when tool/skill
definitions, task config, verifier plan, or contract semantic hash change. Do
not silently read old artifacts as a fallback.

Verification:

- Add tests that modify tool/skill definitions or simulate stale stored
  artifacts and assert `prepare`, `launch-writer`, `submit`, and semantic
  review either refresh or report a typed stale-context condition.
- Re-run focused context tests and semantic reviewer E2E tests.

Implementation status: implement after adding focused stale-artifact tests.

### HIR-002. Writer Launch Context Omits Task Intent

Classification: responsibility-context gap.

Evidence:

- `src/workflow_core/contract_harness/cli.py:185-196` routes
  `launch-writer` through `spawn_session`.
- `src/workflow_core/contract_harness/spawn.py:166-182` builds initial context
  with `task_id`, `agent_tools`, and `agent_skills` only.
- `./harness launch-writer multicollinearity-feature-independence-20260616`
  returned no `intent`, no `scope_contract`, no `verifier_ids`, and no
  `capsule` in `initial_context`.
- `./harness explain <task_id>` printed paths, verifiers, tools, skills, and
  runtime, but did not print the task intent summary/details.

Impact:

The writer can see how the harness constrains work before it sees what product
work it is responsible for. This risks letting the contract crowd out the
agent's implementation responsibility.

Recommended action:

Include a compact task intent in writer initial context and `explain`, such as
`intent.kind`, `intent.summary`, and bounded `intent.details` when present.
Keep this small and human-readable. Do not add a heavy contract packet just to
compensate.

Verification:

- Add a launch-writer test asserting the initial writer context includes the
  task intent.
- Add an explain test asserting the human output, or future JSON output, exposes
  the task intent.

Implementation status: implement with a minimal context addition.

### HIR-003. Context Audit Does Not Validate Responsibility Context

Classification: diagnostic debt.

Evidence:

- `src/workflow_core/contract_harness/context_audit.py:14-30` computes role
  packet pressure and pass/fail.
- `_missing_required` checks required tool names, skill names, and skill paths.
- It does not assert that writer has task intent, reviewer has current candidate
  evidence, integrator has current submission/integration state, or that stored
  artifacts match current tool/skill definitions.

Impact:

`context-audit` can pass while the actual launch context lacks task intent or
while stored artifacts are stale. Operators may trust a green audit too much.

Recommended action:

Extend `context-audit` with role-specific responsibility checks and freshness
diagnostics. Report these as typed missing/stale entries instead of adding broad
fallback loading.

Verification:

- Add tests where writer intent is missing, stored agent-tools are stale, or
  reviewer packet tool hashes are stale; assert audit reports the issue.
- Keep existing assertions that `budget` does not appear in audit output.

Implementation status: implement after HIR-001 and HIR-002 test fixtures exist.

### HIR-004. Recoverable States Often Surface As Generic Exit 1

Classification: continuity bottleneck; diagnostic debt.

Evidence:

- `Plan_N0004.log.md` records that `verify`, `dispatch`, `gate`, `land`,
  `push`, and many config errors can all surface as non-zero command exits.
- Several of these states are legitimate rework or wait conditions, not fatal
  runtime failures.

Impact:

A long-running operator or agent can stop too early if it branches only on
  process status.

Recommended action:

Add or strengthen a reason-to-next-action layer in `status` and phase artifacts.
Keep non-zero exits for failing commands, but make the JSON reason and next
command unambiguous.

Implementation status: implement incrementally with tests for each reason.

### HIR-005. `blocked` Is Overloaded

Classification: ambiguous stop taxonomy.

Evidence:

- `blocked` can currently represent protected external write, local or remote
  lock contention, missing manual resolution, human approval, or missing
  evidence.

Impact:

Operators cannot reliably distinguish "wait and retry", "ask the human", "fix
config", "produce evidence", and "do not proceed".

Recommended action:

Preserve blocking behavior but split reasons and severity. Add next-action
fields to status or result artifacts.

Implementation status: implement with schema-conscious tests.

### HIR-006. There Is No Repo-Internal Keep-Alive Loop

Classification: operational boundary; not a code bug.

Evidence:

- `scripts/hook_stop.py` is fail-open and observational.
- `Plan_N0004.log.md` records that active plans without submission exit 0 and
  do not trigger background continuation.
- Repo storage contracts discourage broad internal queues, dashboards, or
  schedulers by default.

Impact:

Continuous operation requires an external runner or explicit lightweight retry
policy. The harness alone should not be assumed to keep work alive.

Recommended action:

First improve status/next-action output. If automation is needed, build a small
external continuation runner that invokes safe local commands based on typed
reasons.

Implementation status: proposal; do not add an internal scheduler without a
storage-contract decision.

### HIR-007. Stale `.harness` Task And Verifier Config

Classification: excessive/obsolete stop.

Evidence:

- Current `.harness` task/config can point to paths or verifier commands that
  are absent in the current worktree.
- `refactor-instructions.md` D1 records current stale task evidence for
  `multicollinearity-feature-independence-20260616`.

Impact:

Writers can be launched into structurally unwinnable work before any code is
changed.

Recommended action:

Strengthen `status` or add preflight/config-health so stale task paths and
verifier commands are visible before writer launch.

Implementation status: implement diagnostics; do not delete task/config without
approval.

### HIR-008. Completion Authority Conflicts With Dry-Run Operation

Classification: policy-sensitive bottleneck.

Evidence:

- `status.py` treats `push-result.json status=pushed` as completion authority.
- Dry-run external-write policy can correctly produce
  `blocked/protected_external_write`.
- README and current status language can be interpreted differently around
  `integrated`, `landed`, and `pushed`.

Impact:

Automation can loop after a correct protected dry-run block, or mark completion
too early if semantics are loosened.

Recommended action:

Document and test terminal semantics by policy mode before changing behavior.

Implementation status: proposal only until policy is confirmed.

### HIR-009. Semantic Reviewer Infrastructure Failure Is Conflated With Semantic Block

Classification: rational stop with diagnostic debt.

Evidence:

- Semantic reviewer timeout, command failure, or wrapper crash can be recorded
  as a block with `semantic_gap`.
- `refactor-instructions.md` D3 records this behavior and related tests.

Impact:

Operators may send writer rework when the reviewer infrastructure, command
availability, or timeout budget is the actual problem.

Recommended action:

Keep the stop blocking but split operational failure reasons from real semantic
verdict blocks. Write durable command diagnostics.

Implementation status: implement after label policy is confirmed.

### HIR-010. Review Config Validation Happens Too Late

Classification: excessive stop; late failure.

Evidence:

- Review config issues can appear during dispatch/gate after writer submission.
- `refactor-instructions.md` D4 records quorum/profile validation gaps.

Impact:

Invalid review config wastes writer cycles and looks like candidate rework.

Recommended action:

Move review config validation into `prepare`, `status`, or explicit health
preflight.

Implementation status: implement as health/config diagnostics.

### HIR-011. Stop Hook Diagnostics Are Ephemeral

Classification: observability debt with intentional fail-open behavior.

Evidence:

- `docs/reference/harness-observability-reference.md` and Stop hook tests
  require dispatch failures, missing harness, and environment issues to exit 0.
- Diagnostics can remain only in stdout/stderr.

Impact:

Stop-time infrastructure failures can be missed in later `harness status`
inspection.

Recommended action:

If runtime root and task id are known, write a small bounded observation
artifact for hook dispatch failures. Keep the hook stdlib-only and fail-open.

Implementation status: implement only if hook tests continue proving exit 0.

### HIR-012. Worktree Reset Rules Are Uneven

Classification: destructive-operation risk.

Evidence:

- Existing records note stricter dirty-worktree refusal for writer/reviewer
  than for some integrator/compose flows.
- Compose and integration retries can perform resets/cleans for repeatability.

Impact:

Diagnostic state or human investigation work can be lost during retries.

Recommended action:

Add marker validation and dirty diagnostics for compose first. Do not change
integrator reset semantics without approval.

Implementation status: partial implementation candidate; integrator behavior is
ask-first.

### HIR-013. Lock Blocks Are Safe But Recovery Is Weak

Classification: rational stop with recovery bottleneck.

Evidence:

- Remote lock contention blocks push, as it should.
- Local corrupt locks can produce weak `blocked_by_lock` diagnostics.
- Existing stop audit records stale-lock and corrupt-lock risk.

Impact:

One stale or corrupt lock can stall land/push until a human diagnoses the lock
state manually.

Recommended action:

Add read-only lock diagnosis first: owner, task id, path/ref, target sha, age
when known, and exact manual recovery guidance. Do not delete remote locks
without approval.

Implementation status: diagnostics yes; automated stale-lock release proposal
only.

### HIR-014. Command Execution And CLI Artifacts Are Inconsistent

Classification: diagnostic consistency debt.

Evidence:

- Most command execution is moving through `command_runner.py`, but some probes
  and CLI exception paths can still produce different shapes or no phase
  artifact.

Impact:

Timeouts, missing commands, and precondition failures can look different across
phases, increasing operator burden.

Recommended action:

Route non-hook probes through the common command runner. Write typed phase
artifacts for known preconditions while preserving non-zero exits.

Implementation status: implement incrementally.

### HIR-015. Repo Hygiene And Plan Integrity Drift Keep Broad Gates Red

Classification: repository-boundary debt.

Evidence:

- `Plan_N0003.log.md` and `Plan_N0004.log.md` record Plan naming drift,
  top-level root drift, and local `artifact/` exclude drift.
- Full pytest and `make check-required` were red during prior verification for
  these reasons.

Impact:

Continuous agents can confuse unrelated repo-boundary failures with harness
  runtime failures.

Recommended action:

Resolve Plan naming/index consistency and top-level root policy separately from
runtime harness changes. Do not hide these with broad test skips.

Implementation status: separate cleanup track.

### HIR-016. Metrics, Eval, NFR, And Bench Signals Are Passive Or Incomplete

Classification: feedback-loop debt.

Evidence:

- `Plan_N0004.log.md` records empty NFR/bench samples and a current gate that
  missed hack-bait relative to scanned completion evidence.
- `docs/reference/harness-observability-reference.md` documents metrics and AB
  evaluation surfaces, but task-local warnings are not yet consistent.

Impact:

Behavior-quality signals exist but do not yet reliably guide continuous agent
operation.

Recommended action:

Promote relevant metrics/eval observations into task-local warnings and
next-action guidance. Keep inconclusive quantitative results distinct from
failures.

Implementation status: implement after status/next-action taxonomy stabilizes.

### HIR-017. Reviewer Packets Are Evidence-Rich And Can Become Context-Heavy

Classification: bounded context-pressure risk.

Evidence:

- Fresh E2E review packet inspected on 2026-06-18 was `14522` bytes for a tiny
  diff and included capsule, contract, writer handoff, verifier evidence,
  quality/tool/metric/mutation evidence, scope map, diff index, and reviewer
  policy.
- Existing tests prove large diffs are not inlined and require artifact reads.

Impact:

The current design is not over-structured in the tested path, but packet size
can grow as evidence expands. Reviewers need role-focused summaries before
bulky details.

Recommended action:

Keep required evidence available, but present summary-first packets and artifact
pointers for bulky sections. Preserve hash verification for omitted evidence.

Implementation status: monitor and improve after HIR-001/HIR-003 freshness
checks.

## Verification Baseline For This Register

Commands recorded during the 2026-06-18 E2E context-access audit:

```text
uv run pytest -q tests/workflow_core/test_contract_harness.py -k 'prepare_capsule_exposes_existing_agent_tool_set or launch_writer_prepares_worktree_and_returns_interactive_command or spawn_writer_assigns_role_without_running_verify or spawn_does_not_import_gate_land_push or context_audit_quantifies_role_context_without_budget_escape or semantic_ai_reviewer_receives_diff_and_test_interpretation or large_diff_is_not_inlined_in_semantic_reviewer_packet or e2e_semantic_reviewer_receives_writer_handoff_diff_index_tools_and_skills or semantic_reviewer_runs_in_sealed_writer_worktree or scope_map_reverse_reaches_semantic_reviewer or quality_review_flags_do_not_block_submit_and_reach_semantic_reviewer or metric_evidence_reaches_semantic_reviewer or worktree_semantic_review_uses_canonical_metric_evidence'
```

Result:

```text
13 passed, 88 deselected in 40.80s
```

Preserved-artifact rerun:

```text
uv run pytest -q tests/workflow_core/test_contract_harness.py::test_e2e_semantic_reviewer_receives_writer_handoff_diff_index_tools_and_skills tests/workflow_core/test_contract_harness.py::test_context_audit_quantifies_role_context_without_budget_escape --basetemp /tmp/harness-context-e2e
```

Result:

```text
2 passed in 6.23s
```

Runtime audit:

```text
./harness context-audit multicollinearity-feature-independence-20260616
```

Result:

```text
status=pass
writer estimated_tokens=2282
reviewer estimated_tokens=2117
integrator estimated_tokens=3111
total_estimated_tokens=7510
```

## Implementation Guidance

Recommended order:

1. Add tests and diagnostics for stale prepared artifacts and writer intent
   visibility.
2. Extend `context-audit` to report role responsibility context and freshness.
3. Add reason-to-next-action output for common rework/blocked states.
4. Move stale config and review config failures into preflight/status health.
5. Improve lock and phase-precondition diagnostics without weakening stops.
6. Only then consider external continuation automation.

Out of scope for this register:

- Making the Stop hook blocking.
- Treating protected external writes as success without policy approval.
- Deleting stale tasks or Plan files without an ownership decision.
- Adding a broad repo-internal scheduler, queue, or dashboard.
- Skipping correctness gates to keep the loop moving.

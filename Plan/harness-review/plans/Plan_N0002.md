# Plan_N0002: Harness-Managed Merge Oracle Proposal

Date: 2026-06-17
Project: `harness-review`
Status: draft proposal

## Objective

Keep the next step as a proposal only: inspect the implemented harness path,
record the gap, and propose a machine-managed merge-oracle design. Do not
expand active docs, reference docs, templates, or code in this slice.

The target assumption is that loop closure, branch serialization, retry, and
rework routing are owned by `./harness`, not by writer instructions, manual
branch choreography, or a prose-only operational contract.

## Source Inputs

- User direction on 2026-06-17: redo the previous docs direction; assume the
  loop is mechanically managed by the harness; create a proposal only after
  checking the actual implementation.
- Uploaded source plan: `merge-oracle-build-plan.md`.
- Uploaded characterization test: `test_merge_serialization_race.py`.
- Current repository implementation inspected:
  - `src/workflow_core/contract_harness/runtime_paths.py`
  - `src/workflow_core/contract_harness/worktree.py`
  - `src/workflow_core/contract_harness/verify.py`
  - `src/workflow_core/contract_harness/submission.py`
  - `src/workflow_core/contract_harness/gate.py`
  - `src/workflow_core/contract_harness/integration.py`
  - `src/workflow_core/contract_harness/affected.py`
  - `src/workflow_core/contract_harness/land.py`
  - `src/workflow_core/contract_harness/push.py`
  - `src/workflow_core/contract_harness/review.py`
  - `src/workflow_core/contract_harness/mutation.py`
  - `scripts/check-frozen-paths.py`
  - `hooks/pre-commit`
  - `Makefile`

## Actual Implementation Findings

### Runtime and ownership

`runtime_root()` stores harness runtime under the git common directory as
`harness-runtime` by default, or under `HARNESS_RUNTIME_ROOT` when overridden.
It explicitly rejects tracked `.harness/state` as a runtime root. This supports
machine-managed state without committing scheduler or worktree state.

Writer, reviewer, and integrator worktrees are created and reused by
`create_worktree()`. Writer and reviewer worktrees are based on the task's
prepared base SHA. The integrator worktree is based on the configured remote
integration target and uses an owned `agent/<task_id>/integrator/land` branch.
Reuse is marker-checked by repository common directory, task, kind, and reviewer
id; dirty or foreign worktrees are not destructively reused.

### Candidate and gate binding

`verify_task()` writes `candidate.diff`, reverse scope evidence, verifier
results, scope/semantic checks, and `candidate_diff_sha256` / machine evidence
hashes. `submit_task()` validates the passed verify result, evidence hashes, and
candidate hash, optionally runs the configured mutation handoff check, seals the
candidate workspace, then writes `submission.json`.

`gate_task()` resolves the submitted candidate workspace against the expected
candidate hash, rechecks machine evidence, runs the completion check, auto-runs
fresh reviewers when configured, and writes `gate-result.json`. The mergeable
condition is still `reason == ok`; reviewer verdicts are fresh only when their
`evidence_seen` matches the expected evidence.

### Land and push behavior

`classify_affected_set()` fetches the current configured target and classifies
against the prepared base:

- `FAST`: target still equals prepared base.
- `PARTIAL`: target advanced but candidate paths and target-changed paths are
  disjoint.
- `REBASE`: target advanced and changed paths overlap.

`land_task()` validates submission and gate result, takes the local land lock,
creates the integrator worktree, rejects `REBASE`, applies `candidate.diff`,
runs the machine gate in the integrator tree, commits `land <task_id>`, and
writes `land-result.json`.

`push_task()` then fetches the remote target and enforces exact CAS: if the
fetched remote SHA differs from `land_result.target_base_sha`, it writes a
failed `push-result.json` with reason `remote_changed`. Only after that exact
check passes does it acquire the remote lock, create a rescue ref, push the
landed commit, release the lock, and sync the local target branch.

### Reviewer, mutation, and frozen paths

Reviewer verdicts currently contain `evidence_seen`, labels, reason, timestamp,
and `written_by: harness`. They do not yet contain content-addressed certified
test artifacts.

Mutation support exists as an optional handoff check. It is configured through
`review.yaml`, receives the candidate diff and output path, refuses mutation
commands that alter the candidate, normalizes survivor output, and records
`mutation-result.json`. It is not yet a certified-test adequacy gate.

Frozen path enforcement exists through `scripts/check-frozen-paths.py`,
`workflow_core.frozen`, `make check-frozen`, and `hooks/pre-commit`. The freeze
list is opt-in via `Plan/<project>/frozen-paths.txt` or `.frozen-paths`.

## Problem Statement

The current implementation already makes the harness the owner of candidate
hashing, worktree creation, reviewer freshness, gate execution, land, local
lock, remote lock, rescue ref creation, and push CAS.

The missing behavior is narrower:

1. There is no `merge_oracle.py` that composes pending candidates onto the
   current target head and runs a merged-tree test plan.
2. `remote_changed` is final failure, even for disjoint candidates that the
   affected-set classifier already recognizes as `PARTIAL`.
3. Reviewer approvals are evidence-bound verdicts, not content-addressed
   certified test artifacts.
4. Mutation and frozen-path mechanisms exist, but they are not wired into a
   certified-test lifecycle.
5. There is no harness-owned target-branch pending-candidate index for N-way
   compose/localize.

Therefore the right next work is not docs expansion. It is a proposal for a
small harness state machine and merge oracle that uses the already-existing
runtime root, candidate hashes, verifier runner, integrator worktree, land
machine gate, local lock, remote lock, rescue ref, mutation hook, and frozen
path hook.

## Proposed Design

### Principle

Merge authority should be a machine result produced by the harness:

```text
current target head + pinned candidate diff(s) + pinned test plan -> oracle result
```

Do not treat a reviewer verdict, a stale branch base, or disjoint path analysis
as final merge authority. Path disjointness is only a cheap pre-check. The merge
authority is the merged tree `M` tested by the harness.

### Harness-owned transition model

Use explicit task/target states in `harness-runtime`, not active docs or manual
operator instructions:

```text
submitted
  -> integrated
  -> landed
  -> push_attempted
  -> pushed
  |  remote_changed
  -> oracle_retry
  -> pushed
  |  rework_required
  |  escalated
```

The target-branch side should maintain a small runtime index under the git
common-dir runtime root, for example:

```text
harness-runtime/state/integration/<remote>/<branch>/pending.json
harness-runtime/state/integration/<remote>/<branch>/oracle-runs/<run_id>.json
```

This is runtime state, not tracked repo truth. It should contain only candidate
hashes, task ids, target base/head SHAs, verifier/test plan hashes, oracle
status, blame/rework facts, retry counts, and timestamps.

### S1: Single-candidate merge oracle

Add `src/workflow_core/contract_harness/merge_oracle.py`.

Inputs:

- target head SHA;
- one submitted candidate envelope:
  - `task_id`
  - `candidate.diff`
  - `candidate_diff_sha256`
  - verifier/test plan reference;
- oracle policy:
  - timeout;
  - max retries;
  - always-on verifier ids;
  - future certified-test mode.

Behavior:

1. Create or reset a clean integrator worktree at the supplied target head.
2. Verify the candidate diff hash before applying.
3. Apply the candidate diff exactly as submitted.
4. Run the oracle test plan in the merged tree.
5. Return a typed result:

```json
{
  "status": "green | red",
  "target_head_sha": "...",
  "candidate_diff_sha256": "...",
  "applied": [{"task_id": "...", "status": "applied"}],
  "verifiers": [],
  "failures": [],
  "blamed_task_ids": []
}
```

Initial test plan: reuse the writer verifier plan plus always-on invariants.
Do not block this slice on certified-test granularity.

Machine acceptance:

- clean single candidate reapplies and verifies green;
- candidate hash mismatch is red/error, not green;
- apply failure returns blamed task;
- verifier failure returns red and the failing verifier evidence;
- oracle run writes a runtime result artifact under `harness-runtime`, not under
  tracked `.harness/state`.

### S2: Replace push-time `remote_changed` with oracle retry

Change `push_task()` behavior only after S1 is tested.

Current behavior:

```text
remote_sha != land_result.target_base_sha -> failed remote_changed
```

Proposed behavior:

```text
remote_sha != land_result.target_base_sha
  -> release/no remote push lock if held
  -> run merge_oracle against current remote head
  -> green: commit merged tree, retry exact-CAS push against the head just tested
  -> red: rework_required with blamed task and failing evidence
```

The remote lock must remain push-attempt scoped. It should not be held while the
oracle composes candidates or runs tests. Retry count should be bounded by
`policy.yaml` under `bottlenecks.integration`, for example
`max_remote_changed_retries`.

Machine acceptance:

- concurrent overlap remains no-clobber;
- sequential overlap still returns rework before land;
- concurrent disjoint changes from exact-CAS `remote_changed` failure to oracle
  green and automatic repush;
- lock ref is not leaked after green or red paths;
- retry exhaustion returns `escalated` or `blocked`, not an unbounded loop.

### S3: N-candidate compose and localization

After S2 stabilizes, add target-branch pending candidate composition.

Inputs:

- current remote head;
- all pending candidate envelopes for that target branch;
- union test plan.

Behavior:

1. Compose candidates in a deterministic order in a clean integrator worktree.
2. If apply fails, blame the first non-applying candidate.
3. If all apply, run the union test plan once.
4. If green, land/push the maximal green set.
5. If red, localize by leave-one-out reruns first. Bisection can wait.
6. Return precise `rework_required` only for blamed candidate(s).

Machine acceptance:

- three candidates: two disjoint + one conflicting candidate;
- oracle lands the two disjoint candidates together;
- the conflicting candidate receives rework with failing apply/test evidence;
- pending index reflects final states without stale entries.

### S4: Certified test interface

Only after S1-S3 are stable, extend reviewer output with certified tests.

Proposed shape:

```json
{
  "certified_tests": [
    {
      "id": "...",
      "kind": "pytest | shell | verifier",
      "content_sha256": "...",
      "runner": "...",
      "covers": ["behavior-or-scope-label"]
    }
  ]
}
```

Rules:

- The oracle executes the pinned test artifact, not the mutable post-merge test
  file.
- Certified tests are added to the union test plan with always-on invariants.
- Missing or stale certified-test content invalidates the certify claim, not the
  candidate diff itself.
- Until this exists, use full verifier plan + always-on invariants.

### S5: Certified-test adequacy through mutation

Reuse the existing mutation entrypoint, but move from optional handoff signal to
certified-test adequacy gate.

Rules:

- A certified test set must kill enough mutations in the behavior it claims to
  cover.
- Empty or trivial tests cannot certify merge authority.
- Mutation failure invalidates the certify claim and blocks oracle green for the
  relevant reviewer/test set.
- The mutation command must continue to be candidate-hash safe: it must not alter
  the candidate or worktree state it is supposed to evaluate.

### S6: Reviewer-authored test freezing

Reuse the existing frozen-path mechanism.

Rules:

- Reviewer-authored certified tests become frozen for the candidate they review.
- Writer rework may satisfy the test but may not weaken the test.
- Frozen path registration should be harness-written, probably as task-local
  runtime evidence plus a project freeze file only when the repo-level pre-commit
  needs to enforce it.

## Explicit Non-Goals

- Do not add active/reference docs in this slice.
- Do not add a human-facing dashboard or broad scheduler.
- Do not replace exact-CAS with a weaker push rule.
- Do not use an AI resolver for merge authority.
- Do not hold the remote lock while composing/testing.
- Do not introduce provider PR or external merge-queue dependency.
- Do not implement certify granularity before the oracle has empirical data.

## Recommended Implementation Order

1. S1: `merge_oracle.py` single-candidate oracle, tests first.
2. S2: `push.py remote_changed` oracle retry, tests first.
3. S3: target pending index + N-candidate compose/localize.
4. S4: certified-test reviewer interface.
5. S5: mutation adequacy for certified tests.
6. S6: reviewer-authored certified test freezing.

The minimum useful slice is S1 + S2. It keeps the existing optimistic serialized
integrator model, but lets the harness recover the disjoint concurrent case
mechanically.

## Acceptance Test Plan

Use the uploaded characterization test as the baseline contract:

- keep `test_sequential_overlap_forces_rebase_at_land` behavior;
- keep `test_concurrent_overlap_serialized_by_push_cas` no-clobber behavior;
- intentionally change `test_disjoint_concurrent_rejected_by_exact_cas` when S2
  lands so it expects oracle green and automatic repush instead of
  `remote_changed` failure.

Add oracle-specific tests:

- candidate hash mismatch;
- apply failure blame;
- verifier failure blame;
- lock release on green, red, and retry exhaustion;
- runtime artifact placement under git common-dir harness runtime;
- certified-test content pinning once S4 exists;
- mutation adequacy once S5 exists;
- frozen reviewer test protection once S6 exists.

## Open Questions Before Implementation

1. Should the pending target index be task-local plus discoverable by scanning,
   or one explicit per-target runtime index? The proposal favors a per-target
   runtime index because N-candidate compose needs deterministic membership.
2. Should oracle green produce a new `land-result.json`, a new `push-result.json`,
   or a separate `oracle-result.json` linked from both? The proposal favors a
   separate oracle result linked from push result.
3. What is the initial always-on invariant set? Until defined, use all existing
   task verifiers marked `always` plus the writer verifier plan.
4. How should retry exhaustion be named: `blocked`, `escalated`, or
   `rework_required`? The proposal favors `escalated` when no candidate is
   blamed.

## Verification For This Proposal Slice

Not run. This slice intentionally creates only a proposal, index entry, and log.
Implementation and test execution are deferred to a separate approved slice.

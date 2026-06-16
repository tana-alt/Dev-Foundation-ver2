# Worktree / Land / Push Implementation Plan

作成日: 2026-06-15
対象: `workflow_core.contract_harness`
基点: `Plan/harness-review/plans/harness-handoff.md`

## Goal

`verify -> submit -> dispatch/integrate -> review/gate` の最小実行版を、
安全な workspace 管理と remote 反映まで拡張する。

中心方針:

- 共有 artifact の制約を先に固定する。
- `policy.yaml` に全エージェント共有の goal / constraints / bottlenecks を明示する。
- integrator 層は 1 体だけが branch/task の書き込みを担当する。
- worktree 分離、affected-set 判定、land、push rescue、global push-lock の順に足す。
- remote 更新後は local main も機械的に最新化する。

## Non-Goals

この plan では以下を後段に残す。

- cloud queue / dashboard / provider SDK integration
- semantic reviewer の provider 実装
- remote force rollback の自動実行
- multi-writer の大規模 scheduler
- protected branch policy の迂回
- RFC decision 実処理
- multi-writer orchestration
- scope policy の `policy.yaml` への混入

## External Write Policy

Remote ref 更新は、逃げ道としての `human_review` / `human_gate` では表現しない。
実行可否は `policy.yaml` の `constraints.external_writes` に従って機械判定する。

Protected external write が許可されていない場合の結果は完了ではない。

```json
{
  "ok": false,
  "status": "blocked",
  "reason": "protected_external_write",
  "completed": false
}
```

Local worktree 作成、local land、local verification、local bare remote を使うテストは
通常の local write として実装できる。本物の remote ref 更新は `policy.yaml` が
`mode: enabled` を明示した時だけ command が実行可能になる。

## Core Concepts

### Shared Artifacts

共有 artifact は runtime root 配下に置き、tracked repo truth と分離する。

```text
<git-common-dir>/harness-runtime/
  state/tasks/<task_id>/
    contract.lock.json
    verifier-plan.json
    capsule.json
    candidate.diff
    verify-result.json
    submission.json
    reviews/*.json
    gate-result.json
    land-result.json
    push-result.json
    sync-result.json
    affected-set.json
  worktrees/<task_id>/
    writer/
    reviewers/<reviewer_id>/
    integrator/
  locks/
    gate.lock
    land.lock
    push.<remote>.<branch>.lock
```

Rules:

- `candidate.diff` is immutable after `submission.json` unless writer re-runs `verify` and `submit`.
- Every artifact that affects a decision carries `candidate_diff_sha256` and `machine_evidence_sha256`.
- Reviewer and integrator never trust hand-written evidence hashes from workers.
- Runtime artifacts are never read from `.harness/proposals/**` for acceptance.
- Shared artifact schemas are versioned and deterministic JSON.

### Shared Policy

`.harness/policy.yaml` は全エージェントが共有する前提と目標を持つ。
scope はここに置かない。scope は機械側の contract / affected-set / task packet が持ち、
必要な agent に個別に渡す。

Minimal shape:

```yaml
version: 1

goal:
  summary: safe serialized integration for contract harness tasks

constraints:
  runtime_state:
    must_use_git_common_dir: true
    forbidden_tracked_paths:
      - .harness/state/**
  external_writes:
    default_mode: dry_run
    allowed_roles:
      - integrator
    remotes:
      origin:
        branches:
          main:
            mode: dry_run
            require_rescue_ref: true
            require_push_lock: true
            require_local_sync_after_remote_update: true

bottlenecks:
  integration:
    max_active_integrators_per_branch: 1
    lock_timeout_s: 900

metrics:
  observe:
    - rework_rate
    - stale_submission_rate
    - lock_contention_rate
    - local_sync_required_rate
```

Policy should describe:

- protected target branches
- allowed remote names
- branch-level integration bottlenecks
- shared artifact path constraints
- max active integrators per bottleneck, default `1`
- whether remote push is allowed or dry-run only
- observability signals that help improve the harness

The first implementation should enforce only the local deterministic parts:

- one active integrator per task/target branch
- known target branch
- known remote
- runtime artifact paths under git common dir
- no `scope`, `allowed_paths`, or `forbidden_paths` keys in `policy.yaml`

Remote policy can be parsed and reported before actual remote writes are enabled.

### Integrator Unity

There are two acceptable modes:

1. Single active integrator per target branch.
2. Multiple reviewer verdicts, but exactly one integrator owns land/push.

The selected initial mode is single active integrator. Use a local `land.lock` plus
remote `push-lock` before any remote write. The lock is an orchestration boundary,
not a malicious-worker security boundary.

### Local Main Refresh After Remote Update

After remote merge/push succeeds, harness must refresh the local target branch.

Required behavior:

1. `git fetch <remote> <branch>`
2. Verify `refs/remotes/<remote>/<branch>` equals the pushed or merged SHA.
3. If local `<branch>` is checked out and clean, run `git merge --ff-only <remote>/<branch>`.
4. If local `<branch>` is not checked out, update the local branch ref only when it is a fast-forward.
5. If local branch is dirty or non-fast-forward, do not reset. Write `sync-result.json` with
   `status: local_sync_required`.

This prevents the common failure where remote is current but local main remains stale.

## Implementation Phases

### Phase 0 - Shared Artifact And Policy Contract

Implement:

- artifact schema helpers for `land-result.json`, `push-result.json`, `sync-result.json`,
  `affected-set.json`
- strict runtime path validation
- `.harness/policy.yaml` loader for shared goal, constraints, bottlenecks, and metrics
- rejection of scope keys in `policy.yaml`
- explicit result statuses:
  - `ready`
  - `rework_required`
  - `landed`
  - `pushed`
  - `local_synced`
  - `local_sync_required`
  - `blocked_by_lock`

Acceptance tests:

- rejects runtime paths inside `.harness/state`
- rejects unknown target branch or remote from policy config
- rejects `scope`, `allowed_paths`, and `forbidden_paths` in policy config
- artifacts include candidate and machine evidence hashes
- malformed artifacts fail closed

### Phase 1 - Local Locking And Single Integrator Ownership

Implement:

- `gate.lock` and `land.lock` as atomic local lock files under runtime root
- owner fields: `task_id`, `target_branch`, `pid`, `created_at`, `base_sha`
- stale-lock detection with explicit timeout
- `./harness integrate` refuses to land when another active integrator owns the branch

Acceptance tests:

- second integrator for same branch gets `blocked_by_lock`
- stale lock can be reclaimed only after timeout
- lock release happens on success and ordinary failure
- lock is not stored in tracked repo paths

### Phase 2 - Worktree Manager

Implement:

- `./harness worktree <task_id> --writer`
- `./harness worktree <task_id> --reviewer <reviewer_id>`
- `./harness worktree <task_id> --integrator`
- worktrees under `<runtime-root>/worktrees/<task_id>/...`
- deterministic naming and cleanup metadata

Writer worktree:

- created from task base
- writer edits only allowed paths
- `verify` snapshots that worktree, not the parent repo

Reviewer worktree:

- created from candidate base
- applies `candidate.diff`
- reviewer reads files from isolated tree
- deterministic reviewer remains read-only by convention

Integrator worktree:

- created from latest target branch
- applies candidate during land
- owns merge/conflict/test repair in later phases

Acceptance tests:

- parent repo dirty state does not affect writer worktree verify
- reviewer worktree can reconstruct candidate from `candidate.diff`
- integrator worktree starts at latest target branch
- cleanup refuses to delete non-harness worktrees

### Phase 3 - Affected-Set Classification

Implement:

- `affected-set.json`
- classify candidate against latest target branch:
  - `FAST`
  - `PARTIAL`
  - `REBASE`

Definitions:

- `FAST`: target branch still equals prepared base, or candidate applies cleanly with no target drift.
- `PARTIAL`: target branch advanced, but changed paths and one-hop dependency set do not intersect.
- `REBASE`: target branch advanced and candidate affected set intersects target affected set, or patch apply conflicts.

Initial affected set:

- changed candidate paths
- changed target paths since prepared base
- optional one-hop imports/callers only when repo-local tooling exists

Acceptance tests:

- unchanged target -> `FAST`
- unrelated target path -> `PARTIAL`
- same path edited -> `REBASE`
- apply conflict -> `REBASE`
- affected-set output is deterministic

### Phase 4 - Local Land

Implement:

- `./harness land <task_id>`
- requires passed verify, fresh reviews, passed gate, valid submission
- runs in integrator worktree
- applies `candidate.diff` onto latest target branch
- handles classification:
  - `FAST`: apply and run required checks
  - `PARTIAL`: apply, rerun verify/gate on latest target
  - `REBASE`: stop with `rework_required` at first; later allow integrator repair loop
- creates local commit only after checks pass
- writes `land-result.json`

Acceptance tests:

- land does not mutate parent repo HEAD
- land creates a commit in integrator worktree only
- failing checks produce `rework_required`
- `REBASE` without repair does not create commit
- land result records landed commit SHA and target base SHA

### Phase 5 - Remote Push Rescue And Global Push-Lock

Implement in dry-run first:

- remote lock ref:
  - `refs/harness/locks/<remote>/<branch>`
- rescue ref:
  - `refs/harness/rescue/<branch>/<task_id>/<timestamp>`
- push preflight:
  - fetch remote branch
  - verify remote SHA equals expected target base
  - create lock ref
  - create rescue ref from old remote SHA
  - push landed commit
  - release lock

Failure behavior:

- if remote SHA changed, do not push; write `remote_changed`
- if lock exists, write `blocked_by_lock`
- if rescue ref creation fails, do not push
- if push fails after rescue, keep rescue ref and write `push_failed`

Acceptance tests with local bare remote:

- push creates rescue ref before branch update
- concurrent push attempt is blocked by lock
- remote SHA drift blocks push
- failed push leaves rescue ref
- force push is never used in normal path

### Phase 6 - Post-Push Local Sync

Implement:

- `sync_local_target_branch(remote, branch, pushed_sha)`
- called after successful push or remote merge observation
- writes `sync-result.json`

Rules:

- fetch first
- verify remote tracking ref equals expected SHA
- update local branch only by fast-forward
- never use `reset --hard` in automatic path
- if dirty, non-fast-forward, or checked-out conflict, report `local_sync_required`

Acceptance tests:

- clean local main fast-forwards after push
- stale local main becomes current after remote merge
- dirty local main is not overwritten
- non-fast-forward local branch is not rewritten
- sync result records old local SHA, remote SHA, and final local SHA

### Phase 7 - Integrator Repair Loop For REBASE

Implement after local land is stable:

- integrator can repair conflicts in integrator worktree
- repair must stay within allowed affected set or require RFC/proposal
- rerun verifiers and gate
- semantic reviewer gets repaired diff and test interpretation
- writes `rework` or `landed`

Acceptance tests:

- conflict repair outside allowed paths is rejected
- repaired diff gets new candidate hash
- old reviewer verdicts become stale
- semantic reviewer receives repaired diff packet

## Deferred Follow-Up

RFC decision execution and multi-writer orchestration are intentionally outside this
implementation slice. They should be designed only after policy, worktree, local land,
push-lock, push rescue, and local sync are mechanically green.

## Verification Plan

Narrow checks during implementation:

```bash
uv run pytest -q tests/workflow_core/test_contract_harness.py
uv run pytest -q tests/workflow_core/test_contract_harness_policy_acceptance.py
uv run pytest -q tests/test_hook_scripts.py
uv run ruff check harness src/workflow_core/contract_harness tests/workflow_core/test_contract_harness.py tests/workflow_core/test_contract_harness_policy_acceptance.py tests/test_hook_scripts.py scripts/hook_stop.py
uv run ruff format --check harness src/workflow_core/contract_harness tests/workflow_core/test_contract_harness.py tests/workflow_core/test_contract_harness_policy_acceptance.py tests/test_hook_scripts.py scripts/hook_stop.py
```

Remote behavior must use local bare remotes in tests. Real remote writes must be
blocked unless policy explicitly enables them.

## Rollback And Mitigation

- Local worktree land failures leave parent repo HEAD unchanged.
- Remote push failures preserve rescue refs.
- Automatic rollback uses revert commit first.
- Ref rollback to rescue SHA is not automatic in this slice.
- Local branch refresh is fast-forward only and never destructive.

## Residual Risks

- Remote lock refs are cooperative and do not protect against non-harness pushers.
- Branch protection rules may reject rescue refs or direct pushes.
- One-hop affected set may be incomplete without language-aware tooling.
- Integrator repair can become semantic implementation work; this needs bounded loop budgets.
- Multi-writer orchestration should not be implemented until land/push/sync are stable.

IMPLEMENTATION_HANDOFF_BACKGROUND_REVIEW_MVP.md
Goal

Implement a minimal provider-neutral contract harness that integrates with the current goal-first harness.

This MVP uses the current repo profile:

1 human-facing writer lane
2 background reviewer lanes
1 background integrator / gate lane

Only the writer layer may interact with a human.

Reviewer and integrator layers must be non-conversational. They operate through CLI commands, JSON artifacts, Stop hooks, and existing repo evidence paths.

Do not build a multi-agent framework.

Do not build:

planner hierarchy
memory DB
vector store
provider SDK integration
MCP integration
dashboard
cloud queue
plugin system
policy DSL
multi-writer orchestration

The harness exists to let the writer produce a verified candidate, background reviewers independently approve or veto that candidate, and one serialized background gate decide whether the candidate is acceptable.

Core change from the previous handoff

The previous handoff mixed too many implementation domains into one slice:

contract generation
writer snapshotting
reviewer worktrees
reviewer verdicts
integrator worktrees
affected-set FAST / PARTIAL / REBASE logic
land / push / rollback
RFC decision artifacts
metrics ingestion
Stop hook integration
role permissions

This version narrows the first implementation slice to a feasible MVP:

MVP implements
repo-root ./harness wrapper
workflow_core.contract_harness package
runtime state under git common dir
Plan-gated Stop hook delegation to ./harness gate
prepare
explain
verify
report
deterministic candidate snapshot from writer working tree
candidate.diff
verify-result.json
deterministic machine_evidence_sha256
two background reviewer verdicts
review freshness / quorum / block veto
gate
completion evidence reuse through existing workflow_core.completion
trajectory / metrics reuse through existing evaluation and MetricsStore
role-boundary checks through CLI role mode
MVP defers
land
real push
remote rollback
global push-lock semantics
external writer worktrees
external reviewer worktrees
affected-set FAST / PARTIAL / REBASE
RFC approval / rejection
multi-writer support
semantic AI reviewer implementation

Deferred commands may exist as explicit stubs returning:

{
  "ok": false,
  "reason": "deferred_in_mvp"
}

Do not treat deferred commands as acceptance criteria for this MVP.

Human interaction model
Human-facing layer: writer

The human only interacts with the writer lane.

The writer can:

read task intent
edit source files within allowed paths
run ./harness prepare <task_id>
run ./harness explain <task_id>
run ./harness verify <task_id>
run ./harness report <task_id> --type incident|rfc|metric

The writer must not:

write review verdicts
run background reviewer commands
run gate directly in writer role
run land
approve or reject RFCs
edit active contract inputs
decide mergeability
Background reviewer layer

Reviewers do not talk to the human.

Reviewers are background contract readers.

In the MVP, they are deterministic reviewer profiles implemented by the harness itself:

reader-correctness
reader-scope

They read:

capsule.json
candidate.diff
verify-result.json
contract policy output

They write only:

<runtime-root>/state/tasks/<task_id>/reviews/<reviewer_id>.json

They must not:

edit source files
run verify
run gate
run land
create proposals
hand-write evidence hashes
read conversation history
depend on provider SDKs
Background integrator / gate layer

The integrator layer is non-conversational.

It is invoked by:

scripts/hook_stop.py
tests
CI-like local commands with HARNESS_ROLE=integrator

It can:

run ./harness gate <task_id>
collect review verdicts
enforce quorum
enforce machine gate
write gate-result.json

It must not:

edit source code
resolve conflicts
push
force push
ask the human questions

In this MVP, gate is the integration decision. It does not land or push.

Role model

Use an environment variable for role-boundary enforcement:

HARNESS_ROLE=writer
HARNESS_ROLE=reviewer
HARNESS_ROLE=integrator
HARNESS_ROLE=admin

Default:

HARNESS_ROLE=writer

Allowed commands:

Role	Allowed commands
writer	prepare, explain, verify, report
reviewer	review --run, review --write-verdict
integrator	review --collect, gate
admin	all commands, for tests only

This is an orchestration boundary, not a malicious-worker security boundary.

The tests must confirm that:

writer role cannot write reviews
writer role cannot gate
reviewer role cannot verify
reviewer role cannot gate
integrator role cannot edit candidate state through harness commands
CLI scope for MVP

Implement these commands:

./harness prepare <task_id>
./harness explain <task_id>
./harness verify <task_id>
./harness report <task_id> --type incident|rfc|metric

./harness review <task_id> --run <reviewer_id>
./harness review <task_id> --write-verdict <reviewer_id> approve|block [--label L] [--reason TEXT]
./harness review <task_id> --collect

./harness gate <task_id>

Deferred stubs:

./harness worktree <task_id>
./harness worktree <task_id> --reviewer <reviewer_id>
./harness land <task_id>
./harness rfc <task_id> approve|reject <rfc_id> --reason <text>

Deferred stubs must return non-zero with:

{
  "ok": false,
  "reason": "deferred_in_mvp"
}
Runtime state layout

Runtime state must not be worktree-local.

Resolve runtime root as:

git rev-parse --git-common-dir

Then use:

<git-common-dir>/harness-runtime/
  state/
    tasks/
      <task_id>/
        capsule.json
        contract.lock.json
        verifier-plan.json
        candidate.diff
        verify-result.json
        reviews/
          reader-correctness.json
          reader-scope.json
        gate-result.json

  locks/
    gate.lock

Allow override:

HARNESS_RUNTIME_ROOT=/custom/path

Do not store runtime state in:

.harness/state
Tracked repository layout

Use the existing repo tree:

.harness/
  bottleneck.yaml
  owners.yaml
  verifiers.yaml
  review.yaml

  tasks/
    <task_id>/
      task.yaml

  proposals/
    rfcs/
    incidents/
    metrics/

  rfc-decisions/

  schemas/

Writer may create files under:

.harness/proposals/**

Writer and reviewer must not edit:

.harness/bottleneck.yaml
.harness/owners.yaml
.harness/verifiers.yaml
.harness/review.yaml
.harness/rfc-decisions/**
.harness/tasks/*/task.yaml
.harness/generated/**
Provider-neutrality

Harness core may depend only on:

git
shell
filesystem
JSON / YAML
subprocess

Allowed Python dependencies:

PyYAML
pathspec

Do not depend on:

OpenAI SDK
Anthropic SDK
MCP
AGENTS.md
Claude config
Codex config
conversation history
vector store
memory DB
Data model
.harness/tasks/<task_id>/task.yaml

Example:

id: T-0001
scope: payments
base: main
intent:
  kind: implementation
  summary: fix retry idempotency bug
acceptance:
  mode: generated
allowed_outputs:
  - source_diff
  - incident
  - rfc_proposal
  - metric_report

Reject anything except:

acceptance:
  mode: generated
prepare behavior

Command:

./harness prepare T-0001

Required behavior:

Resolve runtime root.
Load .harness/tasks/T-0001/task.yaml.
Load:
.harness/bottleneck.yaml
.harness/owners.yaml
.harness/verifiers.yaml
.harness/review.yaml
.harness/rfc-decisions/**
Reject if acceptance.mode != generated.
Resolve task scope.
Build allowed paths and forbidden paths.
Inject global forbidden paths.
Build verifier plan.
Compute contract_semantic_sha256.
Write:
contract.lock.json
verifier-plan.json
capsule.json

Must not read:

.harness/proposals/**

Proposals must never affect acceptance.

contract.lock.json

Generated by prepare.

Minimal required shape:

{
  "task_id": "T-0001",
  "prepared_base_sha": "abc123",
  "input_hashes": {
    "bottleneck.yaml": "sha256:...",
    "owners.yaml": "sha256:...",
    "verifiers.yaml": "sha256:...",
    "review.yaml": "sha256:...",
    "rfc-decisions": "sha256:...",
    "task.yaml": "sha256:..."
  },
  "scope_contract": {
    "allowed_paths": [
      "services/payments/**",
      "tests/payments/**"
    ],
    "forbidden_paths": [
      ".harness/bottleneck.yaml",
      ".harness/owners.yaml",
      ".harness/verifiers.yaml",
      ".harness/review.yaml",
      ".harness/rfc-decisions/**",
      ".harness/tasks/*/task.yaml",
      ".harness/generated/**"
    ]
  },
  "verifier_plan": [
    {
      "id": "check_required",
      "command": "make check-required",
      "applies_to": ["**/*"],
      "always": true
    }
  ],
  "acceptance": {
    "all_required_verifiers_pass": true,
    "scope_violation_count": 0,
    "proposals_affect_acceptance": false
  },
  "contract_semantic_sha256": "sha256:..."
}

contract_semantic_sha256 must exclude:

prepared_base_sha
explain behavior

Command:

./harness explain T-0001

Print a human-readable summary for the writer.

It may include:

task id
scope
allowed paths
forbidden paths
verifier plan
review quorum
current runtime artifact paths

It must not modify state.

Candidate snapshot behavior

Writer commits are not required.

verify must snapshot the active working tree into candidate.diff.

Use a temporary index.

Do not mutate the writer’s real index.

Algorithm:

List changed files:
git status --porcelain=v1 -z
Resolve changed files to repo-relative paths.
Ignore runtime state files.
Allow:
files matching allowed_paths
files under .harness/proposals/**
Reject:
files outside allowed paths
files matching forbidden paths
active contract input edits
.harness/rfc-decisions/** edits by writer
Create temporary index.
Read base tree into temporary index:
GIT_INDEX_FILE="$TMP_INDEX" git read-tree <base_sha>
Stage concrete changed files only.

Do not pass raw globs to git add.

Use pathspec to match policy globs.

Generate deterministic diff:
GIT_INDEX_FILE="$TMP_INDEX" \
git -c core.autocrlf=false \
    -c diff.noprefix=false \
    -c diff.renames=false \
    diff --cached --binary --full-index <base_sha>
Save:
<runtime-root>/state/tasks/<task_id>/candidate.diff
Hash candidate.diff as:
candidate_diff_sha256
verify behavior

Command:

./harness verify T-0001

Required behavior:

Ensure prepare output exists, or run prepare.
Recompute contract semantics.
Reject if semantic hash changed.
Snapshot active working tree to candidate.diff.
Run verifiers from verifier-plan.json.
Compute machine_evidence_sha256.
Write verify-result.json.
Exit 0 only if:
no scope violation
no forbidden path edit
contract semantics are reproducible
all required verifiers pass
verify-result.json

Minimal required shape:

{
  "task_id": "T-0001",
  "status": "pass",
  "base_sha": "abc123",
  "candidate_diff_sha256": "sha256:...",
  "contract_lock_sha256": "sha256:...",
  "contract_semantic_sha256": "sha256:...",
  "machine_evidence_sha256": "sha256:...",
  "scope": {
    "violation_count": 0,
    "violations": []
  },
  "contract": {
    "semantic_reproducible": true,
    "unapproved_change": false
  },
  "verifiers": [
    {
      "id": "check_required",
      "status": "pass",
      "exit_code": 0,
      "duration_ms": 1234
    }
  ]
}
Machine evidence hash

Hash canonical JSON.

Rules:

sort object keys
sort verifiers by id
no whitespace
exclude volatile fields

Canonical form:

{
  "task_id": "T-0001",
  "candidate_diff_sha256": "sha256:...",
  "contract_semantic_sha256": "sha256:...",
  "scope_violation_count": 0,
  "verifiers": [
    {
      "id": "check_required",
      "status": "pass"
    }
  ]
}

Do not include:

base_sha
prepared_base_sha
duration_ms
timestamp
log path
full contract_lock_sha256
Background review config

Tracked file:

.harness/review.yaml

MVP shape:

default:
  quorum: 2
  reviewers:
    - reader-correctness
    - reader-scope
  background_auto_run: true
  blocking_labels:
    - scope_risk
    - missing_repro
    - acceptance_gap
    - machine_failed
    - protected_contract_edit

metrics:
  reject_unexpected_actions: false

Rules:

quorum defaults to 2
current repo profile requires two fresh approvals
any fresh block verdict rejects
approve contributes only to quorum
approve must never override a failing machine gate
labels are explanatory only
labels do not approve anything
Background reviewer profiles
reader-scope

Command:

HARNESS_ROLE=reviewer ./harness review T-0001 --run reader-scope

Behavior:

Approve only if:

candidate.diff exists
verify-result.json exists
candidate_diff_sha256 matches current candidate.diff
scope.violation_count == 0
no changed file matches forbidden paths
no changed file edits active contract inputs
.harness/proposals/** changes are ignored for acceptance

Block if any of the above fails.

Suggested block labels:

scope_risk
protected_contract_edit
reader-correctness

Command:

HARNESS_ROLE=reviewer ./harness review T-0001 --run reader-correctness

Behavior:

Approve only if:

verify-result.json.status == pass
all required verifiers are pass
machine_evidence_sha256 recomputes exactly
contract.semantic_reproducible == true
candidate_diff_sha256 matches current candidate.diff

Block if any of the above fails.

Suggested block labels:

missing_repro
acceptance_gap
machine_failed
Verdict writing

Low-level command:

HARNESS_ROLE=reviewer ./harness review T-0001 --write-verdict reader-correctness approve
HARNESS_ROLE=reviewer ./harness review T-0001 --write-verdict reader-scope block --label scope_risk --reason "forbidden path changed"

Required behavior:

Resolve runtime root.
Read current candidate.diff.
Read current verify-result.json.
Validate reviewer_id.
Validate verdict is approve or block.
Read candidate_diff_sha256 from verify-result.json.
Read machine_evidence_sha256 from verify-result.json.
Construct verdict JSON.
Atomic write to:
reviews/<reviewer_id>.json

Reviewer must not provide evidence hashes.

Harness stamps evidence hashes.

Verdict artifact

Path:

<runtime-root>/state/tasks/T-0001/reviews/<reviewer_id>.json

Example:

{
  "task_id": "T-0001",
  "reviewer_id": "reader-correctness",
  "verdict": "approve",
  "labels": [],
  "reason": "",
  "evidence_seen": {
    "candidate_diff_sha256": "sha256:...",
    "machine_evidence_sha256": "sha256:..."
  },
  "written_by": "harness",
  "written_at": "2026-06-15T00:00:00Z"
}

written_at is not part of freshness calculation.

Atomic write requirement

Implement verdict writes as atomic replace.

Python behavior:

tmp = reviews_dir / f".{reviewer_id}.json.tmp.{os.getpid()}"
write_json(tmp, verdict)
fsync_file(tmp)
os.replace(tmp, reviews_dir / f"{reviewer_id}.json")
fsync_dir(reviews_dir)

Also require:

reviewer_id must match ^[A-Za-z0-9._-]+$
no slash
no path traversal
Review collect

Command:

HARNESS_ROLE=integrator ./harness review T-0001 --collect

Must:

Read .harness/review.yaml.
Resolve task scope.
Read verify-result.json.
Read reviews/*.json.
Ignore malformed verdicts.
Ignore unknown reviewers if reviewer list is configured.
Ignore stale verdicts.
Count fresh approve verdicts.
Detect fresh block verdicts.
Return JSON summary.

Freshness rule:

A verdict is fresh iff:

verdict.evidence_seen.candidate_diff_sha256 == current verify-result candidate_diff_sha256
AND
verdict.evidence_seen.machine_evidence_sha256 == current verify-result machine_evidence_sha256

Pass example:

{
  "task_id": "T-0001",
  "quorum": 2,
  "fresh_approves": 2,
  "fresh_blocks": 0,
  "stale": [],
  "unknown_reviewers": [],
  "blocking_verdicts": [],
  "review_pass": true
}

Reject example:

{
  "task_id": "T-0001",
  "quorum": 2,
  "fresh_approves": 1,
  "fresh_blocks": 1,
  "stale": [],
  "unknown_reviewers": [],
  "blocking_verdicts": ["reader-scope"],
  "review_pass": false
}
Gate behavior

Command:

HARNESS_ROLE=integrator ./harness gate T-0001

gate is the MVP integrator.

It must not:

mutate main
create commits
push
force push
resolve conflicts
ask the human questions

Algorithm:

Resolve runtime root.
Read:
candidate.diff
verify-result.json
contract.lock.json
review.yaml
Validate candidate_diff_sha256.
Validate verify-result.status == pass.
Validate current working-tree diff still matches candidate.diff.
Run current repo completion check tier:
make ${FOUNDATION_GATE_TIER:-check-required}
Write completion evidence through existing workflow_core.completion.

Use the same evidence shape as the current Stop hook / completion gate path.

If completion evidence fails, reject:
{
  "mergeable": false,
  "reason": "machine_gate_failed"
}
Reuse existing trajectory and metrics paths.

Do not create another trajectory system.

Use existing:

workflow_core.hook_events
workflow_core.runtime
workflow_core.evaluation
workflow_core.metrics_store
Add metric signals to gate-result.json:
{
  "tool_calls": 0,
  "tool_call_rate": 0.0,
  "skill_uses": 0,
  "skill_usage_rate": 0.0,
  "unexpected_actions": []
}
If .harness/review.yaml says:
metrics:
  reject_unexpected_actions: true

then reject when unexpected actions exist:

{
  "mergeable": false,
  "reason": "unexpected_actions"
}
If background_auto_run: true, run missing or stale background reviewers:
reader-correctness
reader-scope
Collect reviews.
Require:
two fresh approvals
zero fresh blocks
no stale-only quorum
Reject cases:
review_blocked
review_quorum_unmet
review_recollect_required
machine_gate_failed
candidate_hash_mismatch
contract_semantic_mismatch
unexpected_actions
Write:
gate-result.json
Print final JSON to stdout.

Pass result example:

{
  "task_id": "T-0001",
  "mergeable": true,
  "reason": "ok",
  "candidate_diff_sha256": "sha256:...",
  "machine_evidence_sha256": "sha256:...",
  "review": {
    "quorum": 2,
    "fresh_approves": 2,
    "fresh_blocks": 0,
    "review_pass": true
  },
  "completion": {
    "status": "pass"
  },
  "metrics": {
    "tool_calls": 8,
    "tool_call_rate": 0.2,
    "skill_uses": 1,
    "skill_usage_rate": 0.025,
    "unexpected_actions": []
  }
}

Reject result example:

{
  "task_id": "T-0001",
  "mergeable": false,
  "reason": "review_blocked",
  "candidate_diff_sha256": "sha256:...",
  "machine_evidence_sha256": "sha256:...",
  "review": {
    "quorum": 2,
    "fresh_approves": 1,
    "fresh_blocks": 1,
    "blocking_verdicts": ["reader-scope"],
    "review_pass": false
  }
}
Stop hook integration

Modify:

scripts/hook_stop.py

Current behavior:

unplanned work exits single-pass
planned work runs make <FOUNDATION_GATE_TIER> directly

New behavior:

Detect planned work using existing workflow_core.plans.
If unplanned and FOUNDATION_SPEC_PRESENT is not set:
keep current single-pass behavior
do not call ./harness gate
If planned:
resolve task_id
default task_id to FOUNDATION_PROJECT_ID
call:
HARNESS_ROLE=integrator ./harness gate <task_id>
Stop hook must not run make <tier> directly for planned work.
./harness gate owns:
completion check tier
evidence writing
review quorum
metrics inclusion
final gate decision
Path matching

Use pathspec.

Do not use Python fnmatch for policy matching.

Required behavior:

** recursive matching
directory matches
repo-relative paths only
no absolute path matching
no acceptance-affecting read from .harness/proposals/**
Python module layout

Add:

src/workflow_core/contract_harness/
  __init__.py
  cli.py
  config.py
  runtime_paths.py
  gitutil.py
  hashing.py
  paths.py
  contract.py
  capsule.py
  snapshot.py
  verifier.py
  policy.py
  review.py
  gate.py
  report.py
  roles.py

Deferred modules may be omitted or added as stubs:

  affected.py
  land.py
  lock.py
  rfc.py
  worktree.py

Repo-root wrapper:

./harness

Wrapper behavior:

Set sys.path to include src/.
Import workflow_core.contract_harness.cli.
Call CLI main.
Reuse existing modules

Do not duplicate current harness systems.

Reuse:

workflow_core.completion
workflow_core.plans
workflow_core.hook_events
workflow_core.runtime
workflow_core.evaluation
workflow_core.metrics_store

make measure and make issues remain public commands.

./harness gate may call the same underlying modules directly.

MVP implementation phases
Phase 0 — wrapper and Stop hook integration

Implement:

repo-root ./harness
CLI skeleton
runtime root resolution
role enforcement
Stop hook delegation for Plan-gated work
unplanned Stop hook unchanged

Tests:

ID	Test	Expected
M0.1	unplanned Stop hook	no harness gate, exit 0
M0.2	Plan-gated Stop hook	calls HARNESS_ROLE=integrator ./harness gate <task>
M0.3	writer role calls gate	rejected
M0.4	integrator role calls verify	rejected
Phase 1 — prepare / explain / contract policy

Implement:

config loading
task.yaml loading
acceptance.mode == generated enforcement
protected input hashing
contract.lock.json
verifier-plan.json
capsule.json
explain
pathspec-based policy

Tests:

ID	Test	Expected
M1.1	acceptance.mode != generated	prepare reject
M1.2	unknown scope	prepare reject
M1.3	no verifier	prepare reject
M1.4	proposal file exists	contract semantic hash unchanged
M1.5	protected RFC decision changes	contract semantic hash changes
Phase 2 — writer snapshot and verify

Implement:

temporary index snapshot
deterministic candidate.diff
scope checks
verifier execution
verify-result.json
canonical machine_evidence_sha256

Tests:

ID	Test	Expected
M2.1	allowed source edit	verify can pass
M2.2	forbidden path edit	verify reject
M2.3	active contract edit	verify reject
M2.4	verifier exits non-zero	verify non-zero
M2.5	snapshot preserves writer index	index unchanged
M2.6	deterministic diff	same candidate hash across git config changes
M2.7	proposal added	proposal may appear in diff but does not affect acceptance
Phase 3 — background reviewer lane

Implement:

review --run reader-correctness
review --run reader-scope
review --write-verdict
atomic verdict writes
evidence stamping
review --collect
stale verdict detection
quorum
block veto

Tests:

ID	Test	Expected
M3.1	reader-correctness approve	verdict written by harness
M3.2	reader-scope approve	verdict written by harness
M3.3	scope violation	reader-scope blocks
M3.4	failing verifier	reader-correctness blocks
M3.5	reviewer provides evidence hash	rejected / ignored
M3.6	verdict write	atomic replace
M3.7	stale review after candidate hash change	ignored
M3.8	two fresh approvals	review pass
M3.9	one fresh block	review fail
M3.10	quorum unmet	review fail
Phase 4 — gate

Implement:

gate
configured make tier execution
completion evidence reuse
existing metrics reuse
background auto-review
quorum enforcement
block veto
gate-result.json

Tests:

ID	Test	Expected
M4.1	candidate hash mismatch	gate reject
M4.2	writer verify failed	gate reject
M4.3	completion check failed	gate reject machine_gate_failed
M4.4	missing reviews with auto-run	background reviewers run
M4.5	two fresh approvals	gate mergeable true
M4.6	fresh block	gate reject review_blocked
M4.7	stale approvals	gate refreshes or rejects
M4.8	unexpected actions with reject policy	gate reject
M4.9	metrics present	tool_call_rate and skill_usage_rate in gate result
M4.10	gate immutability	HEAD unchanged
Deferred phase: land / push / affected set

Do not implement in MVP.

Create a follow-up handoff for:

external worktrees
affected-set FAST / PARTIAL / REBASE
integration lock
detached integration commit
ff-only merge
push without force
push failure rescue refs
RFC approve / reject
writer worktree isolation

Do not claim those are complete in the MVP.

MVP acceptance list

Codex must implement at least these tests.

ID	Test	Expected
A1	unplanned Stop hook	no gate call
A2	Plan-gated Stop hook	delegates to ./harness gate
A3	writer role cannot gate	rejected
A4	reviewer role cannot verify	rejected
A5	integrator role cannot verify	rejected
A6	prepare generated acceptance only	non-generated rejected
A7	proposals ignored for acceptance	semantic hash unchanged
A8	protected contract edit	verify rejected
A9	forbidden source edit	verify rejected
A10	snapshot uses temp index	real index unchanged
A11	verify writes candidate diff	candidate.diff exists
A12	verify writes machine evidence	hash exists and recomputes
A13	reviewer verdict evidence	stamped by harness
A14	hand-written / malformed verdict	ignored by collect
A15	stale verdict	ignored
A16	two fresh approvals	review pass
A17	one block	review fail
A18	approve over failing machine gate	still rejected
A19	gate runs make tier	configured tier called
A20	gate writes completion evidence	existing completion path used
A21	gate includes metrics	tool / skill metrics present
A22	unexpected actions reject policy	gate rejected when configured
A23	gate does not mutate HEAD	same HEAD before/after
A24	provider neutral	no provider SDK imports
Known limitations to document
Background reviewers in MVP are deterministic policy reviewers, not semantic AI reviewers.
Reviewer identity is not cryptographically guaranteed.
Role enforcement is a CLI orchestration boundary, not a malicious-worker security boundary.
Gate does not land or push in MVP.
FAST / PARTIAL / REBASE affected-set logic is deferred.
Reviewer worktrees are deferred.
RFC semantic promotion is deferred.
Multi-writer support is deferred.
No provider SDK, MCP, memory DB, planner, scheduler, dashboard, or cloud queue.
Human feedback enters only through the writer layer.
What Codex must return after MVP implementation

Codex must return:

Implemented files
Commands run
Test results
Known limitations
Invariant-to-test mapping
Writer / reviewer / integrator role-boundary results
Confirmation that Stop hook delegates Plan-gated work to ./harness gate
Confirmation that runtime state is under git common dir
Confirmation that proposals do not affect acceptance
Confirmation that reviewer verdict evidence is stamped by harness
Confirmation that approve cannot override a failing machine gate
Confirmation that block veto rejects gate
Confirmation that gate-result.json includes tool_call_rate and skill_usage_rate
Confirmation that no provider SDK or MCP dependency was added
Confirmation that gate does not mutate HEAD

Do not claim land / push completion in this MVP.

Codex final prompt

Use this prompt instead of the original one.

Implement IMPLEMENTATION_HANDOFF_BACKGROUND_REVIEW_MVP.md.

Critical architecture:

- Only the writer layer is human-facing.
- Reviewer and integrator layers are non-conversational background lanes.
- Current repo profile is:
  - 1 writer
  - 2 background reviewers
  - 1 background integrator / gate
- Multi-writer support is deferred.
- land / push / affected-set FAST-PARTIAL-REBASE are deferred.
- Do not build a multi-agent framework.
- Do not build memory, vector store, scheduler, dashboard, cloud queue, plugin system, provider SDK integration, or MCP integration.

Writer role:

- May run:
  - ./harness prepare <task_id>
  - ./harness explain <task_id>
  - ./harness verify <task_id>
  - ./harness report <task_id> --type incident|rfc|metric
- May edit allowed source paths.
- May create files under .harness/proposals/**.
- Must not write review verdicts.
- Must not run gate.
- Must not run land.
- Must not decide RFCs.
- Must not edit active contract inputs.

Reviewer role:

- Is background-only.
- Does not talk to the human.
- May run:
  - ./harness review <task_id> --run <reviewer_id>
  - ./harness review <task_id> --write-verdict <reviewer_id> approve|block [--label L] [--reason TEXT]
- Reviewer verdict files must be atomic writes.
- Harness must stamp candidate_diff_sha256 and machine_evidence_sha256.
- Reviewer must not provide evidence hashes.
- Reviewer must not edit source.
- Reviewer must not run verify, gate, land, report, or rfc.

Integrator role:

- Is background-only.
- Invoked by Stop hook or tests.
- May run:
  - ./harness review <task_id> --collect
  - ./harness gate <task_id>
- Must not edit source.
- Must not push.
- Must not force push.
- In this MVP, gate is the integration decision.
- land is deferred.

Required MVP commands:

- ./harness prepare <task_id>
- ./harness explain <task_id>
- ./harness verify <task_id>
- ./harness report <task_id> --type incident|rfc|metric
- ./harness review <task_id> --run <reviewer_id>
- ./harness review <task_id> --write-verdict <reviewer_id> approve|block [--label L] [--reason TEXT]
- ./harness review <task_id> --collect
- ./harness gate <task_id>

Deferred commands may exist as stubs returning reason deferred_in_mvp:

- ./harness worktree <task_id>
- ./harness worktree <task_id> --reviewer <reviewer_id>
- ./harness land <task_id>
- ./harness rfc <task_id> approve|reject <rfc_id> --reason <text>

Runtime:

- Runtime state must be stored under git common dir:
    <git-common-dir>/harness-runtime/state/tasks/<task_id>/
- Locks must be stored under:
    <git-common-dir>/harness-runtime/locks/
- Do not store runtime state in worktree-local .harness/state.
- Allow HARNESS_RUNTIME_ROOT override.

Stop hook:

- Unplanned work remains single-pass.
- Planned work must call:
    HARNESS_ROLE=integrator ./harness gate <task_id>
- Stop hook must not run make <FOUNDATION_GATE_TIER> directly for planned work.
- ./harness gate owns the check tier, completion evidence, metrics, review quorum, and final decision.

Contracts:

- acceptance.mode must be generated.
- Active contracts must be generated from protected inputs.
- proposals/** must never affect acceptance.
- Contract compiler must read rfc-decisions/** but must never read proposals/**.
- Use pathspec for policy matching.
- Do not use fnmatch for harness policy.

Candidate:

- Candidate state must be represented by candidate.diff.
- candidate.diff must be generated from the writer working tree using a temporary index.
- Writer commits are not required.
- The real writer index must not be mutated.
- machine_evidence_sha256 must exclude base_sha and volatile fields.

Background reviewers:

Implement two deterministic background reviewer profiles:

1. reader-scope
   - approves only if candidate paths obey allowed/forbidden policy
   - blocks protected contract edits
   - ignores proposals for acceptance

2. reader-correctness
   - approves only if verify-result.status is pass
   - all required verifiers pass
   - machine_evidence_sha256 recomputes
   - contract semantics are reproducible

Review rules:

- quorum defaults to 2.
- current repo profile requires two fresh approvals.
- any fresh block verdict rejects.
- approve only contributes to quorum.
- approve must never override a failing machine gate.
- stale verdicts are ignored.
- malformed verdicts are ignored.

Gate:

- Validate candidate hash.
- Validate writer verify-result.status == pass.
- Run make ${FOUNDATION_GATE_TIER:-check-required}.
- Reuse workflow_core.completion for completion evidence.
- Reuse existing trajectory and MetricsStore data.
- Include tool_calls, tool_call_rate, skill_uses, skill_usage_rate, and unexpected_actions in gate-result.json.
- Reject unexpected actions only when configured by .harness/review.yaml.
- Auto-run missing or stale background reviewers when background_auto_run is true.
- Require two fresh approvals and no fresh block.
- Write gate-result.json.
- Must not mutate HEAD.
- Must not push.

Tests:

Implement the MVP acceptance tests listed in IMPLEMENTATION_HANDOFF_BACKGROUND_REVIEW_MVP.md.

Return:

1. implemented files
2. commands run
3. test results
4. known limitations
5. invariant-to-test mapping
6. writer/reviewer/integrator role-boundary confirmation
7. Stop-hook Plan-gated integration confirmation
8. review veto/quorum/staleness confirmation
9. proposals/** acceptance isolation confirmation
10. reviewer evidence stamping confirmation
11. approve-cannot-override-machine-gate confirmation
12. block-veto confirmation
13. tool_call_rate / skill_usage_rate gate-result confirmation
14. provider-neutrality confirmation
15. confirmation that gate does not mutate HEAD

Do not claim land or push support in this MVP.
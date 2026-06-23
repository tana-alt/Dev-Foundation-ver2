---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
updated_at: 2026-06-17
---

# Git Worktree And Branch Reference

Use this reference only for concrete Git branch, worktree, changed-path,
conflict-check, and protected-branch mechanics.

## Trigger

Open this reference when:

- local write work needs branch or worktree isolation, branch naming, worktree
  creation or validation, canonical primary freshness evidence, or protected
  branch/worktree policy;
- parallel `git_scope` must be checked for completeness, or branch/worktree
  targets must be derived from `work_id`, `lane`, and a short slug;
- changed-path evidence, allowed-write-target checks, sibling-conflict checks,
  or concrete PR-prep mechanics require branch/worktree facts;
- contract-harness `land` or `push` behavior must handle a target branch that
  advanced after a writer candidate was prepared.

Do not open this reference when:

- the task is read-only and asks for wording, review, explanation, or planning
  with no local write, branch, worktree, changed-path, conflict, or PR action;
- the task only needs conceptual parallel-lane scope or handoff boundaries;
- the task only needs verification command choice, fast/full gate choice, CI/PR
  readiness, record templates, evidence schema, repo placement, storage
  boundaries, or migration acceptance.

Adjacent references:

- Use `agent-runtime-and-scope-reference.md` for conceptual parallel lanes,
  scope boundaries, handoff compatibility, and retry/idempotency; do not pair it
  with this reference solely because a concrete local write is in a parallel
  agent lane.
- Use `verification-ci-and-pr-reference.md` for verification command choice,
  fast/full gate choice, CI/PR readiness, result reporting, and human-gate
  notes beyond concrete branch/worktree mechanics.
- Use `packet-evidence-and-rework-reference.md` for work-contract,
  evidence-record, verification-record, and rework-record fields or templates;
  do not open it solely because Git facts will appear in a handoff evidence
  list.
- Use `repo-boundary-and-storage-reference.md` for durable path placement,
  repo truth surfaces, ignored local state, and storage decisions.

Expected effect after opening:

- Derive or validate owned `agent/*` branch and external worktree targets,
  require complete `git_scope` or return rework, run local-write preflight from
  the canonical repo root, record canonical primary freshness before worktree or
  branch creation, check changed paths against allowed write targets, check
  sibling branch conflicts when refs are supplied, and report branch, worktree,
  base, merge target, changed paths, conflict status, and protected
  branch/worktree constraints without adding a record schema unless requested.

## Required Scope For Parallel Work

Parallel work requires a complete `git_scope`. The scope may provide explicit
`branch_target` and `worktree_target`, or provide `work_id`, `lane`,
`base_ref`, and `merge_target` from which targets can be derived.

Required fields:

- `base_ref`: source branch or commit, e.g. `origin/main`
- `merge_target`: target branch or ref for review, e.g. `origin/main`
- `allowed_write_targets`: paths this agent may edit
- `branch_target`: branch owned by this agent, or derivable from `work_id`,
  `lane`, and a short task slug
- `worktree_target`: local worktree path outside the canonical repo root, or
  derivable from `work_id` and `lane`
- `sibling_branch_refs`: optional refs for other parallel lanes
- `conflict_policy`: `no_overlap`, `report_overlap`, or `explicitly_scoped`

If required parallel fields are missing, return rework. Do not invent branch or
worktree ownership.

A lane map may supply the fields for each lane before individual workers start.
Workers should receive only their lane slice plus `lane_map_ref`, not the full
map, unless they are coordinating the split.

## Branch And Worktree Naming

Use explicit branch targets from scope when provided.

Single-lane work may use an `agent/<work_id>/<lane>/<slug>` branch in the
canonical repo root. Parallel work must use one branch and one external
worktree per agent.

Project-specific work must stay project-scoped. Include `project_id` in
`work_id` or in explicit branch and worktree targets, and do not share a
worktree across project IDs.

When `FOUNDATION_PROJECT_ID` is set, `scripts/check-agent-worktree-policy.sh`
requires the branch `work_id` to include that project ID. In enforced parallel
worktree mode, the local worktree path must include it too. Placeholder
ownership such as `agent/none/none/none` is invalid.

The same script reads `FOUNDATION_PRIMARY_BRANCH` (default `main`) as the
protected primary branch when locating the canonical worktree and rejecting
direct agent work on the primary branch.

If the scope provides `work_id`, `lane`, and a short task slug, derive:

```text
agent/<work_id>/<lane>/<short-slug>
../worktrees/<repo>/<work_id>-<lane>
```

Examples:

```text
agent/docs-rebuild-20260506/entrypoint/compact-agents
agent/docs-rebuild-20260506/worktree-policy/git-reference
agent/docs-rebuild-20260506/verification/contract-checks
../worktrees/foundation-development/docs-rebuild-20260506-entrypoint
```

Do not reuse another agent's branch or worktree path.

## Starting Parallel Work

The practical entrypoint is the user request or task packet. Treat any explicit
instruction like "run these in parallel", "split into lanes", or "use separate
worktrees" as `git_scope.mode: parallel`.

For each lane, define:

- `work_id`: shared parallel work identifier
- `lane`: unique lane name
- `base_ref`: source branch or commit
- `merge_target`: review target
- `allowed_write_targets`: lane-owned path prefixes
- `branch_target` and `worktree_target`, or enough fields to derive them
- `conflict_policy` and optional `sibling_branch_refs`

When scope includes `lane_map_ref`, first validate the map with
`make check-lanes`, then derive per-lane branch/worktree values from the lane
entry.

To locally enforce worktree separation, set one of:

```sh
export FOUNDATION_REQUIRE_AGENT_WORKTREE=1
git config foundation.requireAgentWorktree true
```

Clear the config after the parallel run if it was only temporary:

```sh
git config --unset foundation.requireAgentWorktree
```

## Preflight

Run from the canonical repo root:

```sh
git rev-parse --show-toplevel
git status --short
git branch --show-current
git worktree list
```

Confirm the repo root matches the task scope and the status is clean or fully
understood.

If `base_ref` is not supplied, inspect the remote default branch:

```sh
git symbolic-ref --quiet --short refs/remotes/origin/HEAD
```

If the base ref cannot be identified, return rework.

Fetch only when allowed by scope or normal local workflow:

```sh
git fetch --prune origin
```

## Canonical Primary Freshness

Before creating or reusing an agent-owned worktree or lane branch for local
write work, record canonical primary freshness evidence from the canonical repo
root. This evidence belongs in the work contract, lane handoff, evidence
record, or final output selected by the active workflow. Do not store it as a
runtime queue, lock ledger, scheduler, worker heartbeat, dashboard, or local
worktree inventory.

The evidence must record exactly one freshness state:

- `current`
- `stale_fast_forwardable`
- `blocked_dirty_primary`
- `blocked_detached_primary`
- `blocked_missing_primary`
- `blocked_diverged_primary`
- `explicit_base_not_primary`
- `not_applicable`

The evidence must include the canonical repo root, primary branch name,
intended base ref, intended merge target, local primary ref when available, and
remote tracking ref when available. When the state is
`stale_fast_forwardable`, also record the post-update primary ref used to derive
or validate the worktree base. When the state is `explicit_base_not_primary`,
record the explicit base ref and why canonical primary freshness is safe or not
applicable for the scoped work.

Worktree or branch creation may proceed only with `current`,
`stale_fast_forwardable` after post-update evidence,
`explicit_base_not_primary`, or `not_applicable`. Return rework before creating
or reusing the agent worktree when the state is `blocked_dirty_primary`,
`blocked_detached_primary`, `blocked_missing_primary`, or
`blocked_diverged_primary`.

## Create An Isolated Worktree

Do not create worktrees inside tracked repo paths. Run in `bash` with resolved
variables from scope or derivation.

```sh
set -eu

: "${BASE_REF:?set BASE_REF from scope}"
: "${BRANCH_TARGET:?set BRANCH_TARGET from scope}"
: "${WORKTREE_TARGET:?set WORKTREE_TARGET from scope}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

git worktree list

if git show-ref --verify --quiet "refs/heads/$BRANCH_TARGET"; then
  echo "branch already exists: $BRANCH_TARGET" >&2
  exit 2
fi

mkdir -p "$(dirname "$WORKTREE_TARGET")"
git worktree add "$WORKTREE_TARGET" -b "$BRANCH_TARGET" "$BASE_REF"
cd "$WORKTREE_TARGET"

test "$(git branch --show-current)" = "$BRANCH_TARGET"
git status --short
```

## Write Rules

Before editing, inspect current file contents. Do not edit outside
`allowed_write_targets`.

After editing, list changed files:

```sh
set -eu
: "${BASE_REF:?set BASE_REF from scope}"

{
  git diff --name-only
  git diff --cached --name-only
  git diff --name-only "$BASE_REF"...HEAD
} | sort -u | sed '/^$/d'
```

Every changed path must be inside `allowed_write_targets`. Use this check when
`ALLOWED_WRITE_TARGETS` is a newline-separated list of allowed path prefixes:

```sh
set -eu
: "${BASE_REF:?set BASE_REF from scope}"
: "${ALLOWED_WRITE_TARGETS:?set newline-separated allowed targets}"

changed_paths="$({
  git diff --name-only
  git diff --cached --name-only
  git diff --name-only "$BASE_REF"...HEAD
} | sort -u | sed '/^$/d')"

CHANGED_PATHS="$changed_paths" python - <<'PY'
import os
import sys

allowed = [p.strip().rstrip('/') for p in os.environ['ALLOWED_WRITE_TARGETS'].splitlines() if p.strip()]
changed = [p.strip() for p in os.environ.get('CHANGED_PATHS', '').splitlines() if p.strip()]

bad = []
for path in changed:
    normalized = path.strip().lstrip('./')
    if not any(normalized == a or normalized.startswith(a + '/') for a in allowed):
        bad.append(path)

if bad:
    print('out-of-scope changed paths:', file=sys.stderr)
    for path in bad:
        print(path, file=sys.stderr)
    sys.exit(4)

print('allowed-write-target check: passed')
PY
```

If the check fails, revert out-of-scope changes or return rework.

## Sibling Conflict Check

When `sibling_branch_refs` are provided, compare changed paths against each
sibling branch. `SIBLING_BRANCH_REFS` is newline-separated.

```sh
set -eu
: "${BASE_REF:?set BASE_REF from scope}"
: "${SIBLING_BRANCH_REFS:?set newline-separated sibling refs}"

tmp_current="$(mktemp)"
tmp_sibling="$(mktemp)"
trap 'rm -f "$tmp_current" "$tmp_sibling"' EXIT

{
  git diff --name-only
  git diff --cached --name-only
  git diff --name-only "$BASE_REF"...HEAD
} | sort -u | sed '/^$/d' > "$tmp_current"

printf '%s\n' "$SIBLING_BRANCH_REFS" | while IFS= read -r ref; do
  [ -n "$ref" ] || continue
  git diff --name-only "$BASE_REF"..."$ref" | sort -u | sed '/^$/d' > "$tmp_sibling"
  overlap="$(comm -12 "$tmp_current" "$tmp_sibling")"
  if [ -n "$overlap" ]; then
    printf 'conflict risk with %s:\n%s\n' "$ref" "$overlap" >&2
    exit 3
  fi
done

printf 'sibling conflict check: passed\n'
```

If sibling refs are not provided, state that sibling conflict detection was
unverified.

## Contract Harness Branch Serialization

This section applies to the task harness path, not ordinary human PR work. The
baseline harness flow is:

```text
prepare -> writer worktree -> verify -> submit -> gate -> land -> push
```

Harness-created worktrees are task-owned under the git common-dir runtime root.
Writer and reviewer worktrees are based on the task's prepared base. The
integrator worktree fetches the configured target branch and uses an
`agent/<task_id>/integrator/land` branch. Existing harness worktrees must carry
the harness marker for the same repository, task, kind, and reviewer; clean
legacy worktrees may be migrated, but dirty or foreign worktrees must not be
reused destructively.

Current target classification is only a pre-check:

- `FAST`: target still equals the prepared base.
- `PARTIAL`: target advanced, but changed paths do not overlap the candidate.
- `REBASE`: target advanced and changed paths overlap the candidate.

The push-time exact-CAS rule still protects the remote branch: a landed commit
whose `target_base_sha` no longer equals the fetched remote head must not be
pushed as-is. Do not solve `remote_changed` by force-push, by holding a remote
lock across unrelated work, by manually editing branch refs, or by asking the
writer to perform branch choreography when the candidate can be machine-tested
against the current target.

### Merge-Oracle Target Behavior

When `push` detects `remote_changed`, the integrator should run a bounded
merge-oracle retry instead of immediately failing the disjoint case:

1. Fetch the current configured target head.
2. Create or reset a clean integrator worktree to that head.
3. Apply the submitted `candidate.diff` exactly as submitted and verify its
   `candidate_diff_sha256` binding.
4. Run the merge test plan against the merged tree `M`. Until certified tests
   exist, use the writer verifier plan plus always-on invariants. After
   certified tests exist, run the union of pinned certified tests plus always-on
   invariants, using the pinned test contents rather than mutable post-merge
   test files.
5. If apply and tests are green, commit the merged tree and retry the exact-CAS
   push against the head that was just tested.
6. If apply or tests are red, return `rework_required` with the failing apply
   step or test evidence and the blamed task.

The remote lock should be acquired only for each concrete push attempt and
released after that attempt. It should not be held while the oracle composes or
runs tests. Retry count must be bounded by policy, for example
`bottlenecks.integration.max_retries`; exhausted retries escalate rather than
looping indefinitely.

Path disjointness is not final merge authority. It is only a cheap signal that
the oracle is likely to pass. The authority is the candidate diff re-applied to
the current target and the pinned test plan passing on the merged tree. This
keeps the branch rule strict enough to prevent clobber while allowing a safe
disjoint candidate to recover automatically.

### Concurrent Candidate Outcomes

Expected outcomes for concurrent candidates:

- Overlap, sequential: after one candidate lands and pushes, a second candidate
  touching the same affected path should return rework before land.
- Overlap, concurrent: two candidates may both land against the same old base,
  but exact-CAS must prevent the loser from clobbering the remote. With the
  oracle path, the loser should re-apply to the current target and return
  rework if apply or tests fail.
- Disjoint, concurrent: the loser should no longer fail solely because the
  remote advanced. It should run the oracle against the new head and, if green,
  auto-repush with both changes present.

For N pending candidates, compose all candidate diffs in a clean integrator
worktree, run the union test plan once, and on red localize the failing task by
leave-one-out reruns before optimizing with bisection. Land the maximal green
set and return precise rework for the blamed candidate.

Machine acceptance should keep the old exact-CAS characterization visible as a
spec shift: the disjoint concurrent case changes from `remote_changed` failure
to oracle green and automatic repush, while overlapping cases continue to avoid
remote clobber.

## Output Evidence

For write work, report:

- repo root
- branch
- worktree
- base ref
- merge target
- canonical primary freshness state and supporting refs
- changed paths
- allowed-write-target check result
- sibling conflict check result, or why it was unverified
- verification commands and result states

For PR or review handoff, also report the owned source branch, intended target
branch, base ref, merge target, branch/worktree ownership, and canonical primary
freshness result. If the intended merge target advanced after the worktree or
branch was created, report whether the review branch was checked against the
newer target, requires rework, or carries explicit residual risk.

For contract-harness `remote_changed` recovery, also report:

- previous `target_base_sha`
- current target head tested by the merge oracle
- candidate diff hash
- test plan source: all verifiers, certified-test union, or always-only
  invariant set
- oracle status: green or red
- retry count
- final push CAS head, if pushed
- failing apply/test evidence and blamed task, if rework is required

## Human Gate

Agents may push owned `agent/*` review branches and open or update PRs when
scope, branch/worktree ownership, changed-path evidence, and verification are
clear.

Opening or updating a PR is a handoff state, not completion. Do not push
directly to `main` or `master`. Do not merge; merge is human-only. Do not delete
branches, delete worktrees, deploy, release, or perform external writes outside
the owned review branch or PR unless scope explicitly allows it or a human
approves it.

`FOUNDATION_ALLOW_AGENT_POLICY_BYPASS=1` is a human break-glass escape hatch for
local recovery only. Record why it was used in handoff evidence and do not use
it to push protected branches, merge, or skip review.

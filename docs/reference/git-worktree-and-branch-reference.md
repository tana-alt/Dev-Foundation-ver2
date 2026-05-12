---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
---

# Git Worktree And Branch Reference

Use this reference only for local writes, branch isolation, parallel agents,
conflict checks, or PR preparation.

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

## Branch And Worktree Naming

Use explicit branch targets from scope when provided.

Project-specific work must stay project-scoped. Include `project_id` in
`work_id` or in explicit branch and worktree targets, and do not share a
worktree across project IDs.

When `FOUNDATION_PROJECT_ID` is set, `scripts/check-agent-worktree-policy.sh`
requires the branch `work_id` and local worktree path to include that project
ID. Placeholder ownership such as `agent/none/none/none` is invalid.

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

## Output Evidence

For write work, report:

- repo root
- branch
- worktree
- base ref
- merge target
- changed paths
- allowed-write-target check result
- sibling conflict check result, or why it was unverified
- verification commands and result states

## Human Gate

Agents may push owned `agent/*` review branches and open or update PRs when
scope, branch/worktree ownership, changed-path evidence, and verification are
clear.

Do not push directly to `main` or `master`. Do not merge; merge is
human-only. Do not delete branches, delete worktrees, deploy, release, or
perform external writes outside the owned review branch or PR unless scope
explicitly allows it or a human approves it.

`FOUNDATION_ALLOW_AGENT_POLICY_BYPASS=1` is a human break-glass escape hatch for
local recovery only. Record why it was used in handoff evidence and do not use
it to push protected branches, merge, or skip review.

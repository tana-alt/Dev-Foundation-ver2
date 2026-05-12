#!/usr/bin/env sh
set -eu
CDPATH=

fail() {
  echo "agent worktree policy: $*" >&2
  exit 2
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  fail "not inside a git worktree"
fi

ROOT="$(git rev-parse --show-toplevel)"
BRANCH="$(git branch --show-current 2>/dev/null || true)"
PRIMARY_BRANCH="${FOUNDATION_PRIMARY_BRANCH:-main}"

if [ -z "$BRANCH" ]; then
  fail "detached HEAD is not allowed for agent write work"
fi

if [ "${FOUNDATION_ALLOW_AGENT_POLICY_BYPASS:-0}" = "1" ]; then
  echo "agent worktree policy: bypassed by explicit environment override"
  exit 0
fi

CONFIGURED_ROOT="$(git config --get foundation.canonicalRoot 2>/dev/null || true)"

if [ -n "$CONFIGURED_ROOT" ]; then
  PRIMARY_ROOT="$CONFIGURED_ROOT"
else
  PRIMARY_ROOT="$(
    git worktree list --porcelain | awk -v branch="refs/heads/$PRIMARY_BRANCH" '
      /^worktree / { current = substr($0, 10) }
      /^branch / && $2 == branch { print current; exit }
    '
  )"
fi

if [ -z "$PRIMARY_ROOT" ]; then
  fail "cannot identify canonical root; run scripts/setup-agent-environment.sh from the canonical repo root"
fi

if [ ! -d "$PRIMARY_ROOT" ]; then
  fail "configured canonical root does not exist: $PRIMARY_ROOT"
fi

ROOT_REAL="$(cd -- "$ROOT" && pwd -P)"
PRIMARY_REAL="$(cd -- "$PRIMARY_ROOT" && pwd -P)"

case "$BRANCH" in
  "$PRIMARY_BRANCH"|master)
    fail "direct writes on $BRANCH are blocked; use agent/<work_id>/<lane>/<slug> in a linked worktree"
    ;;
  agent/*)
    OLD_IFS=$IFS
    IFS=/
    # Intentional slash split for the required agent/<work_id>/<lane>/<slug> shape.
    # shellcheck disable=SC2086
    set -- $BRANCH
    IFS=$OLD_IFS
    if [ "$#" -ne 4 ] || [ "$1" != "agent" ] || [ -z "$2" ] || [ -z "$3" ] || [ -z "$4" ]; then
      fail "branch '$BRANCH' is blocked for agent work; use agent/<work_id>/<lane>/<slug>"
    fi
    WORK_ID="$2"
    LANE="$3"
    SLUG="$4"
    for part in "$WORK_ID" "$LANE" "$SLUG"; do
      if [ "$part" = "none" ]; then
        fail "branch '$BRANCH' has unset ownership; replace 'none' in agent/<work_id>/<lane>/<slug>"
      fi
    done
    ;;
  *)
    fail "branch '$BRANCH' is blocked for agent work; use agent/<work_id>/<lane>/<slug>"
    ;;
esac

if [ "$ROOT_REAL" = "$PRIMARY_REAL" ]; then
  fail "agent branch '$BRANCH' is checked out in the canonical repo root; use git worktree add outside it"
fi

case "$ROOT_REAL/" in
  "$PRIMARY_REAL"/*)
    fail "agent worktree is inside the canonical repo root; place it outside $PRIMARY_REAL"
    ;;
esac

PROJECT_ID="${FOUNDATION_PROJECT_ID:-}"
if [ -n "$PROJECT_ID" ]; then
  case "$WORK_ID" in
    "$PROJECT_ID"|"$PROJECT_ID"-*) ;;
    *)
      fail "branch work_id '$WORK_ID' must include FOUNDATION_PROJECT_ID '$PROJECT_ID'"
      ;;
  esac

  case "$ROOT_REAL" in
    *"$PROJECT_ID"*) ;;
    *)
      fail "worktree path '$ROOT_REAL' must include FOUNDATION_PROJECT_ID '$PROJECT_ID'"
      ;;
  esac
fi

echo "agent worktree policy: passed ($BRANCH at $ROOT_REAL)"

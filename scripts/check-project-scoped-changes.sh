#!/usr/bin/env sh
set -eu
CDPATH=

fail() {
  echo "project scoped changes: $*" >&2
  exit 2
}

trim() {
  printf '%s' "$1" | awk '{$1=$1; print}'
}

contains_project() {
  wanted="$1"
  list="$2"
  OLD_IFS=$IFS
  IFS=,
  # Intentional comma split for FOUNDATION_ALLOWED_PROJECT_IDS.
  # shellcheck disable=SC2086
  set -- $list
  IFS=$OLD_IFS
  for item in "$@"; do
    item="$(trim "$item")"
    if [ "$item" = "$wanted" ]; then
      return 0
    fi
  done
  return 1
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  fail "not inside a git worktree"
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

PROJECT_SCOPE="${FOUNDATION_PROJECT_SCOPE:-}"
PROJECT_ID="${FOUNDATION_PROJECT_ID:-}"
ALLOWED_PROJECT_IDS="${FOUNDATION_ALLOWED_PROJECT_IDS:-}"
SCOPE_REASON="${FOUNDATION_PROJECT_SCOPE_REASON:-}"

case "$PROJECT_SCOPE" in
  "")
    if [ -z "$PROJECT_ID" ]; then
      echo "project scoped changes: skipped (FOUNDATION_PROJECT_ID not set)"
      exit 0
    fi
    ALLOWED_PROJECT_IDS="$PROJECT_ID"
    ;;
  multi)
    if [ -n "$PROJECT_ID" ]; then
      fail "set either FOUNDATION_PROJECT_ID or FOUNDATION_PROJECT_SCOPE=multi, not both"
    fi
    if [ -z "$(trim "$ALLOWED_PROJECT_IDS")" ]; then
      fail "FOUNDATION_ALLOWED_PROJECT_IDS is required in multi mode"
    fi
    if [ -z "$(trim "$SCOPE_REASON")" ]; then
      fail "FOUNDATION_PROJECT_SCOPE_REASON is required in multi mode"
    fi
    ;;
  *)
    fail "unsupported FOUNDATION_PROJECT_SCOPE '$PROJECT_SCOPE'; use 'multi' or unset"
    ;;
esac

BASE_REF="${FOUNDATION_BASE_REF:-}"
if [ -z "$BASE_REF" ] && git rev-parse --verify --quiet origin/main >/dev/null; then
  BASE_REF="origin/main"
fi

changed_paths="$(
  {
    git diff --name-only
    git diff --cached --name-only
    if [ -n "$BASE_REF" ]; then
      git diff --name-only "$BASE_REF"...HEAD 2>/dev/null || true
    fi
  } | sort -u | sed '/^$/d'
)"

bad_paths=""

printf '%s\n' "$changed_paths" | while IFS= read -r path; do
  [ -n "$path" ] || continue
  case "$path" in
    Plan/README.md|artifact/README.md|artifact/.gitkeep|src/README.md|src/.gitkeep)
      continue
      ;;
    Plan/*|artifact/*|src/*)
      root="${path%%/*}"
      rest="${path#*/}"
      project="${rest%%/*}"

      if [ "$rest" = "$project" ]; then
        printf '%s\n' "$path"
        continue
      fi

      case "$project" in
        ""|active|completed|logs|plans|output|evidence|verification)
          printf '%s\n' "$path"
          continue
          ;;
      esac

      if ! contains_project "$project" "$ALLOWED_PROJECT_IDS"; then
        printf '%s\n' "$path"
        continue
      fi

      case "$root" in
        Plan|artifact|src) ;;
        *)
          printf '%s\n' "$path"
          ;;
      esac
      ;;
  esac
done > "${TMPDIR:-/tmp}/project-scoped-changes.$$"

bad_paths="$(cat "${TMPDIR:-/tmp}/project-scoped-changes.$$")"
rm -f "${TMPDIR:-/tmp}/project-scoped-changes.$$"

if [ -n "$bad_paths" ]; then
  printf 'project scoped changes: blocked paths outside declared project scope:\n%s\n' "$bad_paths" >&2
  exit 2
fi

echo "project scoped changes: passed ($ALLOWED_PROJECT_IDS)"

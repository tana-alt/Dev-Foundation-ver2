#!/usr/bin/env sh
set -eu
CDPATH=

ROOT="${FOUNDATION_REPO_ROOT:-$(cd -- "$(dirname -- "$0")/.." && pwd)}"
STATUS=0

report_block() {
  title="$1"
  body="$2"
  if [ -n "$body" ]; then
    printf '%s\n%s\n' "$title" "$body" >&2
    STATUS=1
  fi
}

tracked_ignored="$(git -C "$ROOT" ls-files -ci --exclude-standard)"
report_block "tracked ignored files:" "$tracked_ignored"

forbidden_tracked=""
for pattern in \
  '.serena/*' \
  'archive/*' \
  'agent_docs_rebuild_scope_ref/*' \
  'Foundation-development/*' \
  'packets/*' \
  'project-orchestration/*' \
  'runtime/*' \
  'source-docs/*'
do
  matches="$(git -C "$ROOT" ls-files "$pattern")"
  if [ -n "$matches" ]; then
    forbidden_tracked="${forbidden_tracked}${matches}
"
  fi
done
report_block "tracked forbidden local or past-source refs:" "$forbidden_tracked"

sensitive_name_tracked="$(
  git -C "$ROOT" ls-files | awk '
    function basename(path) {
      count = split(path, parts, "/")
      return parts[count]
    }
    {
      base = basename($0)
      if ($0 ~ /(^|\/)logs\//) {
        if ($0 !~ /^Plan\/[^\/]+\/logs\/Plan_N[0-9][0-9][0-9][0-9]\.log\.md$/) {
          print $0
        }
      } else if (base == ".env.example") {
        next
      } else if (base ~ /^\.env(\..*)?$/) {
        print $0
      } else if (base ~ /^(\.netrc|\.npmrc|\.pypirc|auth\.json|credentials\.json|cookies\.json|token\.json|id_rsa|id_ed25519)$/) {
        print $0
      } else if (base ~ /\.(pem|key|p12|pfx|sqlite|db)$/) {
        print $0
      } else if (base ~ /^(credentials|secrets|cookies|tokens?|sessions?)\./) {
        print $0
      }
    }
  '
)"
report_block "tracked sensitive-name refs:" "$sensitive_name_tracked"

gitlinks="$(git -C "$ROOT" ls-files -s | awk '$1 == 160000 { print $4 }')"
if [ -n "$gitlinks" ]; then
  if [ ! -f "$ROOT/.gitmodules" ]; then
    report_block "gitlinks without .gitmodules:" "$gitlinks"
  else
    missing=""
    for path in $gitlinks; do
      if ! git -C "$ROOT" config -f .gitmodules --get-regexp 'submodule\..*\.path' \
        | awk '{ print $2 }' | grep -Fx "$path" >/dev/null; then
        missing="${missing}${path}
"
      fi
    done
    report_block "gitlinks missing .gitmodules mapping:" "$missing"
  fi
fi

nested_git_dirs="$(
  find "$ROOT" -path "$ROOT/.git" -prune -o -name .git -print | while IFS= read -r git_dir; do
    parent="${git_dir%/.git}"
    rel="${parent#"$ROOT"/}"
    if git -C "$ROOT" check-ignore -q "$rel/"; then
      continue
    fi
    printf '%s\n' "$rel/.git"
  done
)"
report_block "unignored nested git dirs:" "$nested_git_dirs"

if [ "$STATUS" -eq 0 ]; then
  echo "repo hygiene: passed"
fi

exit "$STATUS"

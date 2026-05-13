#!/usr/bin/env sh
set -eu
CDPATH=

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "secret scan: missing gitleaks; install Gitleaks and rerun" >&2
  exit 127
fi

if git -C "$ROOT" rev-parse --verify HEAD >/dev/null 2>&1; then
  git -C "$ROOT" grep -I -n -e . -- . \
    | gitleaks --config "$ROOT/.gitleaks.toml" --redact --no-banner --log-level warn stdin
  gitleaks git --config "$ROOT/.gitleaks.toml" --redact --no-banner --log-level warn "$ROOT"
else
  git -C "$ROOT" grep --cached -I -n -e . -- . \
    | gitleaks --config "$ROOT/.gitleaks.toml" --redact --no-banner --log-level warn stdin
  echo "secret scan: skipped git history scan (no commits yet)"
fi

echo "secret scan: passed"

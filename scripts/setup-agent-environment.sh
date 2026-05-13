#!/usr/bin/env sh
set -eu
CDPATH=

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
SERENA_TEMPLATE="$ROOT/templates/serena-project.yml"
CODEX_TEMPLATE="$ROOT/templates/codex-config.toml.example"
SERENA_PROJECT="$ROOT/.serena/project.yml"
SERENA_LOCAL="$ROOT/.serena/project.local.yml"
SERENA_CONFIG="$HOME/.serena/serena_config.yml"
CODEX_CONFIG="$HOME/.codex/config.toml"
FORCE="${FORCE:-0}"

mkdir -p "$ROOT/.serena" "$HOME/.codex"

if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$ROOT" config core.hooksPath hooks
  CONFIGURED_CANONICAL_ROOT="$(git -C "$ROOT" config --get foundation.canonicalRoot 2>/dev/null || true)"
  if [ "$FORCE" = "1" ] || [ -z "$CONFIGURED_CANONICAL_ROOT" ] || [ ! -d "$CONFIGURED_CANONICAL_ROOT" ]; then
    git -C "$ROOT" config foundation.canonicalRoot "$ROOT"
    echo "configured foundation.canonicalRoot=$ROOT"
  else
    echo "kept existing foundation.canonicalRoot"
  fi
  echo "configured git hooks path: hooks"
else
  echo "not a git worktree; skipped git hook configuration"
fi

if [ "$FORCE" = "1" ] || [ ! -f "$SERENA_PROJECT" ]; then
  cp "$SERENA_TEMPLATE" "$SERENA_PROJECT"
  echo "wrote $SERENA_PROJECT"
else
  echo "kept existing $SERENA_PROJECT (set FORCE=1 to overwrite)"
fi

if [ ! -f "$SERENA_LOCAL" ]; then
  {
    echo "# Local Serena overrides. Keep this file untracked."
    echo "# Use the same keys as project.yml."
  } > "$SERENA_LOCAL"
  echo "wrote $SERENA_LOCAL"
fi

if [ -f "$SERENA_CONFIG" ]; then
  python3 - "$SERENA_CONFIG" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

def set_yaml_scalar(body: str, key: str, value: str) -> str:
    lines = body.splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            lines[index] = f"{key}: {value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"

text = set_yaml_scalar(text, "web_dashboard", "true")
text = set_yaml_scalar(text, "web_dashboard_open_on_launch", "false")
path.write_text(text, encoding="utf-8")
PY
  echo "ensured Serena dashboard does not open on launch"
else
  echo "missing $SERENA_CONFIG; run Serena init/setup once, then rerun this script"
fi

SERENA_COMMAND=""
if command -v serena >/dev/null 2>&1; then
  SERENA_COMMAND="$(command -v serena)"
elif [ -x "$HOME/.local/bin/serena" ]; then
  SERENA_COMMAND="$HOME/.local/bin/serena"
fi

python3 - "$CODEX_CONFIG" "$CODEX_TEMPLATE" "$SERENA_COMMAND" <<'PY'
from pathlib import Path
import sys

config = Path(sys.argv[1])
template = Path(sys.argv[2])
serena_command = sys.argv[3]

existing = config.read_text(encoding="utf-8") if config.exists() else ""
block = template.read_text(encoding="utf-8")

if serena_command:
    block = block.replace('command = "serena"', f'command = "{serena_command}"')

sections = {
    "[mcp_servers.serena]": block.split("[mcp_servers.context7]")[0].rstrip(),
    "[mcp_servers.context7]": "[mcp_servers.context7]" + block.split("[mcp_servers.context7]", 1)[1].rstrip(),
}

changed = False
for marker, section in sections.items():
    if marker not in existing:
        existing = existing.rstrip() + "\n\n" + section + "\n"
        changed = True

if changed:
    config.write_text(existing.lstrip(), encoding="utf-8")
    print(f"updated {config}")
else:
    print(f"kept existing MCP blocks in {config}")
PY

if command -v npx >/dev/null 2>&1; then
  npx -y @upstash/context7-mcp --version
else
  echo "npx is missing; install Node.js/npm before using Context7 MCP"
fi

if [ -n "$SERENA_COMMAND" ]; then
  "$SERENA_COMMAND" project health-check "$ROOT"
else
  echo "serena is missing; install Serena before running the health check"
fi

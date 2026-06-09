#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CONFIG_PATH="${CODEX_CONFIG:-$HOME/.codex/config.toml}"
APPLY=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --config)
            shift
            CONFIG_PATH="$1"
            ;;
        --apply) APPLY=1 ;;
        --dry-run) APPLY=0 ;;
        *)
            echo "unknown argument: $1" >&2
            exit 64
            ;;
    esac
    shift
done

python3 - "$CONFIG_PATH" "$APPLY" "$ROOT_DIR" <<'PY'
from __future__ import annotations

import shutil
import sys
import time
import tomllib
from pathlib import Path

config_path = Path(sys.argv[1]).expanduser()
apply = sys.argv[2] == "1"
root_dir = Path(sys.argv[3]).resolve()

block = f'''

[mcp_servers."commondb.search"]
startup_timeout_sec = 5
command = "python3"
args = ["{root_dir / "scripts" / "commondb-mcp-dry-run.py"}", "--config", "{config_path}"]
dry_run = true
live_mcp = false
qdrant = "out_of_scope"
'''


def emit(status: str, **fields: str) -> int:
    print(f"status={status}")
    for key, value in fields.items():
        print(f"{key}={value}")
    return 0 if status in {"already_present", "would_append", "appended"} else 1


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    if not path.is_file():
        raise ValueError("config target is not a file")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def is_safe_existing(config: dict) -> bool:
    commondb = config.get("mcp_servers", {}).get("commondb.search")
    if not isinstance(commondb, dict):
        return False
    args = commondb.get("args")
    return (
        commondb.get("dry_run") is True
        and commondb.get("live_mcp") is False
        and commondb.get("qdrant") == "out_of_scope"
        and commondb.get("command") == "python3"
        and isinstance(args, list)
        and any(str(item).endswith("commondb-mcp-dry-run.py") for item in args)
    )


try:
    parsed = load_config(config_path)
except Exception as exc:
    raise SystemExit(emit("blocked", reason=f"config_parse_failed:{exc.__class__.__name__}"))

if is_safe_existing(parsed):
    raise SystemExit(emit("already_present", config=str(config_path), backup="none"))

if parsed.get("mcp_servers", {}).get("commondb.search") is not None:
    raise SystemExit(emit("blocked", reason="existing_commondb_search_block_is_not_dry_run_only"))

if not apply:
    raise SystemExit(emit("would_append", config=str(config_path), backup="none"))

config_path.parent.mkdir(parents=True, exist_ok=True)
backup = "none"
if config_path.exists():
    backup_path = config_path.with_name(f"{config_path.name}.bak-{time.strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(config_path, backup_path)
    backup = str(backup_path)

with config_path.open("a", encoding="utf-8") as handle:
    handle.write(block)

parsed_after = load_config(config_path)
if not is_safe_existing(parsed_after):
    raise SystemExit(emit("blocked", reason="post_append_verification_failed", backup=backup))

raise SystemExit(emit("appended", config=str(config_path), backup=backup))
PY

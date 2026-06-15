#!/usr/bin/env python3
"""PostToolUse hook -- append one TrajectoryEvent per tool call.

Reads the Claude/Codex PostToolUse JSON from stdin, translates it to a
TrajectoryEvent-shaped record, and appends it to
artifact/<project>/trajectory/<session>.jsonl. Non-blocking: always exits 0.
Stdlib-only (the translation lives in workflow_core.hook_events, which must
not import pydantic at module level). Wire under the PostToolUse hook in
.claude/settings.json (Claude) or config.toml [hooks] (Codex).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main() -> int:
    try:
        from workflow_core.hook_events import event_dict_from_post_tool_use
    except ImportError as exc:  # never break the agent loop over environment
        print(f"hook_post_tool_use: import failed, event dropped: {exc}", file=sys.stderr)
        return 0

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    event = event_dict_from_post_tool_use(payload, ts=ts)

    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    out_dir = root / "artifact" / project / "trajectory"
    out_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True)
    with (out_dir / f"{event['run_id']}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

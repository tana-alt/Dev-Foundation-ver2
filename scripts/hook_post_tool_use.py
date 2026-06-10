#!/usr/bin/env python3
"""PostToolUse hook -- append one TrajectoryEvent per tool call.

Reads the Claude/Codex PostToolUse JSON from stdin, translates it to a
TrajectoryEvent, and appends it to artifact/<project>/trajectory/<session>.jsonl.
Non-blocking: always exits 0. Wire under the PostToolUse hook in
.claude/settings.json (Claude) or config.toml [hooks] (Codex).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from datetime import UTC, datetime

    from workflow_core.hook_events import from_post_tool_use

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    event = from_post_tool_use(payload, ts=ts)

    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    out_dir = root / "artifact" / project / "trajectory"
    out_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event.model_dump(), sort_keys=True)
    with (out_dir / f"{event.run_id}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

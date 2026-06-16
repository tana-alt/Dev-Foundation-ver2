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
import subprocess
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
    role = os.environ.get("HARNESS_ROLE") or os.environ.get("FOUNDATION_AGENT_ROLE", "implementer")
    event = event_dict_from_post_tool_use(payload, ts=ts, role=role)

    root = _repo_root()
    project = _project_id(root)
    out_dir = root / "artifact" / project / "trajectory"
    out_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True)
    with (out_dir / f"{event['run_id']}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return 0


def _repo_root() -> Path:
    if value := os.environ.get("FOUNDATION_REPO_ROOT"):
        return Path(value)
    marker_root = _nearest_marker_root(Path.cwd())
    if marker_root is not None:
        return _common_dir_parent(marker_root) or marker_root
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode == 0 and completed.stdout.strip():
        return Path(completed.stdout.strip())
    return Path(__file__).resolve().parents[1]


def _common_dir_parent(root: Path) -> Path | None:
    completed = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    common = Path(completed.stdout.strip())
    if not common.is_absolute():
        common = root / common
    return common.resolve().parent


def _project_id(root: Path) -> str:
    for name in ("FOUNDATION_PROJECT_ID", "FOUNDATION_TASK_ID"):
        if value := os.environ.get(name):
            return value
    for candidate in (Path.cwd(), root):
        task_id = _marker_task_id(candidate)
        if task_id:
            return task_id
    return "default"


def _nearest_marker_root(start: Path) -> Path | None:
    for path in (start, *start.parents):
        if (path / ".harness-worktree.json").is_file():
            return path
    return None


def _marker_task_id(root: Path) -> str | None:
    marker = root / ".harness-worktree.json"
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    task_id = data.get("task_id") if isinstance(data, dict) else None
    return str(task_id) if task_id else None


if __name__ == "__main__":
    raise SystemExit(main())

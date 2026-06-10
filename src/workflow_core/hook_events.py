"""Hook payload -> TrajectoryEvent translator (the observe-mode core).

Claude Code and Codex expose nearly identical hook schemas
(``tool_name`` / ``tool_input`` / ``tool_response`` on PostToolUse), so one pure
translator serves both. This is the cheap real-runtime path: the agent calls the
harness via hooks (inverted control), so no SDK or process driver is needed for
day-to-day completion gating and trajectory recording. Token usage and unattended
eval still require the headless/SDK drive path -- not this module.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from workflow_core.runtime import TrajectoryEvent

_BASH_TOOLS = frozenset({"Bash", "shell"})
_SKILL_TOOLS = frozenset({"Skill", "skill"})


def _target_from_input(tool_name: str, tool_input: dict[str, Any]) -> str:
    for key in ("file_path", "path", "notebook_path"):
        if tool_input.get(key):
            return str(tool_input[key])
    if tool_name in _SKILL_TOOLS:
        return str(tool_input.get("name") or tool_input.get("command") or "")
    if tool_name in _BASH_TOOLS:
        command = str(tool_input.get("command", "")).strip()
        return command.split()[0] if command else ""
    return ""


def _exit_code_from_response(response: object) -> int | None:
    if isinstance(response, dict):
        code = response.get("exit_code")
        if isinstance(code, int):
            return code
        if response.get("is_error") is True:
            return 1
    return None


def from_post_tool_use(
    payload: dict[str, Any],
    *,
    ts: str,
    role: str = "implementer",
) -> TrajectoryEvent:
    """Translate a Claude/Codex PostToolUse payload into a TrajectoryEvent.

    Emitted as ``tool_call`` so eval's tool-call and unexpected-action counting
    apply; the tool's exit code (when present) rides along for failure tracking.
    """
    tool_name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    args_hash = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(tool_input, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
    )
    return TrajectoryEvent(
        ts=ts,
        run_id=str(payload.get("session_id") or "unknown"),
        role=role,
        kind="tool_call",
        tool=tool_name,
        target=_target_from_input(tool_name, tool_input),
        args_hash=args_hash,
        exit_code=_exit_code_from_response(payload.get("tool_response")),
    )

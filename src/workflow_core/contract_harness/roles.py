from __future__ import annotations

import os


class RoleError(RuntimeError):
    pass


_ALLOWED = {
    "writer": {
        "prepare",
        "explain",
        "verify",
        "report",
        "submit",
        "scope-map",
        "spawn",
        "status",
        "tools",
        "context-audit",
        "launch-writer",
        "comm-send",
        "comm-inbox",
    },
    "reviewer": {
        "certify",
        "review:run",
        "review:write-verdict",
        "scope-map",
        "spawn",
        "status",
        "tools",
        "context-audit",
        "comm-send",
        "comm-inbox",
    },
    "integrator": {
        "review:collect",
        "gate",
        "dispatch",
        "integrate",
        "worktree",
        "affected",
        "scope-map",
        "spawn",
        "status",
        "tools",
        "context-audit",
        "launch-writer",
        "land",
        "compose",
        "compose-push",
        "manual-resolution-check",
        "oracle",
        "pr:create",
        "pr:checks",
        "push",
        "comm-send",
        "comm-inbox",
    },
}


def current_role() -> str:
    return os.environ.get("HARNESS_ROLE", "writer")


def require_allowed(command: str, *, action: str | None = None) -> None:
    role = current_role()
    if role == "admin":
        return
    key = f"{command}:{action}" if action else command
    if key not in _ALLOWED.get(role, set()):
        raise RoleError(f"role {role} cannot run {key}")

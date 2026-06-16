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
        "tools",
        "context-audit",
        "launch-writer",
    },
    "reviewer": {
        "review:run",
        "review:write-verdict",
        "scope-map",
        "tools",
        "context-audit",
    },
    "integrator": {
        "review:collect",
        "gate",
        "dispatch",
        "integrate",
        "worktree",
        "affected",
        "scope-map",
        "tools",
        "context-audit",
        "launch-writer",
        "land",
        "push",
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

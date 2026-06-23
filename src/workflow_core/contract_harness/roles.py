from __future__ import annotations

import os


class RoleError(RuntimeError):
    pass


_ALLOWED = {
    "writer": {
        "acp:list",
        "acp:request-action",
        "acp:send",
        "prepare",
        "explain",
        "passport",
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
        "comm-peers",
    },
    "reviewer": {
        "acp:list",
        "acp:request-action",
        "acp:send",
        "certify",
        "passport",
        "review:run",
        "review:write-verdict",
        "scope-map",
        "spawn",
        "status",
        "tools",
        "context-audit",
        "comm-send",
        "comm-inbox",
        "comm-peers",
    },
    "integrator": {
        "acp:list",
        "acp:request-action",
        "acp:send",
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
        "comm-peers",
    },
}

_EXPLICIT_ROLE_REQUIRED = {
    "compose-push",
    "land",
    "pr:create",
    "push",
}


def current_role() -> str:
    return os.environ.get("HARNESS_ROLE", "writer")


def role_context() -> dict[str, object]:
    explicit = "HARNESS_ROLE" in os.environ
    return {
        "current": current_role(),
        "explicit": explicit,
        "source": "HARNESS_ROLE" if explicit else "default",
    }


def require_allowed(command: str, *, action: str | None = None) -> None:
    role = current_role()
    if role == "admin":
        return
    key = f"{command}:{action}" if action else command
    if key in _EXPLICIT_ROLE_REQUIRED and "HARNESS_ROLE" not in os.environ:
        raise RoleError(f"HARNESS_ROLE must be explicit for protected command: {key}")
    if key not in _ALLOWED.get(role, set()):
        raise RoleError(f"role {role} cannot run {key}")

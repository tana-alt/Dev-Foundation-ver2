from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

_REASONS = {"escalation", "not-algorithmically-resolvable"}


def create_issue(
    root: Path,
    task_id: str,
    *,
    reason: str,
    title: str,
    body: str,
    execute: bool = False,
) -> tuple[dict[str, Any], int]:
    if reason not in _REASONS:
        raise ValueError(f"issue reason must be one of: {', '.join(sorted(_REASONS))}")
    if not title.strip():
        raise ValueError("issue title is required")
    if not body.strip():
        raise ValueError("issue body is required")

    command = ["gh", "issue", "create", "--title", title, "--body", body]
    result: dict[str, Any] = {
        "task_id": task_id,
        "status": "protected_external_write",
        "external_write": "github_issue",
        "reason": reason,
        "dry_run": True,
        "requested_execute": execute,
        "command": command,
        "title": title,
    }
    if not execute:
        return result, 0
    role = os.environ.get("HARNESS_ROLE", "")
    if role != "writer":
        result["status"] = "forbidden"
        result["block_reason"] = "issue_create_requires_explicit_writer_role"
        return result, 1

    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    result["dry_run"] = False
    result["returncode"] = completed.returncode
    if completed.stdout.strip():
        result["stdout"] = completed.stdout.strip()
    if completed.stderr.strip():
        result["stderr"] = completed.stderr.strip()
    result["status"] = "created" if completed.returncode == 0 else "failed"
    return result, completed.returncode

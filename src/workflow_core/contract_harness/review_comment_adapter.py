from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ReviewMode = Literal["normal", "arch", "full"]

_COMMANDS: dict[str, ReviewMode] = {
    "/review": "normal",
    "/review arch": "arch",
    "/review full": "full",
}
_SAFE_REF_PART_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class ReviewCommand:
    sha: str
    mode: ReviewMode
    comment_id: str
    actor: str


def parse_review_command(
    body: str,
    *,
    sha: str,
    comment_id: str,
    actor: str,
) -> ReviewCommand | None:
    mode = normalize_review_mode(body)
    if mode is None:
        return None
    return ReviewCommand(
        sha=str(sha),
        mode=mode,
        comment_id=str(comment_id),
        actor=str(actor),
    )


def normalize_review_mode(body: str) -> ReviewMode | None:
    command = body.strip().lower()
    return _COMMANDS.get(command)


def acquire_review_lock(repo: Path, *, sha: str, mode: ReviewMode) -> bool:
    _validate_ref_part(sha, "sha")
    _validate_ref_part(mode, "mode")
    ref = f"refs/harness/locks/{sha}-{mode}"
    completed = subprocess.run(
        ["git", "update-ref", ref, sha, ""],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return completed.returncode == 0


def status_for_exit_code(exit_code: int) -> Literal["success", "failure"]:
    return "success" if exit_code == 0 else "failure"


def _validate_ref_part(value: str, label: str) -> None:
    if not value or not _SAFE_REF_PART_RE.match(value):
        raise ValueError(f"invalid review {label}")

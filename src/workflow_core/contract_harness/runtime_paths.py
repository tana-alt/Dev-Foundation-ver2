from __future__ import annotations

import os
from pathlib import Path

from workflow_core.contract_harness.config import ConfigError
from workflow_core.contract_harness.gitutil import common_dir


def runtime_root(repo: Path) -> Path:
    override = os.environ.get("HARNESS_RUNTIME_ROOT")
    root = Path(override) if override else common_dir(repo) / "harness-runtime"
    _validate_runtime_root(repo, root)
    return root


def task_dir(repo: Path, task_id: str) -> Path:
    return runtime_root(repo) / "state" / "tasks" / task_id


def locks_dir(repo: Path) -> Path:
    return runtime_root(repo) / "locks"


def _validate_runtime_root(repo: Path, root: Path) -> None:
    absolute = root if root.is_absolute() else repo / root
    forbidden = repo / ".harness" / "state"
    try:
        absolute.resolve().relative_to(forbidden.resolve())
    except ValueError:
        return
    raise ConfigError("runtime root must not be under tracked .harness/state")

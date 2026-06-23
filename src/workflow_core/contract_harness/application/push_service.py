from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.push import push_task


def push_candidate(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    return push_task(root, task_id)

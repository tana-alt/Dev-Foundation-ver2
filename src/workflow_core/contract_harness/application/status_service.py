from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.status import task_status


def status_task(root: Path, task_id: str) -> dict[str, Any]:
    return task_status(root, task_id)

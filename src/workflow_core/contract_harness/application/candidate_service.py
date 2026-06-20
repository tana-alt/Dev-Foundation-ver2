from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.submission import submit_task


def submit_candidate(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    return submit_task(root, task_id)

from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.verify import verify_task


def verify_candidate(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    return verify_task(root, task_id)

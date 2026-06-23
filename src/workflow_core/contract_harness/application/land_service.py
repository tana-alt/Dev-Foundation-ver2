from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.land import land_task


def land_candidate(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    return land_task(root, task_id)

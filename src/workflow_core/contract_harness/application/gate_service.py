from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.gate import gate_task


def gate_candidate(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    return gate_task(root, task_id)

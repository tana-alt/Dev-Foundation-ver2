from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness import review


def run_review(root: Path, task_id: str, reviewer_id: str) -> dict[str, Any]:
    return review.run_profile(root, task_id, reviewer_id)

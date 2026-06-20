from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.application.reconcile_service import verify_task_integrity


def reconcile_task(root: Path, task_id: str) -> dict[str, Any]:
    result = verify_task_integrity(root, task_id)
    status = "consistent" if result.get("status") == "pass" else "inconsistent"
    findings = [
        {
            "severity": "error",
            "code": str(reason),
            "message": str(reason),
            "recoverable": False,
            "details": {},
        }
        for reason in result.get("reasons", [])
    ]
    return {
        "schema_version": 1,
        "task_id": task_id,
        "status": status,
        "findings": findings,
        "state_store": result.get("state_store", {}),
        "repaired_event_sha256": None,
    }

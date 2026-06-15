from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.jsonio import write_json

_DIRS = {"incident": "incidents", "rfc": "rfcs", "metric": "metrics"}


def write_report(root: Path, task_id: str, report_type: str) -> dict[str, Any]:
    if report_type not in _DIRS:
        raise ValueError("report type must be incident, rfc, or metric")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    data = {"task_id": task_id, "type": report_type, "created_at": timestamp}
    path = root / ".harness" / "proposals" / _DIRS[report_type] / f"{task_id}-{timestamp}.json"
    write_json(path, data)
    return {"ok": True, "path": str(path.relative_to(root))}

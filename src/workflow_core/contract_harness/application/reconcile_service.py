from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.application.services import state_summary
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json
from workflow_core.contract_harness.runtime_paths import task_dir


def verify_task_integrity(root: Path, task_id: str) -> dict[str, Any]:
    runtime = task_dir(root, task_id)
    reasons: list[str] = []
    manifest_path = runtime / "authority-manifest.json"
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        artifacts = manifest.get("authority_artifacts")
        if isinstance(artifacts, dict):
            for name, raw in artifacts.items():
                if not isinstance(raw, dict):
                    continue
                path = runtime / str(name)
                if not path.is_file():
                    reasons.append(f"missing_{name}")
                    continue
                if raw.get("compatibility_sha256") != file_hash(path):
                    reasons.append(f"hash_mismatch_{name}")
    store = state_summary(root, task_id)
    if store.get("integrity") == "fail":
        reasons.append(f"state_store:{store.get('reason')}")
    return {
        "task_id": task_id,
        "status": "pass" if not reasons else "inconsistent",
        "reasons": reasons,
        "state_store": store,
    }

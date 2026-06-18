from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.runtime_paths import task_dir

READ_ONLY_RESOURCES = (
    "contract.lock.json",
    "verifier-plan.json",
    "candidate.diff",
    "verify-result.json",
    "quality-result.json",
    "scope-map-forward.json",
    "scope-map-reverse.json",
    "submission.json",
    "reviews/*.json",
    "gate-result.json",
    "affected-set.json",
    "land-result.json",
    "oracle-result.json",
    "push-result.json",
    "rework-request.json",
)

WRITE_TOOLS: tuple[str, ...] = ()


def list_resources(root: Path, task_id: str) -> list[dict[str, Any]]:
    runtime = task_dir(root, task_id)
    resources: list[dict[str, Any]] = []
    for pattern in READ_ONLY_RESOURCES:
        matches = sorted(runtime.glob(pattern))
        if matches:
            resources.extend(_resource(runtime, path, present=True) for path in matches)
        else:
            resources.append(
                {
                    "name": pattern,
                    "path": str(runtime / pattern),
                    "present": False,
                    "sha256": None,
                    "readonly": True,
                }
            )
    return resources


def read_resource(root: Path, task_id: str, name: str) -> dict[str, Any]:
    _ensure_allowed(name)
    path = task_dir(root, task_id) / name
    if not path.is_file():
        raise FileNotFoundError(name)
    return {
        "name": name,
        "path": str(path),
        "sha256": file_hash(path),
        "content": path.read_text(encoding="utf-8"),
        "readonly": True,
    }


def exposed_tools() -> tuple[str, ...]:
    return WRITE_TOOLS


def _ensure_allowed(name: str) -> None:
    if name in READ_ONLY_RESOURCES:
        return
    if name.startswith("reviews/") and name.endswith(".json"):
        return
    raise ValueError(f"resource is not exposed by read-only facade: {name}")


def _resource(runtime: Path, path: Path, *, present: bool) -> dict[str, Any]:
    return {
        "name": str(path.relative_to(runtime)).replace("\\", "/"),
        "path": str(path),
        "present": present,
        "sha256": file_hash(path) if present else None,
        "readonly": True,
    }

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from workflow_core.contract_harness.jsonio import read_json, write_json_atomic
from workflow_core.contract_harness.runtime_paths import locks_dir


class LockBlocked(RuntimeError):
    def __init__(self, reason: str, diagnostics: dict[str, str] | None = None) -> None:
        super().__init__(reason)
        self.diagnostics = diagnostics or {}


@contextmanager
def local_lock(
    root: Path,
    name: str,
    *,
    task_id: str,
    target_branch: str,
    base_sha: str,
    timeout_s: int,
) -> Iterator[Path]:
    path = _lock_path(root, name, target_branch)
    path.parent.mkdir(parents=True, exist_ok=True)
    _remove_stale(path, timeout_s)
    payload = {
        "task_id": task_id,
        "target_branch": target_branch,
        "pid": os.getpid(),
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_sha": base_sha,
    }
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}"
    write_json_atomic(tmp, payload)
    try:
        os.link(tmp, path)
    except FileExistsError as exc:
        raise LockBlocked("blocked_by_lock", _lock_diagnostics(path)) from exc
    finally:
        tmp.unlink(missing_ok=True)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def _remove_stale(path: Path, timeout_s: int) -> None:
    if not path.exists():
        return
    try:
        payload = read_json(path)
        created = datetime.strptime(str(payload["created_at"]), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
    except (OSError, ValueError, KeyError):
        return
    age = (datetime.now(UTC) - created).total_seconds()
    if age > timeout_s:
        path.unlink(missing_ok=True)


def _lock_diagnostics(path: Path) -> dict[str, str]:
    diagnostics = {"path": str(path)}
    try:
        payload = read_json(path)
    except OSError as exc:
        return {**diagnostics, "read_status": "unreadable", "error": str(exc)}
    except ValueError as exc:
        return {**diagnostics, "read_status": "invalid_json", "error": str(exc)}
    diagnostics["read_status"] = "readable"
    for key in ("task_id", "target_branch", "pid", "created_at", "base_sha"):
        if key in payload:
            diagnostics[key] = str(payload[key])
    return diagnostics


def _lock_path(root: Path, name: str, target_branch: str) -> Path:
    return locks_dir(root) / f"{_ref_component(name)}-{_ref_component(target_branch)}.lock"


def _ref_component(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    compact = cleaned.strip(".-")[:80] or "ref"
    digest = sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{compact}-{digest}"

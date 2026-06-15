from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from workflow_core.contract_harness.jsonio import read_json, write_json_atomic
from workflow_core.contract_harness.runtime_paths import locks_dir


class LockBlocked(RuntimeError):
    pass


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
    path = locks_dir(root) / f"{name}.lock"
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
        raise LockBlocked("blocked_by_lock") from exc
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

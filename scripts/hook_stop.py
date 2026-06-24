#!/usr/bin/env python3
"""Stop hook -- observational submitted-work dispatch.

On stop, if task-scoped submission evidence exists, delegate reviewer and
integrator processing to the harness. Ordinary reviewer, gate, or merge-preflight
rework is recorded by the harness and must not become a fragile hook-level stop.

Env: FOUNDATION_PROJECT_ID, FOUNDATION_TASK_ID, HARNESS_RUNTIME_ROOT,
FOUNDATION_GATE_TIMEOUT_S (default 900).

Fail-open by design: an environment problem (missing pydantic, hung check)
must never trap the user's session, so those paths log to stderr and exit 0.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

_STRICT_ENFORCEMENT: tuple[str, ...] = ()
_OBSERVATIONAL = (
    "runtime_root_discovery",
    "submission_detection",
    "submitted_dispatch",
    "harness_environment_failure",
)


def hook_responsibilities() -> dict[str, list[str]]:
    """Expose the Stop hook's split between blocking and fail-open paths."""
    return {
        "strict_enforcement": list(_STRICT_ENFORCEMENT),
        "observational": list(_OBSERVATIONAL),
    }


def _timeout_s() -> int:
    raw = os.environ.get("FOUNDATION_GATE_TIMEOUT_S", "900")
    try:
        return int(raw)
    except ValueError:
        print(f"hook_stop: invalid FOUNDATION_GATE_TIMEOUT_S={raw!r}; using 900", file=sys.stderr)
        return 900


def _block_reason(stdout: str) -> str:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return "harness_gate_failed"
    if isinstance(data, dict):
        return str(data.get("reason") or data.get("feedback") or "harness_gate_failed")
    return "harness_gate_failed"


def _runtime_root(root: Path) -> Path | None:
    override = os.environ.get("HARNESS_RUNTIME_ROOT")
    if override:
        return Path(override)
    completed = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        print("hook_stop: no git common dir; submitted dispatch skipped", file=sys.stderr)
        return None
    path = Path(completed.stdout.strip())
    common = path if path.is_absolute() else root / path
    return common / "harness-runtime"


def _repo_root() -> Path:
    if value := os.environ.get("FOUNDATION_REPO_ROOT"):
        return Path(value)
    marker_root = _nearest_marker_root(Path.cwd())
    if marker_root is not None:
        return _common_dir_parent(marker_root) or marker_root
    return Path(__file__).resolve().parents[1]


def _project_id(root: Path) -> str:
    marker_root = _nearest_marker_root(Path.cwd())
    candidates = (marker_root, root) if _marker_belongs_to_root(marker_root, root) else (root,)
    for candidate in candidates:
        task_id = _marker_task_id(candidate)
        if task_id:
            return task_id
    for name in ("FOUNDATION_PROJECT_ID", "FOUNDATION_TASK_ID"):
        if value := os.environ.get(name):
            return value
    return "default"


def _marker_belongs_to_root(marker_root: Path | None, root: Path) -> bool:
    if marker_root is None:
        return False
    if marker_root.resolve() == root.resolve():
        return True
    common_root = _common_dir_parent(marker_root)
    return common_root is not None and common_root.resolve() == root.resolve()


def _nearest_marker_root(start: Path) -> Path | None:
    for path in (start, *start.parents):
        if (path / ".harness-worktree.json").is_file():
            return path
    return None


def _common_dir_parent(root: Path) -> Path | None:
    completed = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    common = Path(completed.stdout.strip())
    if not common.is_absolute():
        common = root / common
    return common.resolve().parent


def _marker_task_id(root: Path) -> str | None:
    marker = root / ".harness-worktree.json"
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    task_id = data.get("task_id") if isinstance(data, dict) else None
    return str(task_id) if task_id else None


def _submitted(root: Path, task_id: str) -> bool:
    runtime = _runtime_root(root)
    if runtime is None:
        return False
    return (runtime / "state" / "tasks" / task_id / "submission.json").is_file()


def _run_harness_dispatch(root: Path, task_id: str) -> int:
    env = {**os.environ, "HARNESS_ROLE": "integrator"}
    try:
        completed = subprocess.run(
            [str(root / "harness"), "dispatch", task_id],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=_timeout_s(),
            env=env,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        _write_dispatch_observation(
            root,
            task_id,
            {
                "status": "skipped",
                "reason": type(exc).__name__,
                "dispatch_returncode": None,
                "error": str(exc),
            },
        )
        print(f"hook_stop: harness gate skipped: {exc}", file=sys.stderr)
        return 0
    if completed.returncode == 0:
        reason = _block_reason(completed.stdout)
    else:
        reason = _block_reason(completed.stdout)
        _write_dispatch_observation(
            root,
            task_id,
            {
                "status": "failed",
                "reason": reason,
                "dispatch_returncode": completed.returncode,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            },
        )
    print(
        json.dumps(
            {
                "decision": "allow",
                "dispatch_returncode": completed.returncode,
                "reason": reason,
            },
            sort_keys=True,
        )
    )
    return 0


def _write_dispatch_observation(root: Path, task_id: str, payload: dict[str, object]) -> None:
    runtime = _runtime_root(root)
    if runtime is None:
        return
    path = runtime / "state" / "tasks" / task_id / "hook-stop-dispatch.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1,
        "task_id": task_id,
        "written_by": "hook_stop",
        **payload,
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _tail(value: str, limit: int = 4096) -> str:
    raw = value.encode("utf-8")
    if len(raw) <= limit:
        return value
    return raw[-limit:].decode("utf-8", errors="replace")


def main() -> int:
    # Drain stdin; respect the loop guard so we never block forever.
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if isinstance(payload, dict) and payload.get("stop_hook_active") is True:
        return 0

    root = _repo_root()
    project = _project_id(root)
    task_id = project
    if not _submitted(root, task_id):
        return 0
    return _run_harness_dispatch(root, task_id)


if __name__ == "__main__":
    raise SystemExit(main())

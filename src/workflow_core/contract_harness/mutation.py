from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.config import mutation_profile
from workflow_core.contract_harness.gitutil import head_sha
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.snapshot import (
    candidate_diff_hash,
    changed_repo_paths,
    snapshot_diff,
)

_MAX_CAPTURED_OUTPUT_CHARS = 4000
_SECRET_VALUE = re.compile(r"(?i)\b(token|password|secret|api[_-]?key)(\s*[:=]\s*)([^\s]+)")


def run_handoff_mutation(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
) -> dict[str, Any] | None:
    profile = mutation_profile(root)
    if profile is None:
        return None
    runtime = task_dir(root, task_id)
    candidate_path = runtime / "candidate.diff"
    output_path = runtime / "mutation-output.json"
    expected_hash = str(verify_result["candidate_diff_sha256"])
    before_head = head_sha(root)
    before_hash = _current_worktree_hash(root, task_id)
    if before_hash != expected_hash or file_hash(candidate_path) != expected_hash:
        raise ValueError("candidate hash mismatch before mutation check")

    start = time.monotonic()
    completed = subprocess.run(
        _command(profile, task_id, runtime, candidate_path, output_path),
        cwd=root,
        capture_output=True,
        text=True,
        timeout=int(profile["timeout_s"]),
        env={
            **os.environ,
            "HARNESS_TASK_ID": task_id,
            "HARNESS_CANDIDATE_DIFF": str(candidate_path),
            "HARNESS_MUTATION_OUTPUT": str(output_path),
        },
    )
    duration_ms = int((time.monotonic() - start) * 1000)
    after_head = head_sha(root)
    after_hash = _current_worktree_hash(root, task_id)
    if after_head != before_head or after_hash != before_hash:
        result = _error_result(
            task_id,
            expected_hash,
            "mutation_command_mutated_candidate",
            completed,
            duration_ms,
        )
        write_json(runtime / "mutation-result.json", result)
        raise ValueError("mutation command mutated candidate")
    if completed.returncode != 0:
        result = _error_result(
            task_id,
            expected_hash,
            "mutation_command_failed",
            completed,
            duration_ms,
        )
        write_json(runtime / "mutation-result.json", result)
        raise ValueError("mutation check failed")

    raw = read_json(output_path) if output_path.is_file() else _json_from_stdout(completed.stdout)
    result = _normalize_result(task_id, expected_hash, raw, duration_ms)
    write_json(runtime / "mutation-result.json", result)
    return result


def mutation_result_hash(root: Path, task_id: str) -> str | None:
    path = task_dir(root, task_id) / "mutation-result.json"
    return file_hash(path) if path.is_file() else None


def _command(
    profile: dict[str, Any],
    task_id: str,
    runtime: Path,
    candidate_path: Path,
    output_path: Path,
) -> list[str]:
    command = [str(item) for item in profile["command"]]
    replacements = {
        "{candidate_diff}": str(candidate_path),
        "{mutation_output}": str(output_path),
        "{task_id}": task_id,
        "{runtime_task_dir}": str(runtime),
    }
    raw = " ".join(command)
    rendered = [_replace(part, replacements) for part in command]
    if "{candidate_diff}" not in raw:
        rendered.append(str(candidate_path))
    if "{mutation_output}" not in raw:
        rendered.append(str(output_path))
    return rendered


def _replace(value: str, replacements: dict[str, str]) -> str:
    for token, replacement in replacements.items():
        value = value.replace(token, replacement)
    return value


def _normalize_result(
    task_id: str,
    candidate_diff_sha256: str,
    raw: dict[str, Any],
    duration_ms: int,
) -> dict[str, Any]:
    survivors = [_normalize_survivor(item) for item in _list(raw.get("survivors"))]
    survivor_count = _survivor_count(raw, survivors)
    status = str(raw.get("status") or ("review_required" if survivor_count else "pass"))
    if status not in {"pass", "review_required"}:
        status = "review_required" if survivor_count else "pass"
    return {
        "task_id": task_id,
        "status": status,
        "candidate_diff_sha256": candidate_diff_sha256,
        "survivor_count": survivor_count,
        "survivors": survivors,
        "duration_ms": duration_ms,
        "written_by": "harness",
    }


def _normalize_survivor(item: object) -> dict[str, Any]:
    if isinstance(item, dict):
        survivor: dict[str, Any] = {}
        for key in ("path", "mutator", "reason"):
            if key in item:
                survivor[key] = str(item[key])
        if "line" in item:
            survivor["line"] = int(item["line"])
        return survivor or {"reason": json.dumps(item, sort_keys=True)}
    return {"reason": str(item)}


def _survivor_count(raw: dict[str, Any], survivors: list[dict[str, Any]]) -> int:
    value = raw.get("survivor_count")
    if isinstance(value, int):
        return value
    return len(survivors)


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _json_from_stdout(stdout: str) -> dict[str, Any]:
    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise ValueError("mutation stdout must be a JSON object")
    return data


def _error_result(
    task_id: str,
    candidate_diff_sha256: str,
    reason: str,
    completed: subprocess.CompletedProcess[str],
    duration_ms: int,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "error",
        "reason": reason,
        "candidate_diff_sha256": candidate_diff_sha256,
        "survivor_count": 0,
        "survivors": [],
        "exit_code": completed.returncode,
        "stdout": _safe_output(completed.stdout),
        "stderr": _safe_output(completed.stderr),
        "duration_ms": duration_ms,
        "written_by": "harness",
    }


def _safe_output(text: str) -> str:
    redacted = _SECRET_VALUE.sub(r"\1\2[REDACTED]", text)
    if len(redacted) <= _MAX_CAPTURED_OUTPUT_CHARS:
        return redacted
    omitted = len(redacted) - _MAX_CAPTURED_OUTPUT_CHARS
    head = redacted[:1000]
    tail = redacted[-3000:]
    return f"{head}\n[truncated {omitted} chars]\n{tail}"


def _current_worktree_hash(root: Path, task_id: str) -> str:
    contract = read_json(task_dir(root, task_id) / "contract.lock.json")
    paths = changed_repo_paths(root, task_id=task_id)
    diff_text = snapshot_diff(root, str(contract["prepared_base_sha"]), paths)
    return candidate_diff_hash(diff_text)

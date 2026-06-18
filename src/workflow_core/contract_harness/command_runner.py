from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_OUTPUT_TAIL_BYTES = 8192


def env_timeout_s(name: str, default: int = 900) -> int:
    return parse_timeout_s(os.environ.get(name), default)


def parse_timeout_s(value: object, default: int = 900) -> int:
    if value in (None, ""):
        return default
    try:
        timeout = int(str(value))
    except (TypeError, ValueError):
        return default
    return timeout if timeout > 0 else default


def run_command(
    command: Sequence[str] | str,
    *,
    cwd: Path,
    timeout_s: int,
    env: Mapping[str, str] | None = None,
    shell: bool = False,
) -> dict[str, Any]:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=dict(env) if env is not None else None,
            shell=shell,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        exit_code = completed.returncode
        timed_out = False
        reason = "ok" if exit_code == 0 else f"exit_{exit_code}"
    except subprocess.TimeoutExpired as exc:
        stdout = _to_text(exc.stdout)
        stderr = _to_text(exc.stderr)
        exit_code = 124
        timed_out = True
        reason = "timeout"
    except FileNotFoundError as exc:
        stdout = ""
        stderr = str(exc)
        exit_code = 127
        timed_out = False
        reason = "command_not_found"
    except OSError as exc:
        stdout = ""
        stderr = str(exc)
        exit_code = 1
        timed_out = False
        reason = "os_error"
    duration_ms = int((time.monotonic() - start) * 1000)
    return {
        "status": "pass" if exit_code == 0 else ("timeout" if timed_out else "fail"),
        "reason": reason,
        "command": _command_value(command),
        "command_display": _command_display(command, shell=shell),
        "cwd": str(cwd),
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "timeout_s": timeout_s,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }


def command_result_artifact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in {"stdout", "stderr"}}


def command_failure_summary(result: Mapping[str, Any]) -> str:
    for key in ("stderr", "stdout", "stderr_tail", "stdout_tail", "reason"):
        value = str(result.get(key) or "").strip()
        if value:
            return value
    return "command_failed"


def _command_value(command: Sequence[str] | str) -> list[str] | str:
    if isinstance(command, str):
        return command
    return [str(part) for part in command]


def _command_display(command: Sequence[str] | str, *, shell: bool) -> str:
    if isinstance(command, str):
        return command
    joined = " ".join(str(part) for part in command)
    return f"sh -c {joined}" if shell else joined


def _tail(value: str) -> str:
    raw = value.encode("utf-8")
    if len(raw) <= _OUTPUT_TAIL_BYTES:
        return value
    return raw[-_OUTPUT_TAIL_BYTES:].decode("utf-8", errors="replace")


def _to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value

"""Environment fingerprint for AB run provenance (Plan-N0002 R13).

Best-effort by design: every field is present, unknowns are the explicit
string "unknown" (macOS exposes no cgroups, containers often hide CPU
governors), and the fingerprint is the sha256 of the canonical JSON so
baseline/candidate environments compare exactly. A fingerprint mismatch is a
warning on the verdict, not a hard stop.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from workflow_core.hashing import canonical_hash, file_sha256

_UNKNOWN = "unknown"
_LOCKFILES = ("uv.lock", "pnpm-lock.yaml", "package-lock.json", "poetry.lock")


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _run(command: list[str]) -> str | None:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _cpu_model() -> str:
    if sys.platform == "darwin":
        return _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or _UNKNOWN
    for line in (_read_text("/proc/cpuinfo") or "").splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", 1)[1].strip()
    return _UNKNOWN


def _cgroup_mem_limit_mb() -> int | str:
    raw = _read_text("/sys/fs/cgroup/memory.max")
    if raw is None or not raw.isdigit():
        return _UNKNOWN
    return int(raw) // (1024 * 1024)


def _os_image() -> str:
    for line in (_read_text("/etc/os-release") or "").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip('"')
    return platform.platform()


def _runtime_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    if shutil.which("node"):
        node = _run(["node", "--version"])
        if node:
            versions["node"] = node.lstrip("v")
    return versions


def _lockfile_hashes(worktree: Path | None) -> dict[str, str]:
    if worktree is None:
        return {}
    hashes: dict[str, str] = {}
    for name in _LOCKFILES:
        path = worktree / name
        if path.is_file():
            hashes[name] = f"sha256:{file_sha256(path)}"
    return hashes


def _virtualized() -> bool | str:
    if Path("/.dockerenv").exists():
        return True
    cgroup = _read_text("/proc/1/cgroup")
    if cgroup is not None:
        return any(marker in cgroup for marker in ("docker", "lxc", "kubepods"))
    return _UNKNOWN


def collect_fingerprint(worktree: Path | None = None) -> dict[str, object]:
    """Collect the R13 fields; lockfile hashes come from the given worktree."""
    governor = _read_text("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    return {
        "cpu_model": _cpu_model(),
        "nproc": os.cpu_count() or 0,
        "cgroup_cpu_quota": _read_text("/sys/fs/cgroup/cpu.max") or _UNKNOWN,
        "cgroup_mem_limit_mb": _cgroup_mem_limit_mb(),
        "kernel": platform.release(),
        "os_image": _os_image(),
        "runtime_versions": _runtime_versions(),
        "lockfile_hashes": _lockfile_hashes(worktree),
        "cpu_governor": governor or _UNKNOWN,
        "virtualized": _virtualized(),
    }


def fingerprint_hash(data: Mapping[str, object]) -> str:
    """sha256 of the canonical JSON form (R13)."""
    return canonical_hash(dict(data))

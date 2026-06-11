"""Plan-record gating -- Plan_N files are the loop switch, not spec.md.

Agents operate plan'd work as ``Plan/<project>/plans/Plan_N000X.md`` records
with ``index.yaml`` carrying per-plan status (see Plan/README.md). The harness
gates the completion loop on that convention: a project is "gated work" when it
has at least one active plan record. ``index.yaml`` is parsed with a minimal
line scanner (no yaml dependency) because hooks run under plain python3.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLAN_FILE = re.compile(r"^Plan_N\d{4,}\.md$")
_PLAN_ID = re.compile(r"^\s*-\s*plan_id:\s*(\S+)")
_STATUS = re.compile(r"^\s*status:\s*(\S+)")


def plan_files(root: Path, project: str) -> list[Path]:
    """All Plan_N records of the project, sorted by plan number."""
    plans_dir = root / "Plan" / project / "plans"
    if not plans_dir.is_dir():
        return []
    return sorted(path for path in plans_dir.iterdir() if _PLAN_FILE.match(path.name))


def active_plan_ids(index_text: str) -> list[str]:
    """Plan ids whose nearest following ``status:`` line says active."""
    active: list[str] = []
    current: str | None = None
    for line in index_text.splitlines():
        id_match = _PLAN_ID.match(line)
        if id_match:
            current = id_match.group(1)
            continue
        status_match = _STATUS.match(line)
        if status_match and current is not None:
            if status_match.group(1) == "active":
                active.append(current)
            current = None
    return active


def plan_gated(root: Path, project: str) -> bool:
    """True when the project carries plan'd (loop-gated) work.

    With an ``index.yaml``, gating requires an active entry whose Plan_N file
    exists; without one, any Plan_N file gates (the index is written by the
    agent and may lag one step behind the first plan file).
    """
    files = plan_files(root, project)
    if not files:
        return False
    index_path = root / "Plan" / project / "index.yaml"
    if not index_path.is_file():
        return True
    names = {path.stem for path in files}
    return any(
        plan_id in names for plan_id in active_plan_ids(index_path.read_text(encoding="utf-8"))
    )

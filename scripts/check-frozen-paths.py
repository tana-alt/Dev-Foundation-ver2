#!/usr/bin/env python3
"""Test-ownership freeze check (report S4).

Blocks a commit whose staged changes touch frozen paths. The freeze list is
declared at spec time in ``Plan/<project>/frozen-paths.txt`` (or ``.frozen-paths``
at the repo root), one glob per line. Inert when no list exists, so wiring it
into pre-commit is safe until a project opts in.

Env: FOUNDATION_PROJECT_ID, FOUNDATION_REPO_ROOT.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from workflow_core.frozen import frozen_path_violations

    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "")

    candidates = []
    if project:
        candidates.append(root / "Plan" / project / "frozen-paths.txt")
    candidates.append(root / ".frozen-paths")
    frozen_file = next((path for path in candidates if path.is_file()), None)
    if frozen_file is None:
        print("frozen-paths check: no frozen list, skipping")
        return 0

    globs = [
        line.strip()
        for line in frozen_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    changed = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=root, capture_output=True, text=True
    ).stdout.split()

    violations = frozen_path_violations(changed, globs)
    if violations:
        print(
            f"frozen-paths check: BLOCKED -- staged changes touch frozen paths: {violations}",
            file=sys.stderr,
        )
        print(f"frozen list: {frozen_file.relative_to(root)}", file=sys.stderr)
        return 2
    print("frozen-paths check: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

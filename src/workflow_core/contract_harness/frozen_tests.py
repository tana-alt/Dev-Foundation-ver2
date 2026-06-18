from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.frozen import frozen_path_violations


def freeze_certified_test_paths(
    root: Path,
    project_id: str,
    certified_tests: list[dict[str, Any]],
) -> dict[str, Any]:
    paths = sorted(
        {
            str(test["path"])
            for test in certified_tests
            if isinstance(test.get("path"), str) and str(test["path"]).strip()
        }
    )
    if not paths:
        raise ValueError("certified tests do not include paths to freeze")
    frozen_file = root / "Plan" / project_id / "frozen-paths.txt"
    frozen_file.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_lines(frozen_file)
    merged = sorted(set(existing) | set(paths))
    frozen_file.write_text("\n".join(merged) + "\n", encoding="utf-8")
    return {
        "project_id": project_id,
        "frozen_file": str(frozen_file),
        "frozen_paths": merged,
        "written_by": "harness",
    }


def certified_test_freeze_violations(
    root: Path,
    project_id: str,
    changed_paths: list[str],
) -> list[str]:
    frozen_file = root / "Plan" / project_id / "frozen-paths.txt"
    return frozen_path_violations(changed_paths, _existing_lines(frozen_file))


def _existing_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

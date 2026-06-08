#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from workflow_core import WorkflowCheckError, check_workflow_document  # noqa: E402


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise WorkflowCheckError(f"{path}: expected a YAML mapping")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Workflow Core state records.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    failures: list[str] = []
    for path in args.paths:
        try:
            check_workflow_document(load_yaml(path))
        except (ValueError, WorkflowCheckError) as exc:
            failures.append(f"{path}: {exc}")

    if failures:
        for failure in failures:
            print(f"error: {failure}", file=sys.stderr)
        return 1

    for path in args.paths:
        print(f"ok: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

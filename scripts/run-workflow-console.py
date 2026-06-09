#!/usr/bin/env python3
"""Render the sanitized workflow console."""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    runpy.run_module("app.workflow_console", run_name="__main__")

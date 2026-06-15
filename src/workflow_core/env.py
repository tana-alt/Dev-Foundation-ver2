"""FOUNDATION_* environment knob parsing shared by scripts and hooks.

Stdlib-only (hooks import this outside the uv venv). A malformed value must
degrade to the default with a stderr warning instead of crashing the tool --
env typos are operator input, not programmer errors.
"""

from __future__ import annotations

import os
import sys


def env_int(name: str, default: int) -> int:
    """Read an integer knob; warn and fall back to the default on bad input."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"warning: {name}={raw!r} is not an integer; using {default}", file=sys.stderr)
        return default


def env_float(name: str, default: float) -> float:
    """Read a float knob; warn and fall back to the default on bad input."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"warning: {name}={raw!r} is not a number; using {default}", file=sys.stderr)
        return default

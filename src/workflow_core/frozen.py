"""Test-ownership freeze (report S4): paths frozen at spec time stay frozen.

If the implementer can edit the acceptance tests, verification is circular. This
pure helper reports which changed paths match a frozen glob; the pre-commit
wiring in ``scripts/check-frozen-paths.py`` blocks the commit when any match.
The freeze list is declared once at spec time, not by the implementer.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence


def frozen_path_violations(
    changed_paths: Sequence[str],
    frozen_globs: Sequence[str],
) -> list[str]:
    violations: list[str] = []
    for path in changed_paths:
        if any(fnmatch.fnmatch(path, glob) for glob in frozen_globs):
            violations.append(path)
    return violations

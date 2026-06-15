#!/usr/bin/env python3
"""SessionStart hook -- replay open harness issues into the agent's context.

Reads artifact/<project>/metrics/open-issues.json (written by `make issues`)
and prints a short summary; the hook's stdout lands in the session context, so
known problems resurface at the start of every session until a fresh
`make measure && make issues` clears them. Non-blocking: silent when there is
nothing to surface, always exits 0.

Env: FOUNDATION_PROJECT_ID, FOUNDATION_REPO_ROOT.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_MAX_SHOWN = 5


def main() -> int:
    sys.stdin.read()  # drain the hook payload; nothing in it changes the output
    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    path = root / "artifact" / project / "metrics" / "open-issues.json"
    if not path.is_file():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    issues = payload.get("issues") or []
    if not isinstance(issues, list) or not issues:
        return 0

    generated_at = payload.get("generated_at", "unknown")
    print(
        f"[harness] {len(issues)} open issue(s) for project '{project}' "
        f"(measured {generated_at}; refresh with `make measure` then `make issues`):"
    )
    for issue in issues[:_MAX_SHOWN]:
        if isinstance(issue, dict):
            print(f"- [{issue.get('kind', '?')}] {issue.get('detail', '')}")
    if len(issues) > _MAX_SHOWN:
        print(f"- ... and {len(issues) - _MAX_SHOWN} more in {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

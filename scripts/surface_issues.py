#!/usr/bin/env python3
"""Surface harness issues from the accumulated eval store.

Reads artifact/<project>/metrics/eval.db (filled by `make measure`), derives
issues -- low run success rate, per-tool/skill failure rates over threshold,
runs acting outside their envelope -- and writes
artifact/<project>/metrics/open-issues.{json,md}. The SessionStart hook
(scripts/hook_session_start.py) replays the result into the agent's context, so
problems keep resurfacing every session until the numbers recover. Run via
`make issues`, manually or on a schedule.

Env: FOUNDATION_PROJECT_ID, FOUNDATION_REPO_ROOT,
FOUNDATION_ISSUE_MIN_CALLS (default 5),
FOUNDATION_ISSUE_FAILURE_RATE (default 0.3),
FOUNDATION_ISSUE_SUCCESS_RATE (default 0.8).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from datetime import UTC, datetime

    from workflow_core.env import env_float, env_int
    from workflow_core.issues import IssueThresholds, derive_issues, render_issues_markdown
    from workflow_core.metrics_store import MetricsStore

    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    db_path = root / "artifact" / project / "metrics" / "eval.db"
    if not db_path.is_file():
        rel = db_path.relative_to(root)
        print(f"surface-issues: no metrics store at {rel}; run `make measure`")
        return 0

    thresholds = IssueThresholds(
        min_calls=env_int("FOUNDATION_ISSUE_MIN_CALLS", 5),
        max_failure_rate=env_float("FOUNDATION_ISSUE_FAILURE_RATE", 0.3),
        min_success_rate=env_float("FOUNDATION_ISSUE_SUCCESS_RATE", 0.8),
    )
    with MetricsStore(db_path) as store:
        issues = derive_issues(store.aggregate_stored(), store.tool_stats(), thresholds)

    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir = db_path.parent
    (out_dir / "open-issues.json").write_text(
        json.dumps(
            {
                "project": project,
                "generated_at": generated_at,
                "thresholds": thresholds.model_dump(),
                "issues": [issue.model_dump() for issue in issues],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    markdown = render_issues_markdown(issues, project=project, generated_at=generated_at)
    (out_dir / "open-issues.md").write_text(markdown, encoding="utf-8")
    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

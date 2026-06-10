#!/usr/bin/env python3
"""Completion gate entrypoint -- the gate owns the completion decision.

Re-derives the verdict from observed facts (required-check exit code + escape
scan) bound to the current diff hash, writes agent-read-only evidence, and exits
non-zero when completion must be blocked. Wire this to a Codex/Claude stop hook
so an agent cannot declare done without a fresh passing gate for its diff.

Env: FOUNDATION_GATE_TIER (default check-required), FOUNDATION_PROJECT_ID
(default "default"), FOUNDATION_REPO_ROOT.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from datetime import UTC, datetime

    from workflow_core.completion import CheckOutcome, run_completion_gate, write_evidence

    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    tier = os.environ.get("FOUNDATION_GATE_TIER", "check-required")
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")

    diff = subprocess.run(["git", "diff", "HEAD"], cwd=root, capture_output=True, text=True).stdout
    diff_hash = "sha256:" + hashlib.sha256(diff.encode("utf-8")).hexdigest()

    completed = subprocess.run(["make", tier], cwd=root)
    check = CheckOutcome(command=f"make {tier}", exit_code=completed.returncode)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    verdict, evidence = run_completion_gate(diff, diff_hash, check, timestamp)
    path = write_evidence(evidence, artifact_dir=root / "artifact" / project / "evidence")
    rel = path.relative_to(root)

    if verdict.passed:
        print(f"completion gate: passed ({evidence.diff_hash})")
        print(f"evidence: {rel}")
        return 0
    print(f"completion gate: BLOCKED -- {verdict.feedback}", file=sys.stderr)
    print(f"evidence: {rel}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

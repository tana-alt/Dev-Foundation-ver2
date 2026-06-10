#!/usr/bin/env python3
"""Stop hook -- the in-session completion loop, spec-gated.

On stop, if the project is spec'd work, re-derive the gate verdict (required
check + escape scan, bound to the diff hash), write agent-read-only evidence,
and on failure emit {"decision":"block","reason":...} so the agent keeps working
in the SAME session. Non-spec work is not gated (single pass), so casual use
stays usable. No SDK or process driver -- the agent calls this via its Stop hook.

Spec presence: a project is "spec'd" when Plan/<project>/spec.md exists or
FOUNDATION_SPEC_PRESENT=1. Env: FOUNDATION_GATE_TIER, FOUNDATION_PROJECT_ID.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def _spec_present(root: Path, project: str) -> bool:
    if os.environ.get("FOUNDATION_SPEC_PRESENT") == "1":
        return True
    return (root / "Plan" / project / "spec.md").is_file()


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from datetime import UTC, datetime

    from workflow_core.completion import CheckOutcome, run_completion_gate, write_evidence

    # Drain stdin; respect the loop guard so we never block forever.
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if isinstance(payload, dict) and payload.get("stop_hook_active") is True:
        return 0

    root = Path(os.environ.get("FOUNDATION_REPO_ROOT", Path(__file__).resolve().parents[1]))
    project = os.environ.get("FOUNDATION_PROJECT_ID", "default")
    if not _spec_present(root, project):
        return 0  # non-spec work: single pass, no loop

    tier = os.environ.get("FOUNDATION_GATE_TIER", "check-required")
    diff = subprocess.run(["git", "diff", "HEAD"], cwd=root, capture_output=True, text=True).stdout
    diff_hash = "sha256:" + hashlib.sha256(diff.encode("utf-8")).hexdigest()
    completed = subprocess.run(["make", tier], cwd=root, capture_output=True, text=True)
    check = CheckOutcome(command=f"make {tier}", exit_code=completed.returncode)
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    verdict, evidence = run_completion_gate(diff, diff_hash, check, ts)
    write_evidence(evidence, artifact_dir=root / "artifact" / project / "evidence")

    if verdict.passed:
        return 0
    print(json.dumps({"decision": "block", "reason": verdict.feedback}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

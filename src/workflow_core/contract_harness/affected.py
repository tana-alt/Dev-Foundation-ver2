from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.contract import load_contract
from workflow_core.contract_harness.gitutil import git
from workflow_core.contract_harness.jsonio import write_json
from workflow_core.contract_harness.paths import paths_from_diff
from workflow_core.contract_harness.policy import integration_target, load_policy
from workflow_core.contract_harness.runtime_paths import task_dir


def classify_affected_set(root: Path, task_id: str) -> dict[str, Any]:
    lock = load_contract(root, task_id)
    base_sha = str(lock["prepared_base_sha"])
    policy = load_policy(root)
    remote, branch, _ = integration_target(policy)
    git(root, ["fetch", remote, branch])
    target_ref = f"refs/remotes/{remote}/{branch}"
    target_sha = git(root, ["rev-parse", target_ref]).stdout.strip()
    candidate_diff = (task_dir(root, task_id) / "candidate.diff").read_text(encoding="utf-8")
    candidate_paths = paths_from_diff(candidate_diff)
    target_paths = _changed_paths(root, base_sha, target_sha)
    overlap = sorted(set(candidate_paths) & set(target_paths))
    if target_sha == base_sha:
        classification = "FAST"
        reason = "target_at_prepared_base"
    elif overlap:
        classification = "REBASE"
        reason = "affected_paths_overlap"
    else:
        classification = "PARTIAL"
        reason = "target_changed_disjoint_paths"
    result = {
        "task_id": task_id,
        "classification": classification,
        "reason": reason,
        "base_sha": base_sha,
        "target_sha": target_sha,
        "remote": remote,
        "branch": branch,
        "candidate_paths": candidate_paths,
        "target_paths": target_paths,
        "overlap": overlap,
    }
    write_json(task_dir(root, task_id) / "affected-set.json", result)
    return result


def _changed_paths(root: Path, base_sha: str, target_sha: str) -> list[str]:
    if base_sha == target_sha:
        return []
    raw = git(root, ["diff", "--name-only", base_sha, target_sha]).stdout
    return sorted(path for path in raw.splitlines() if path)

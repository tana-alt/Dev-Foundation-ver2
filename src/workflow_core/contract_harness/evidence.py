from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.metric_evidence import metric_evidence_hash
from workflow_core.contract_harness.mutation import mutation_result_hash
from workflow_core.contract_harness.quality import quality_result_hash, tool_candidates_hash
from workflow_core.contract_harness.scope_map import scope_map_hash


def artifact_hashes(root: Path, task_id: str) -> dict[str, str | None]:
    return {
        "quality_result_sha256": quality_result_hash(root, task_id),
        "tool_candidates_sha256": tool_candidates_hash(root, task_id),
        "metric_evidence_sha256": metric_evidence_hash(root, task_id),
        "scope_map_reverse_sha256": scope_map_hash(root, task_id, "reverse"),
    }


def machine_artifact_hashes(root: Path, task_id: str) -> dict[str, str | None]:
    hashes = artifact_hashes(root, task_id)
    return {
        "quality_result_sha256": hashes["quality_result_sha256"],
        "tool_candidates_sha256": hashes["tool_candidates_sha256"],
        "scope_map_reverse_sha256": hashes["scope_map_reverse_sha256"],
    }


def reviewer_evidence_seen(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
    *,
    semantic: bool,
) -> dict[str, Any]:
    evidence = {
        "candidate_diff_sha256": verify_result.get("candidate_diff_sha256"),
        "machine_evidence_sha256": verify_result.get("machine_evidence_sha256"),
    }
    if semantic:
        evidence.update(semantic_artifact_hashes(root, task_id))
    return evidence


def semantic_artifact_hashes(root: Path, task_id: str) -> dict[str, str | None]:
    return {
        "mutation_result_sha256": mutation_result_hash(root, task_id),
        **artifact_hashes(root, task_id),
    }

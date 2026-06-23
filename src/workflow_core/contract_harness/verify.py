from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.application.services import (
    candidate_id_from_patch_sha256,
    record_authority_artifact,
)
from workflow_core.contract_harness.architecture_gate import (
    ArchitectureGate,
    architecture_gate_to_json,
    canonical_architecture_gate,
    evaluate_architecture_gate,
)
from workflow_core.contract_harness.contract import (
    ensure_prepared,
    load_verifier_plan,
    semantic_reproducible,
)
from workflow_core.contract_harness.domain.models import ImpactResult, WorkflowPhase
from workflow_core.contract_harness.evidence import machine_artifact_hashes
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import write_json
from workflow_core.contract_harness.quality import (
    quality_gate_verifier,
    tool_candidate_gate_verifier,
    write_quality_artifacts,
)
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.scope_map import write_reverse_scope_map
from workflow_core.contract_harness.snapshot import (
    candidate_diff_hash,
    changed_repo_paths,
    scope_impact,
    scope_violations,
    snapshot_diff,
)
from workflow_core.contract_harness.verifier import all_passed, machine_evidence_hash, run_verifiers


def verify_task(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    lock = ensure_prepared(root, task_id)
    plan = load_verifier_plan(root, task_id)
    paths = changed_repo_paths(root, task_id=task_id)
    diff_text = snapshot_diff(root, str(lock["prepared_base_sha"]), paths)
    out_dir = task_dir(root, task_id)
    (out_dir / "candidate.diff").write_text(diff_text, encoding="utf-8")
    write_reverse_scope_map(root, task_id, diff_text=diff_text)
    impact = scope_impact(paths, lock)
    violations = scope_violations(paths, lock)
    semantic_ok = _semantic_ok(root, task_id, lock)
    architecture_gate = evaluate_architecture_gate(
        root,
        base_sha=str(lock["prepared_base_sha"]),
        diff_text=diff_text,
        changed_paths=paths,
    )
    quality, tool_candidates = write_quality_artifacts(root, task_id, paths, plan)
    verifiers = (
        run_verifiers(root, plan)
        if not violations and semantic_ok and architecture_gate.status != "block"
        else []
    )
    verifiers.extend(
        [quality_gate_verifier(quality), tool_candidate_gate_verifier(tool_candidates)]
    )
    status = "pass" if _passed(violations, semantic_ok, architecture_gate, verifiers) else "fail"
    result = _result(
        root,
        task_id,
        lock,
        diff_text,
        impact,
        violations,
        semantic_ok,
        architecture_gate,
        verifiers,
        status,
    )
    write_json(out_dir / "verify-result.json", result)
    _record_verify_artifacts(root, task_id, result, status)
    return result, 0 if status == "pass" else 1


def _record_verify_artifacts(root: Path, task_id: str, result: dict[str, Any], status: str) -> None:
    record_authority_artifact(
        root,
        task_id,
        "candidate.diff",
        event_type="CANDIDATE_SNAPSHOT",
        to_phase=WorkflowPhase.WRITER_ACTIVE,
        payload={
            "candidate_diff_sha256": result["candidate_diff_sha256"],
            "base_sha": result["base_sha"],
        },
        candidate_id=result["candidate_id"],
        media_type="text/x-diff",
    )
    record_authority_artifact(
        root,
        task_id,
        "verify-result.json",
        event_type="VERIFY",
        to_phase=WorkflowPhase.VERIFIED if status == "pass" else WorkflowPhase.BLOCKED,
        payload={
            "candidate_diff_sha256": result["candidate_diff_sha256"],
            "machine_evidence_sha256": result["machine_evidence_sha256"],
            "status": status,
            "base_sha": result["base_sha"],
        },
        candidate_id=result["candidate_id"],
    )


def recompute_machine_evidence(verify_result: dict[str, Any]) -> str:
    scope_obj = verify_result.get("scope")
    scope: dict[str, Any] = scope_obj if isinstance(scope_obj, dict) else {}
    return machine_evidence_hash(
        task_id=str(verify_result["task_id"]),
        candidate_diff_sha256=str(verify_result["candidate_diff_sha256"]),
        contract_semantic_sha256=str(verify_result["contract_semantic_sha256"]),
        scope_violation_count=int(scope.get("violation_count", 0)),
        architecture_gate=canonical_architecture_gate(verify_result.get("architecture_gate")),
        verifiers=[item for item in verify_result.get("verifiers", []) if isinstance(item, dict)],
    )


def _semantic_ok(root: Path, task_id: str, lock: dict[str, Any]) -> bool:
    try:
        return semantic_reproducible(root, task_id, lock)
    except (OSError, ValueError, KeyError, RuntimeError):
        return False


def _passed(
    violations: list[dict[str, str]],
    semantic_ok: bool,
    architecture_gate: ArchitectureGate,
    verifiers: list[dict[str, Any]],
) -> bool:
    return (
        not violations
        and semantic_ok
        and architecture_gate.status != "block"
        and all_passed(verifiers)
    )


def _result(
    root: Path,
    task_id: str,
    lock: dict[str, Any],
    diff_text: str,
    impact: ImpactResult,
    violations: list[dict[str, str]],
    semantic_ok: bool,
    architecture_gate: ArchitectureGate,
    verifiers: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    candidate_sha = candidate_diff_hash(diff_text)
    result = {
        "schema_version": 1,
        "task_id": task_id,
        "candidate_id": candidate_id_from_patch_sha256(candidate_sha),
        "status": status,
        "base_sha": lock["prepared_base_sha"],
        "candidate_diff_sha256": candidate_sha,
        "contract_lock_sha256": file_hash(task_dir(root, task_id) / "contract.lock.json"),
        "contract_semantic_sha256": lock["contract_semantic_sha256"],
        "scope": {
            "violation_count": len(violations),
            "violations": violations,
            "warning_count": len(
                [finding for finding in impact.findings if finding.severity == "warning"]
            ),
        },
        "impact_result": impact.model_dump(mode="json"),
        "architecture_gate": architecture_gate_to_json(architecture_gate),
        "contract": {"semantic_reproducible": semantic_ok, "unapproved_change": not semantic_ok},
        "verifiers": verifiers,
        **machine_artifact_hashes(root, task_id),
    }
    result["machine_evidence_sha256"] = recompute_machine_evidence(result)
    return result

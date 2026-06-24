from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from workflow_core.contract_harness.application.services import (
    candidate_id_from_patch_sha256,
    record_authority_artifact,
)
from workflow_core.contract_harness.config import ConfigError, review_profile, review_settings
from workflow_core.contract_harness.domain.models import WorkflowPhase
from workflow_core.contract_harness.evidence import reviewer_evidence_seen
from workflow_core.contract_harness.hashing import file_hash, hash_json
from workflow_core.contract_harness.jsonio import read_json, write_json_atomic
from workflow_core.contract_harness.quality import (
    quality_result,
    tool_candidates_result,
)
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.semantic_review import run_command_profile
from workflow_core.contract_harness.verifier import all_passed
from workflow_core.contract_harness.verify import recompute_machine_evidence

_REVIEWER_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def run_profile(
    root: Path,
    task_id: str,
    reviewer_id: str,
    *,
    allow_ai: bool = False,
) -> dict[str, Any]:
    if reviewer_id in {"reader-scope", "reader-impact"}:
        verdict, labels, reason = _reader_scope(root, task_id)
    elif reviewer_id == "reader-correctness":
        verdict, labels, reason = _reader_correctness(root, task_id)
    else:
        profile = review_profile(root, reviewer_id)
        if profile is None or profile.get("kind") != "command":
            raise ConfigError(f"unknown reviewer: {reviewer_id}")
        if _is_ai_reviewer(root, reviewer_id) and not allow_ai:
            raise ConfigError("AI reviewers must be run through review --mode")
        verdict, labels, reason = run_command_profile(root, task_id, reviewer_id, profile)
    return write_verdict(
        root,
        task_id,
        reviewer_id,
        verdict,
        labels=labels,
        reason=reason,
        allow_ai=allow_ai,
    )


def write_verdict(
    root: Path,
    task_id: str,
    reviewer_id: str,
    verdict: str,
    *,
    labels: list[str] | None = None,
    reason: str = "",
    allow_ai: bool = False,
) -> dict[str, Any]:
    _validate_reviewer(root, reviewer_id)
    if _is_ai_reviewer(root, reviewer_id) and not allow_ai:
        raise ConfigError("AI reviewer verdicts must be written through review --mode")
    if verdict not in {"approve", "block"}:
        raise ConfigError("verdict must be approve or block")
    verify_result = _verify_result(root, task_id)
    data = _verdict_payload(
        task_id,
        reviewer_id,
        verdict,
        _expected_evidence(root, task_id, reviewer_id, verify_result),
        labels or [],
        reason,
    )
    write_json_atomic(task_dir(root, task_id) / "reviews" / f"{reviewer_id}.json", data)
    record_authority_artifact(
        root,
        task_id,
        f"reviews/{reviewer_id}.json",
        event_type="REVIEW_VERDICT",
        to_phase=WorkflowPhase.REVIEWED,
        payload={
            "candidate_diff_sha256": verify_result.get("candidate_diff_sha256"),
            "machine_evidence_sha256": verify_result.get("machine_evidence_sha256"),
            "reviewer_id": reviewer_id,
            "verdict": verdict,
        },
        candidate_id=str(data.get("candidate_id") or ""),
    )
    return data


def collect(root: Path, task_id: str, *, mode: str = "default") -> dict[str, Any]:
    settings = review_settings(root, mode=mode)
    verify_result = _verify_result(root, task_id)
    expected = set(settings["reviewers"])
    rows = [_read_verdict(path) for path in _reviews_dir(root, task_id).glob("*.json")]
    valid = [row for row in rows if isinstance(row, dict) and row.get("written_by") == "harness"]
    fresh = [row for row in valid if _known_fresh(root, task_id, row, expected, verify_result)]
    fresh_ai = _fresh_ai_reviews(root, task_id, valid, verify_result) if mode == "default" else []
    unknown = [
        str(row.get("reviewer_id"))
        for row in valid
        if row.get("reviewer_id") not in expected
        and row.get("reviewer_id") not in _ai_reviewer_ids(root)
    ]
    stale = [
        str(row.get("reviewer_id"))
        for row in valid
        if _known_stale(root, task_id, row, expected, verify_result)
    ]
    blocks = [str(row["reviewer_id"]) for row in fresh if row.get("verdict") == "block"]
    blocks.extend(str(row["reviewer_id"]) for row in fresh_ai if row.get("verdict") == "block")
    approves = [row for row in fresh if row.get("verdict") == "approve"]
    semantic_review_satisfied = (
        _normal_mode_satisfied(root, task_id, valid, verify_result) if mode == "default" else None
    )
    return _collect_summary(
        root,
        task_id,
        settings,
        approves,
        fresh_ai,
        blocks,
        stale,
        unknown,
        semantic_review_satisfied=semantic_review_satisfied,
    )


def stale_or_missing(root: Path, task_id: str, *, mode: str = "default") -> list[str]:
    settings = review_settings(root, mode=mode)
    summary = collect(root, task_id, mode=mode)
    fresh = set(summary["fresh_reviewers"])
    return [reviewer for reviewer in settings["reviewers"] if reviewer not in fresh]


def run_mode(root: Path, task_id: str, mode: str) -> dict[str, Any]:
    settings = review_settings(root, mode=mode)
    reviewers = list(settings["reviewers"])
    if not reviewers:
        raise ConfigError(f"no reviewers configured for review mode: {mode}")
    results = []
    for reviewer_id in stale_or_missing(root, task_id, mode=mode):
        results.append(run_profile(root, task_id, reviewer_id, allow_ai=True))
    return {
        "schema_version": 1,
        "task_id": task_id,
        "mode": mode,
        "reviewers": reviewers,
        "runs": results,
        "review": collect(root, task_id, mode=mode),
        "written_by": "harness",
    }


def _reader_scope(root: Path, task_id: str) -> tuple[str, list[str], str]:
    verify_result = _verify_result(root, task_id)
    if not _candidate_hash_ok(root, task_id, verify_result):
        return "block", ["scope_risk"], "candidate hash mismatch"
    impact = _mapping(verify_result.get("impact_result"))
    if impact.get("status") == "blocked":
        return "block", ["scope_risk", "protected_contract_edit"], "forbidden path change"
    scope = _mapping(verify_result.get("scope"))
    if int(scope.get("violation_count", 0)) > 0:
        return "block", ["scope_risk", "protected_contract_edit"], "scope violation"
    return "approve", [], ""


def _reader_correctness(root: Path, task_id: str) -> tuple[str, list[str], str]:
    verify_result = _verify_result(root, task_id)
    if not _candidate_hash_ok(root, task_id, verify_result):
        return "block", ["missing_repro"], "candidate hash mismatch"
    if verify_result.get("machine_evidence_sha256") != recompute_machine_evidence(verify_result):
        return "block", ["missing_repro"], "machine evidence mismatch"
    if verify_result.get("status") != "pass" or not all_passed(
        list(verify_result.get("verifiers", []))
    ):
        return "block", ["machine_failed", "acceptance_gap"], "machine verification failed"
    contract = _mapping(verify_result.get("contract"))
    if contract.get("semantic_reproducible") is not True:
        return "block", ["missing_repro"], "contract semantics changed"
    return "approve", [], ""


def _validate_reviewer(root: Path, reviewer_id: str) -> None:
    if not _REVIEWER_ID.match(reviewer_id):
        raise ConfigError("invalid reviewer_id")
    configured = set(review_settings(root)["reviewers"])
    configured.update(_ai_reviewer_ids(root))
    if "reader-scope" in configured:
        configured.add("reader-impact")
    if "reader-impact" in configured:
        configured.add("reader-scope")
    if reviewer_id not in configured:
        raise ConfigError(f"reviewer is not configured: {reviewer_id}")


def _verdict_payload(
    task_id: str,
    reviewer_id: str,
    verdict: str,
    evidence_seen: dict[str, Any],
    labels: list[str],
    reason: str,
) -> dict[str, Any]:
    written_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema_version": 1,
        "task_id": task_id,
        "candidate_id": candidate_id_from_patch_sha256(str(evidence_seen["candidate_diff_sha256"])),
        "reviewer_id": reviewer_id,
        "verdict": verdict,
        "labels": labels,
        "reason": reason,
        "evidence_seen": evidence_seen,
        "evidence_seen_sha256": hash_json(evidence_seen),
        "written_by": "harness",
        "written_at": written_at,
        "created_at": written_at,
    }


def _verify_result(root: Path, task_id: str) -> dict[str, Any]:
    return read_json(task_dir(root, task_id) / "verify-result.json")


def _candidate_hash_ok(root: Path, task_id: str, verify_result: dict[str, Any]) -> bool:
    path = task_dir(root, task_id) / "candidate.diff"
    return path.is_file() and file_hash(path) == verify_result.get("candidate_diff_sha256")


def _reviews_dir(root: Path, task_id: str) -> Path:
    path = task_dir(root, task_id) / "reviews"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_verdict(path: Path) -> dict[str, Any] | None:
    try:
        return read_json(path)
    except (OSError, ValueError):
        return None


def _known_fresh(
    root: Path,
    task_id: str,
    row: dict[str, Any],
    expected: set[str],
    verify_result: dict[str, Any],
) -> bool:
    return row.get("reviewer_id") in expected and _fresh(root, task_id, row, verify_result)


def _known_stale(
    root: Path,
    task_id: str,
    row: dict[str, Any],
    expected: set[str],
    verify_result: dict[str, Any],
) -> bool:
    return row.get("reviewer_id") in expected and not _fresh(root, task_id, row, verify_result)


def _fresh(
    root: Path,
    task_id: str,
    row: dict[str, Any],
    verify_result: dict[str, Any],
) -> bool:
    evidence = _mapping(row.get("evidence_seen"))
    reviewer_id = str(row.get("reviewer_id", ""))
    expected = _expected_evidence(root, task_id, reviewer_id, verify_result)
    return all(evidence.get(key) == value for key, value in expected.items())


def _expected_evidence(
    root: Path,
    task_id: str,
    reviewer_id: str,
    verify_result: dict[str, Any],
) -> dict[str, Any]:
    return reviewer_evidence_seen(
        root,
        task_id,
        verify_result,
        semantic=_uses_semantic_evidence(root, reviewer_id),
    )


def _uses_semantic_evidence(root: Path, reviewer_id: str) -> bool:
    profile = review_profile(root, reviewer_id)
    return isinstance(profile, dict) and profile.get("kind") == "command"


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _collect_summary(
    root: Path,
    task_id: str,
    settings: dict[str, Any],
    approves: list[dict[str, Any]],
    fresh_ai: list[dict[str, Any]],
    blocks: list[str],
    stale: list[str],
    unknown: list[str],
    semantic_review_satisfied: bool | None,
) -> dict[str, Any]:
    semantic_required = _semantic_review_required(root, task_id)
    semantic_approves = [
        row
        for row in [*approves, *fresh_ai]
        if _satisfies_semantic_review(root, str(row["reviewer_id"]))
        and row.get("verdict") == "approve"
    ]
    semantic_ok = semantic_review_satisfied
    if semantic_ok is None:
        semantic_ok = bool(semantic_approves)
    review_pass = (
        len(approves) >= settings["quorum"]
        and not blocks
        and (not semantic_required or semantic_ok)
    )
    return {
        "task_id": task_id,
        "mode": settings.get("mode", "default"),
        "quorum": settings["quorum"],
        "fresh_approves": len(approves),
        "fresh_blocks": len(blocks),
        "fresh_semantic_approves": len(semantic_approves),
        "semantic_review_required": semantic_required,
        "fresh_reviewers": [str(row["reviewer_id"]) for row in approves] + blocks,
        "stale": sorted(set(stale)),
        "unknown_reviewers": sorted(set(unknown)),
        "blocking_verdicts": blocks,
        "review_pass": review_pass,
    }


def _semantic_review_required(root: Path, task_id: str) -> bool:
    settings = review_settings(root)
    if any(_uses_semantic_evidence(root, str(reviewer)) for reviewer in settings["reviewers"]):
        return True
    quality = quality_result(root, task_id)
    tools = tool_candidates_result(root, task_id)
    return quality.get("status") == "review_required" or tools.get("status") == "review_required"


def _satisfies_semantic_review(root: Path, reviewer_id: str) -> bool:
    profile = review_profile(root, reviewer_id)
    if not isinstance(profile, dict) or profile.get("kind") != "command":
        return False
    return str(profile.get("ai_kind") or "semantic") in {"semantic", "aggressive"}


def _normal_mode_satisfied(
    root: Path,
    task_id: str,
    rows: list[dict[str, Any]],
    verify_result: dict[str, Any],
) -> bool | None:
    settings = review_settings(root, mode="normal")
    expected = set(settings["reviewers"])
    if not expected:
        return None
    fresh = [row for row in rows if _known_fresh(root, task_id, row, expected, verify_result)]
    blocks = [row for row in fresh if row.get("verdict") == "block"]
    approves = [
        row
        for row in fresh
        if row.get("verdict") == "approve"
        and _satisfies_semantic_review(root, str(row.get("reviewer_id") or ""))
    ]
    return len(approves) >= int(settings["quorum"]) and not blocks


def _fresh_ai_reviews(
    root: Path,
    task_id: str,
    rows: list[dict[str, Any]],
    verify_result: dict[str, Any],
) -> list[dict[str, Any]]:
    expected = _ai_reviewer_ids(root)
    return [row for row in rows if _known_fresh(root, task_id, row, expected, verify_result)]


def _ai_reviewer_ids(root: Path) -> set[str]:
    reviewers: set[str] = set()
    for mode in ("normal", "arch", "full"):
        reviewers.update(review_settings(root, mode=mode)["reviewers"])
    return reviewers


def _is_ai_reviewer(root: Path, reviewer_id: str) -> bool:
    if reviewer_id in _ai_reviewer_ids(root):
        return True
    profile = review_profile(root, reviewer_id)
    return isinstance(profile, dict) and "ai_kind" in profile

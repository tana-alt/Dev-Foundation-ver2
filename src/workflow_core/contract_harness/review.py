from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from workflow_core.contract_harness.config import ConfigError, review_profile, review_settings
from workflow_core.contract_harness.evidence import reviewer_evidence_seen
from workflow_core.contract_harness.hashing import file_hash
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


def run_profile(root: Path, task_id: str, reviewer_id: str) -> dict[str, Any]:
    if reviewer_id == "reader-scope":
        verdict, labels, reason = _reader_scope(root, task_id)
    elif reviewer_id == "reader-correctness":
        verdict, labels, reason = _reader_correctness(root, task_id)
    else:
        profile = review_profile(root, reviewer_id)
        if profile is None or profile.get("kind") != "command":
            raise ConfigError(f"unknown reviewer: {reviewer_id}")
        verdict, labels, reason = run_command_profile(root, task_id, reviewer_id, profile)
    return write_verdict(root, task_id, reviewer_id, verdict, labels=labels, reason=reason)


def write_verdict(
    root: Path,
    task_id: str,
    reviewer_id: str,
    verdict: str,
    *,
    labels: list[str] | None = None,
    reason: str = "",
) -> dict[str, Any]:
    _validate_reviewer(root, reviewer_id)
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
    return data


def collect(root: Path, task_id: str) -> dict[str, Any]:
    settings = review_settings(root)
    verify_result = _verify_result(root, task_id)
    expected = set(settings["reviewers"])
    rows = [_read_verdict(path) for path in _reviews_dir(root, task_id).glob("*.json")]
    valid = [row for row in rows if isinstance(row, dict) and row.get("written_by") == "harness"]
    fresh = [row for row in valid if _known_fresh(root, task_id, row, expected, verify_result)]
    unknown = [
        str(row.get("reviewer_id")) for row in valid if row.get("reviewer_id") not in expected
    ]
    stale = [
        str(row.get("reviewer_id"))
        for row in valid
        if _known_stale(root, task_id, row, expected, verify_result)
    ]
    blocks = [str(row["reviewer_id"]) for row in fresh if row.get("verdict") == "block"]
    approves = [row for row in fresh if row.get("verdict") == "approve"]
    return _collect_summary(root, task_id, settings, approves, blocks, stale, unknown)


def stale_or_missing(root: Path, task_id: str) -> list[str]:
    settings = review_settings(root)
    summary = collect(root, task_id)
    fresh = set(summary["fresh_reviewers"])
    return [reviewer for reviewer in settings["reviewers"] if reviewer not in fresh]


def _reader_scope(root: Path, task_id: str) -> tuple[str, list[str], str]:
    verify_result = _verify_result(root, task_id)
    if not _candidate_hash_ok(root, task_id, verify_result):
        return "block", ["scope_risk"], "candidate hash mismatch"
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
    if reviewer_id not in set(review_settings(root)["reviewers"]):
        raise ConfigError(f"reviewer is not configured: {reviewer_id}")


def _verdict_payload(
    task_id: str,
    reviewer_id: str,
    verdict: str,
    evidence_seen: dict[str, Any],
    labels: list[str],
    reason: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "reviewer_id": reviewer_id,
        "verdict": verdict,
        "labels": labels,
        "reason": reason,
        "evidence_seen": evidence_seen,
        "written_by": "harness",
        "written_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    blocks: list[str],
    stale: list[str],
    unknown: list[str],
) -> dict[str, Any]:
    semantic_required = _semantic_review_required(root, task_id)
    semantic_approves = [
        row for row in approves if _uses_semantic_evidence(root, str(row["reviewer_id"]))
    ]
    review_pass = (
        len(approves) >= settings["quorum"]
        and not blocks
        and (not semantic_required or bool(semantic_approves))
    )
    return {
        "task_id": task_id,
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

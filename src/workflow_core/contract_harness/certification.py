from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.config import review_profile
from workflow_core.contract_harness.hashing import file_hash, hash_json
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.runtime_paths import task_dir

_EMPTY_SHA256 = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def write_pass_certificate(
    root: Path,
    task_id: str,
    reviewer_id: str,
    *,
    certified_tests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    verdict = _approved_verdict(root, task_id, reviewer_id)
    subject = build_certificate_subject(
        root,
        task_id,
        reviewer_id,
        certified_tests=certified_tests or verdict.get("certified_tests") or [],
    )
    if subject["mutation_adequacy_status"] == "failed":
        raise ValueError("certified test mutation adequacy failed")
    pass_subject_sha256 = hash_json(subject)
    certificate = {
        "schema_version": 1,
        "task_id": task_id,
        "reviewer_id": reviewer_id,
        "subject": subject,
        "pass_subject_sha256": pass_subject_sha256,
        "written_by": "harness",
    }
    write_json(
        task_dir(root, task_id) / "reviews" / "certificates" / f"{pass_subject_sha256}.json",
        certificate,
    )
    return certificate


def build_certificate_subject(
    root: Path,
    task_id: str,
    reviewer_id: str,
    *,
    certified_tests: list[dict[str, Any]],
) -> dict[str, Any]:
    _validate_certified_tests(certified_tests)
    runtime = task_dir(root, task_id)
    verify_result = read_json(runtime / "verify-result.json")
    contract = read_json(runtime / "contract.lock.json")
    submission = _optional_json(runtime / "submission.json")
    profile = review_profile(root, reviewer_id) or {}
    mutation_adequacy = _mutation_adequacy_status(submission, certified_tests)
    return {
        "task_id": task_id,
        "contract_semantic_sha256": contract["contract_semantic_sha256"],
        "contract_lock_sha256": file_hash(runtime / "contract.lock.json"),
        "prepared_base_sha": contract["prepared_base_sha"],
        "candidate_diff_sha256": verify_result["candidate_diff_sha256"],
        "machine_evidence_sha256": verify_result["machine_evidence_sha256"],
        "scope_contract_sha256": hash_json(contract["scope_contract"]),
        "goal_acceptance_sha256": hash_json(contract["acceptance"]),
        "reviewer_id": reviewer_id,
        "review_profile_sha256": hash_json(profile),
        "certified_tests": certified_tests,
        "mutation_result_sha256": submission.get("mutation_result_sha256"),
        "mutation_adequacy_status": mutation_adequacy,
    }


def validate_pass_certificate(root: Path, task_id: str, certificate: dict[str, Any]) -> bool:
    subject = certificate.get("subject")
    if not isinstance(subject, dict):
        return False
    reviewer_id = str(certificate.get("reviewer_id") or subject.get("reviewer_id") or "")
    certified_tests = subject.get("certified_tests")
    if not isinstance(certified_tests, list):
        return False
    try:
        expected = build_certificate_subject(
            root,
            task_id,
            reviewer_id,
            certified_tests=[item for item in certified_tests if isinstance(item, dict)],
        )
    except (OSError, ValueError, KeyError):
        return False
    return subject == expected and certificate.get("pass_subject_sha256") == hash_json(expected)


def _approved_verdict(root: Path, task_id: str, reviewer_id: str) -> dict[str, Any]:
    verdict = read_json(task_dir(root, task_id) / "reviews" / f"{reviewer_id}.json")
    if verdict.get("written_by") != "harness" or verdict.get("verdict") != "approve":
        raise ValueError("pass certificate requires harness approve verdict")
    return verdict


def _validate_certified_tests(certified_tests: list[dict[str, Any]]) -> None:
    for test in certified_tests:
        content_sha256 = str(test.get("content_sha256") or "")
        if not content_sha256.startswith("sha256:"):
            raise ValueError("certified test requires content_sha256")
        if not test.get("id") or not test.get("kind") or not test.get("runner"):
            raise ValueError("certified test requires id, kind, and runner")
        covers = test.get("covers")
        if content_sha256 == _EMPTY_SHA256 or not isinstance(covers, list) or not covers:
            raise ValueError("trivial certified test fails mutation adequacy")


def _mutation_adequacy_status(
    submission: dict[str, Any],
    certified_tests: list[dict[str, Any]],
) -> str:
    if not certified_tests:
        return "not_configured"
    if submission.get("mutation_result_sha256") is None:
        return "not_configured"
    if int(submission.get("mutation_survivor_count") or 0) > 0:
        return "failed"
    if submission.get("mutation_status") == "pass":
        return "pass"
    return "not_configured"


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return read_json(path)

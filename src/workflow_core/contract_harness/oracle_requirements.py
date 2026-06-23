from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.config import ConfigError, mutation_profile
from workflow_core.contract_harness.contract import load_verifier_plan
from workflow_core.contract_harness.jsonio import read_json
from workflow_core.contract_harness.paths import PathPolicy
from workflow_core.contract_harness.runtime_paths import task_dir

T_UNION_COVERS_BEHAVIORAL_BOUNDARY = "T_UNION_COVERS_BEHAVIORAL_BOUNDARY"
MUTATION_ADEQUACY_COVERS_CHANGED_CODE = "MUTATION_ADEQUACY_COVERS_CHANGED_CODE"

_ADVISORY_REQUIREMENT_MAP = {
    "ROUTING_OR_CONTEXT_BOUNDARY_CHANGED": (
        T_UNION_COVERS_BEHAVIORAL_BOUNDARY,
        MUTATION_ADEQUACY_COVERS_CHANGED_CODE,
    ),
    "HARNESS_ROLE_BOUNDARY_CHANGED": (T_UNION_COVERS_BEHAVIORAL_BOUNDARY,),
    "VERIFICATION_GATE_CHANGED": (
        T_UNION_COVERS_BEHAVIORAL_BOUNDARY,
        MUTATION_ADEQUACY_COVERS_CHANGED_CODE,
    ),
    "REVIEW_FRESHNESS_CHANGED": (T_UNION_COVERS_BEHAVIORAL_BOUNDARY,),
    "POLICY_TOUCH": (T_UNION_COVERS_BEHAVIORAL_BOUNDARY,),
}


def oracle_requirements_for_advisories(
    root: Path,
    advisory_codes: tuple[str, ...],
) -> tuple[str, ...]:
    requirements = {
        requirement
        for code in advisory_codes
        for requirement in _ADVISORY_REQUIREMENT_MAP.get(code, ())
    }
    if not _has_mutation_profile(root):
        requirements.discard(MUTATION_ADEQUACY_COVERS_CHANGED_CODE)
    return tuple(sorted(requirements))


def oracle_requirements_satisfied(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
) -> tuple[bool, list[str]]:
    architecture_gate = verify_result.get("architecture_gate")
    if not isinstance(architecture_gate, dict):
        return False, ["ARCHITECTURE_GATE_SCHEMA_INVALID"]
    requirements = architecture_gate.get("oracle_requirements")
    if not isinstance(requirements, list):
        return False, ["ARCHITECTURE_GATE_SCHEMA_INVALID"]

    unmet: list[str] = []
    for requirement in [str(item) for item in requirements]:
        if requirement == T_UNION_COVERS_BEHAVIORAL_BOUNDARY:
            if not check_t_union_covers_behavioral_boundary(root, task_id, verify_result):
                unmet.append(requirement)
        elif requirement == MUTATION_ADEQUACY_COVERS_CHANGED_CODE:
            if not check_mutation_adequacy_covers_changed_code(root, task_id, verify_result):
                unmet.append(requirement)
        else:
            unmet.append(requirement)
    return not unmet, unmet


def check_t_union_covers_behavioral_boundary(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
) -> bool:
    try:
        plan = load_verifier_plan(root, task_id)
    except (OSError, ValueError, KeyError, ConfigError):
        return False
    statuses = _verifier_statuses(verify_result)
    changed_paths = _changed_paths(verify_result)
    for verifier in plan:
        verifier_id = str(verifier.get("id") or "")
        if statuses.get(verifier_id) != "pass":
            continue
        if bool(verifier.get("always", True)) or _verifier_matches(verifier, changed_paths):
            return True
    return False


def check_mutation_adequacy_covers_changed_code(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
) -> bool:
    path = task_dir(root, task_id) / "mutation-result.json"
    if not path.is_file():
        return False
    try:
        result = read_json(path)
    except (OSError, ValueError):
        return False
    return result.get("status") == "pass" and result.get(
        "candidate_diff_sha256"
    ) == verify_result.get("candidate_diff_sha256")


def _has_mutation_profile(root: Path) -> bool:
    try:
        return mutation_profile(root) is not None
    except (OSError, ValueError, KeyError, ConfigError):
        return False


def _verifier_statuses(verify_result: dict[str, Any]) -> dict[str, str]:
    verifiers = verify_result.get("verifiers")
    if not isinstance(verifiers, list):
        return {}
    return {
        str(item.get("id")): str(item.get("status")) for item in verifiers if isinstance(item, dict)
    }


def _changed_paths(verify_result: dict[str, Any]) -> list[str]:
    impact = verify_result.get("impact_result")
    if not isinstance(impact, dict):
        return []
    changed = impact.get("changed_paths")
    if not isinstance(changed, list):
        return []
    return [str(path) for path in changed]


def _verifier_matches(verifier: dict[str, Any], changed_paths: list[str]) -> bool:
    patterns = [str(pattern) for pattern in verifier.get("applies_to") or []]
    if not patterns:
        return False
    policy = PathPolicy(patterns)
    return any(policy.matches(path) for path in changed_paths)

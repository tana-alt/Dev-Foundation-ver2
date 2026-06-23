from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from workflow_core.contract_harness.architecture_predicates import (
    PredicateFinding,
    run_hard_block_predicates,
)
from workflow_core.contract_harness.oracle_requirements import (
    oracle_requirements_for_advisories,
)

ArchitectureGateStatus = Literal["pass", "advisory", "block"]
ArchitectureSignificance = Literal["none", "local", "significant", "unknown"]

PREDICATE_VERSION = "architecture-gate/v1"
_VALID_STATUSES = {"pass", "advisory", "block"}
_VALID_SIGNIFICANCE = {"none", "local", "significant", "unknown"}


@dataclass(frozen=True)
class ArchitectureGate:
    status: ArchitectureGateStatus
    derived_significance: ArchitectureSignificance
    reason_codes: tuple[str, ...]
    advisory_codes: tuple[str, ...]
    oracle_requirements: tuple[str, ...]
    requires_human_review: bool
    predicate_version: str
    check_kinds: dict[str, str]


def evaluate_architecture_gate(
    root: Path,
    *,
    base_sha: str,
    diff_text: str,
    changed_paths: list[str],
) -> ArchitectureGate:
    try:
        if not isinstance(diff_text, str) or not isinstance(base_sha, str):
            raise TypeError("architecture gate inputs must be strings")
        paths = _normalize_paths(changed_paths)
        findings = run_hard_block_predicates(root, changed_paths=paths, diff_text=diff_text)
        reason_codes = tuple(sorted({finding.code for finding in findings}))
        check_kinds = _check_kinds(findings)
        significance = _derive_significance(paths, reason_codes)
        advisory_codes = (
            () if reason_codes else tuple(sorted(_derive_advisory_codes(paths, significance)))
        )
        oracle_requirements = (
            () if reason_codes else oracle_requirements_for_advisories(root, advisory_codes)
        )
        status = _status(reason_codes, advisory_codes)
        return ArchitectureGate(
            status=status,
            derived_significance=significance,
            reason_codes=reason_codes,
            advisory_codes=advisory_codes,
            oracle_requirements=oracle_requirements,
            requires_human_review=any(item.requires_human_review for item in findings),
            predicate_version=PREDICATE_VERSION,
            check_kinds=check_kinds,
        )
    except Exception:
        return inconclusive_architecture_gate()


def inconclusive_architecture_gate() -> ArchitectureGate:
    return ArchitectureGate(
        status="block",
        derived_significance="unknown",
        reason_codes=("ARCH_PREDICATE_INCONCLUSIVE",),
        advisory_codes=(),
        oracle_requirements=(),
        requires_human_review=True,
        predicate_version=PREDICATE_VERSION,
        check_kinds={"ARCH_PREDICATE_INCONCLUSIVE": "fail_closed"},
    )


def architecture_gate_to_json(gate: ArchitectureGate) -> dict[str, Any]:
    return {
        "status": gate.status,
        "derived_significance": gate.derived_significance,
        "reason_codes": list(gate.reason_codes),
        "advisory_codes": list(gate.advisory_codes),
        "oracle_requirements": list(gate.oracle_requirements),
        "requires_human_review": gate.requires_human_review,
        "predicate_version": gate.predicate_version,
        "check_kinds": dict(sorted(gate.check_kinds.items())),
    }


def architecture_gate_from_json(value: object) -> ArchitectureGate:
    if isinstance(value, ArchitectureGate):
        return value
    if not isinstance(value, dict):
        raise ValueError("architecture_gate must be an object")
    status = str(value.get("status"))
    significance = str(value.get("derived_significance"))
    if status not in _VALID_STATUSES:
        raise ValueError("architecture_gate.status is invalid")
    if significance not in _VALID_SIGNIFICANCE:
        raise ValueError("architecture_gate.derived_significance is invalid")
    predicate_version = str(value.get("predicate_version") or "")
    if predicate_version != PREDICATE_VERSION:
        raise ValueError("architecture_gate.predicate_version is invalid")
    return ArchitectureGate(
        status=_status_literal(status),
        derived_significance=_significance_literal(significance),
        reason_codes=_string_tuple(value.get("reason_codes")),
        advisory_codes=_string_tuple(value.get("advisory_codes")),
        oracle_requirements=_string_tuple(value.get("oracle_requirements")),
        requires_human_review=bool(value.get("requires_human_review", False)),
        predicate_version=predicate_version,
        check_kinds=_string_mapping(value.get("check_kinds")),
    )


def canonical_architecture_gate(value: object) -> dict[str, Any]:
    try:
        gate = architecture_gate_from_json(value)
    except ValueError:
        gate = inconclusive_architecture_gate()
    return {
        "status": gate.status,
        "derived_significance": gate.derived_significance,
        "reason_codes": list(gate.reason_codes),
        "advisory_codes": list(gate.advisory_codes),
        "oracle_requirements": list(gate.oracle_requirements),
        "requires_human_review": gate.requires_human_review,
        "predicate_version": gate.predicate_version,
    }


def _normalize_paths(paths: list[str]) -> list[str]:
    return sorted({str(path).replace("\\", "/").lstrip("/") for path in paths})


def _check_kinds(findings: tuple[PredicateFinding, ...]) -> dict[str, str]:
    return {finding.code: finding.check_kind for finding in findings}


def _status(
    reason_codes: tuple[str, ...],
    advisory_codes: tuple[str, ...],
) -> ArchitectureGateStatus:
    if reason_codes:
        return "block"
    if advisory_codes:
        return "advisory"
    return "pass"


def _derive_significance(
    paths: list[str],
    reason_codes: tuple[str, ...],
) -> ArchitectureSignificance:
    if "ARCH_PREDICATE_INCONCLUSIVE" in reason_codes:
        return "unknown"
    if any(_touches_active_contract(path) or _touches_gate_boundary(path) for path in paths):
        return "significant"
    if any(_touches_harness_runtime(path) or _touches_skill_boundary(path) for path in paths):
        return "local"
    return "none"


def _derive_advisory_codes(paths: list[str], significance: str) -> set[str]:
    codes: set[str] = set()
    if significance == "significant":
        codes.add("POLICY_TOUCH")
    if any(_touches_routing_boundary(path) for path in paths):
        codes.add("ROUTING_OR_CONTEXT_BOUNDARY_CHANGED")
    if any(_touches_role_boundary(path) for path in paths):
        codes.add("HARNESS_ROLE_BOUNDARY_CHANGED")
    if any(_touches_gate_boundary(path) for path in paths):
        codes.add("VERIFICATION_GATE_CHANGED")
    if any(_touches_review_freshness(path) for path in paths):
        codes.add("REVIEW_FRESHNESS_CHANGED")
    return codes


def _touches_active_contract(path: str) -> bool:
    return path in {
        "AGENTS.md",
        "docs/01-agent-operating-contract.md",
        "docs/02-output-verification-contract.md",
        "docs/03-repo-boundary-and-storage-contract.md",
    }


def _touches_gate_boundary(path: str) -> bool:
    return path in {
        "src/workflow_core/contract_harness/architecture_gate.py",
        "src/workflow_core/contract_harness/gate.py",
        "src/workflow_core/contract_harness/merge_oracle.py",
        "src/workflow_core/contract_harness/oracle_requirements.py",
        "src/workflow_core/contract_harness/verifier.py",
        "src/workflow_core/contract_harness/verify.py",
    }


def _touches_harness_runtime(path: str) -> bool:
    return path.startswith("src/workflow_core/contract_harness/")


def _touches_skill_boundary(path: str) -> bool:
    return path.startswith(".agents/skills/")


def _touches_routing_boundary(path: str) -> bool:
    return path in {
        "AGENTS.md",
        ".agents/skills/SKILL_INDEX.md",
        "src/workflow_core/contract_harness/agent_tools.py",
        "src/workflow_core/contract_harness/context_audit.py",
    } or path.startswith(".agents/skills/")


def _touches_role_boundary(path: str) -> bool:
    return path in {
        "src/workflow_core/contract_harness/agent_comm.py",
        "src/workflow_core/contract_harness/agent_tools.py",
        "src/workflow_core/contract_harness/roles.py",
        "src/workflow_core/contract_harness/spawn.py",
    }


def _touches_review_freshness(path: str) -> bool:
    return path in {
        "src/workflow_core/contract_harness/review.py",
        "src/workflow_core/contract_harness/semantic_review.py",
        "src/workflow_core/contract_harness/submission.py",
        "src/workflow_core/contract_harness/verifier.py",
        "src/workflow_core/contract_harness/verify.py",
    }


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _status_literal(value: str) -> ArchitectureGateStatus:
    if value == "pass":
        return "pass"
    if value == "advisory":
        return "advisory"
    return "block"


def _significance_literal(value: str) -> ArchitectureSignificance:
    if value == "none":
        return "none"
    if value == "local":
        return "local"
    if value == "significant":
        return "significant"
    return "unknown"

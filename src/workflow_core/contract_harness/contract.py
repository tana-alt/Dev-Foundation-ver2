from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from workflow_core.contract_harness.acceptance import (
    build_acceptance,
    load_task_policy,
    write_acceptance_rework,
)
from workflow_core.contract_harness.agent_tools import (
    role_agent_tools,
    write_agent_skills,
    write_agent_tools,
)
from workflow_core.contract_harness.application.services import record_authority_artifact
from workflow_core.contract_harness.config import (
    CONFIG_FILES,
    ConfigError,
    harness_dir,
    load_task,
    load_yaml,
    scope_paths,
    verifier_plan,
)
from workflow_core.contract_harness.domain.models import WorkflowPhase
from workflow_core.contract_harness.gitutil import head_sha
from workflow_core.contract_harness.hashing import directory_hash, file_hash, hash_json
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.runtime_paths import task_dir

GLOBAL_FORBIDDEN = [
    "harness-runtime/**",
    ".harness/state/**",
    ".harness/generated/**",
]


def prepare(root: Path, task_id: str) -> dict[str, Any]:
    from workflow_core.contract_harness.scope_map import write_forward_scope_map

    compiled = compile_contract(root, task_id)
    if compiled.get("status") == "rework_required":
        return compiled
    out_dir = task_dir(root, task_id)
    if compiled.get("acceptance_proposal") is not None:
        write_json(out_dir / "acceptance-proposal.json", compiled["acceptance_proposal"])
    write_json(out_dir / "contract.lock.json", compiled["contract"])
    write_json(out_dir / "verifier-plan.json", {"verifiers": compiled["verifier_plan"]})
    write_json(out_dir / "capsule.json", compiled["capsule"])
    write_json(out_dir / "resume-capsule.json", compiled["resume_capsule"])
    write_agent_tools(root, task_id)
    write_agent_skills(root, task_id)
    write_forward_scope_map(root, task_id)
    record_authority_artifact(
        root,
        task_id,
        "contract.lock.json",
        event_type="PREPARE",
        to_phase=WorkflowPhase.PREPARED,
        payload={
            "contract_semantic_sha256": compiled["contract"]["contract_semantic_sha256"],
            "prepared_base_sha": compiled["contract"]["prepared_base_sha"],
        },
    )
    return cast(dict[str, Any], compiled["contract"])


def ensure_prepared(root: Path, task_id: str) -> dict[str, Any]:
    path = task_dir(root, task_id) / "contract.lock.json"
    if path.is_file():
        return read_json(path)
    prepared = prepare(root, task_id)
    if "contract_semantic_sha256" not in prepared:
        raise ConfigError(str(prepared.get("reason") or "prepare failed"))
    return prepared


def load_contract(root: Path, task_id: str) -> dict[str, Any]:
    return read_json(task_dir(root, task_id) / "contract.lock.json")


def load_verifier_plan(root: Path, task_id: str) -> list[dict[str, Any]]:
    path = task_dir(root, task_id) / "verifier-plan.json"
    data = read_json(path)
    plan = data.get("verifiers")
    if not isinstance(plan, list):
        raise ConfigError("verifier-plan.json is malformed")
    return [item for item in plan if isinstance(item, dict)]


def compile_contract(
    root: Path,
    task_id: str,
    *,
    prepared_base_sha: str | None = None,
) -> dict[str, Any]:
    task = load_task(root, task_id)
    configs = {name: load_yaml(harness_dir(root) / name) for name in CONFIG_FILES}
    scope = str(task.get("scope") or "")
    allowed, local_forbidden = scope_paths(configs["owners.yaml"], scope)
    verifiers = verifier_plan(configs["verifiers.yaml"], scope)
    policy = load_task_policy(root, task)
    acceptance, acceptance_proposal = build_acceptance(root, task_id, task, policy, verifiers)
    audit = acceptance.get("audit") if isinstance(acceptance.get("audit"), dict) else None
    if audit is not None and audit.get("status") != "pass":
        if acceptance_proposal is not None:
            write_json(task_dir(root, task_id) / "acceptance-proposal.json", acceptance_proposal)
        return write_acceptance_rework(
            root,
            task_id,
            audit=audit,
            task=task,
            policy=policy,
            acceptance=acceptance,
        )
    contract = _contract_payload(
        root,
        task_id,
        task,
        allowed,
        local_forbidden,
        verifiers,
        policy,
        acceptance,
    )
    contract["prepared_base_sha"] = prepared_base_sha or head_sha(root)
    contract["contract_semantic_sha256"] = semantic_hash(contract)
    return {
        "contract": contract,
        "verifier_plan": verifiers,
        "acceptance_proposal": acceptance_proposal,
        "capsule": _capsule(root, task, contract),
        "resume_capsule": _resume_capsule(root, task, contract),
    }


def semantic_hash(contract: dict[str, Any]) -> str:
    payload = deepcopy(contract)
    payload.pop("prepared_base_sha", None)
    payload.pop("contract_semantic_sha256", None)
    return hash_json(payload)


def semantic_reproducible(root: Path, task_id: str, lock: dict[str, Any]) -> bool:
    compiled = compile_contract(root, task_id, prepared_base_sha=str(lock["prepared_base_sha"]))
    contract = cast(dict[str, Any], compiled["contract"])
    return str(contract["contract_semantic_sha256"]) == str(lock["contract_semantic_sha256"])


def _contract_payload(
    root: Path,
    task_id: str,
    task: dict[str, Any],
    allowed: list[str],
    local_forbidden: list[str],
    verifiers: list[dict[str, Any]],
    policy: dict[str, Any] | None,
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "task_id": task_id,
        "input_hashes": _input_hashes(root, task_id),
        "goal": task.get("goal") or task.get("intent", {}).get("summary"),
        "scope_contract": {
            "allowed_paths": allowed,
            "forbidden_paths": _dedupe([*GLOBAL_FORBIDDEN, *local_forbidden]),
        },
        "verifier_plan": verifiers,
        "acceptance": acceptance,
    }
    if policy is not None:
        payload["policy"] = policy
    return payload


def _input_hashes(root: Path, task_id: str) -> dict[str, str]:
    base = harness_dir(root)
    hashes = {name: file_hash(base / name) for name in CONFIG_FILES}
    hashes["rfc-decisions"] = directory_hash(base / "rfc-decisions")
    hashes["task.yaml"] = file_hash(base / "tasks" / task_id / "task.yaml")
    task = load_yaml(base / "tasks" / task_id / "task.yaml")
    policy_id = str(task.get("policy") or "").strip()
    if policy_id:
        hashes[f"policies/{policy_id}.yaml"] = file_hash(base / "policies" / f"{policy_id}.yaml")
    return hashes


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _capsule(root: Path, task: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": contract["task_id"],
        "scope": task.get("scope"),
        "intent": task.get("intent", {}),
        "scope_contract": contract["scope_contract"],
        "verifier_plan": contract["verifier_plan"],
        "agent_tools": role_agent_tools(root, str(contract["task_id"]), "writer"),
        "contract_semantic_sha256": contract["contract_semantic_sha256"],
    }


def _resume_capsule(root: Path, task: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": contract["task_id"],
        "role": "writer",
        "task_goal": contract.get("goal"),
        "policy": contract.get("policy"),
        "locked_acceptance": contract["acceptance"],
        "current_phase": "prepared",
        "latest_evidence": [],
        "unresolved": None,
        "next_expected_action": "implement verified candidate or request rework",
        "agent_tools": role_agent_tools(root, str(contract["task_id"]), "writer"),
        "contract_semantic_sha256": contract["contract_semantic_sha256"],
        "written_by": "harness",
    }

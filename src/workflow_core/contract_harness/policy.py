from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.config import ConfigError, harness_dir, load_yaml

_WRITE_ACTIONS = {
    "create_rescue_ref",
    "acquire_remote_push_lock",
    "push_landed_commit",
    "release_remote_push_lock",
}


def load_policy(root: Path) -> dict[str, Any]:
    policy = load_yaml(harness_dir(root) / "policy.yaml")
    _reject_task_scope(policy)
    _validate_policy_contract(policy)
    _require_mapping(policy, "goal")
    _require_mapping(policy, "constraints")
    _require_mapping(policy, "bottlenecks")
    return policy


def decide_external_write(
    policy: dict[str, Any],
    *,
    role: str,
    remote: str,
    branch: str,
    action: str,
) -> dict[str, Any]:
    if action not in _WRITE_ACTIONS:
        raise ConfigError(f"unknown external write action: {action}")
    external = _external_writes(policy)
    allowed_roles = [str(item) for item in external.get("allowed_roles") or []]
    branch_policy = _branch_policy(external, remote, branch)
    mode = str(branch_policy.get("mode") or external.get("default_mode") or "dry_run")
    if role not in allowed_roles or mode != "enabled":
        return _blocked(role=role, remote=remote, branch=branch, action=action, mode=mode)
    return {
        "ok": True,
        "status": "allowed",
        "reason": "ok",
        "completed": False,
        "mode": mode,
        "role": role,
        "remote": remote,
        "branch": branch,
        "action": action,
    }


def integration_target(policy: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    external = _external_writes(policy)
    constraints = _require_mapping(policy, "constraints")
    target = constraints.get("integration_target")
    if not isinstance(target, dict):
        raise ConfigError("policy.yaml constraints.integration_target must be a mapping")
    remote = _required_target_text(target, "remote")
    branch = _required_target_text(target, "branch")
    branch_policy = _branch_policy(external, remote, branch)
    return remote, branch, branch_policy


def max_remote_changed_retries(policy: dict[str, Any]) -> int:
    integration = _integration_bottlenecks(policy)
    return int(integration.get("max_remote_changed_retries", 0))


def oracle_timeout_s(policy: dict[str, Any]) -> int:
    integration = _integration_bottlenecks(policy)
    return int(integration.get("oracle_timeout_s", 900))


def _blocked(
    *,
    role: str,
    remote: str,
    branch: str,
    action: str,
    mode: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "reason": "protected_external_write",
        "completed": False,
        "mode": mode,
        "role": role,
        "remote": remote,
        "branch": branch,
        "action": action,
    }


def _external_writes(policy: dict[str, Any]) -> dict[str, Any]:
    constraints = _require_mapping(policy, "constraints")
    value = constraints.get("external_writes")
    if not isinstance(value, dict):
        raise ConfigError("policy.yaml constraints.external_writes must be a mapping")
    return value


def _branch_policy(external: dict[str, Any], remote: str, branch: str) -> dict[str, Any]:
    remotes = external.get("remotes")
    if not isinstance(remotes, dict) or remote not in remotes:
        raise ConfigError(f"policy.yaml does not define remote: {remote}")
    remote_policy = remotes[remote]
    if not isinstance(remote_policy, dict):
        raise ConfigError(f"policy.yaml remote must be a mapping: {remote}")
    branches = remote_policy.get("branches")
    if not isinstance(branches, dict) or branch not in branches:
        raise ConfigError(f"policy.yaml does not define branch: {remote}/{branch}")
    branch_policy = branches[branch]
    if not isinstance(branch_policy, dict):
        raise ConfigError(f"policy.yaml branch must be a mapping: {remote}/{branch}")
    return branch_policy


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"policy.yaml {key} must be a mapping")
    return value


def _integration_bottlenecks(policy: dict[str, Any]) -> dict[str, Any]:
    bottlenecks = _require_mapping(policy, "bottlenecks")
    integration = bottlenecks.get("integration")
    return integration if isinstance(integration, dict) else {}


def _required_target_text(target: dict[str, Any], key: str) -> str:
    value = target.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"policy.yaml constraints.integration_target.{key} must be non-empty")
    return value.strip()


def _reject_task_scope(policy: dict[str, Any]) -> None:
    if "scope" in policy:
        raise ConfigError("policy.yaml must not define task-specific scope")


def _validate_policy_contract(policy: dict[str, Any]) -> None:
    authority = policy.get("authority")
    if isinstance(authority, dict):
        _require_rework_value(
            authority,
            "missing_required_yaml_information",
            "authority.missing_required_yaml_information",
        )

    scope_policy = policy.get("scope_policy")
    if isinstance(scope_policy, dict):
        _require_hard_gate(scope_policy, "allowed_paths", expected=False)
        _require_hard_gate(scope_policy, "forbidden_paths", expected=True)

    task_contract = policy.get("task_contract")
    if isinstance(task_contract, dict):
        _require_rework_value(
            task_contract,
            "missing_required_information_result",
            "task_contract.missing_required_information_result",
        )


def _require_hard_gate(
    scope_policy: dict[str, Any],
    key: str,
    *,
    expected: bool,
) -> None:
    value = scope_policy.get(key)
    if value is None:
        return
    if not isinstance(value, dict):
        raise ConfigError(f"policy.yaml scope_policy.{key} must be a mapping")
    if "hard_gate" in value and bool(value.get("hard_gate")) is not expected:
        expected_text = "true" if expected else "false"
        raise ConfigError(f"policy.yaml scope_policy.{key}.hard_gate must be {expected_text}")


def _require_rework_value(data: dict[str, Any], key: str, label: str) -> None:
    if key in data and str(data.get(key)) != "rework":
        raise ConfigError(f"policy.yaml {label} must be rework")

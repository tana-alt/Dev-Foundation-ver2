from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.config import ConfigError, harness_dir, load_yaml

_SCOPE_KEYS = {"scope", "allowed_paths", "forbidden_paths"}
_WRITE_ACTIONS = {
    "create_rescue_ref",
    "acquire_remote_push_lock",
    "push_landed_commit",
    "release_remote_push_lock",
}


def load_policy(root: Path) -> dict[str, Any]:
    policy = load_yaml(harness_dir(root) / "policy.yaml")
    _reject_scope_keys(policy)
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


def _reject_scope_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in _SCOPE_KEYS:
                raise ConfigError("policy.yaml must not define scope")
            _reject_scope_keys(child)
        return
    if isinstance(value, list):
        for item in value:
            _reject_scope_keys(item)

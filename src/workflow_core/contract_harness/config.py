from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    pass


CONFIG_FILES = ("bottleneck.yaml", "owners.yaml", "verifiers.yaml", "review.yaml")


def harness_dir(root: Path) -> Path:
    return control_root(root) / ".harness"


def control_root(root: Path) -> Path:
    source = _marker_source_root(root)
    if source is not None and (source / ".harness").is_dir():
        return source
    return root


def _marker_source_root(root: Path) -> Path | None:
    marker = root / ".harness-worktree.json"
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    common = data.get("source_repo_common_dir") if isinstance(data, dict) else None
    if not common:
        return None
    return Path(str(common)).resolve().parent


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"missing config: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a mapping")
    return raw


def load_task(root: Path, task_id: str) -> dict[str, Any]:
    task = load_yaml(harness_dir(root) / "tasks" / task_id / "task.yaml")
    if task.get("id") not in (None, task_id):
        raise ConfigError(f"task id mismatch for {task_id}")
    acceptance = task.get("acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("mode") not in {
        "generated",
        "agent_generated",
    }:
        raise ConfigError("acceptance.mode must be generated or agent_generated")
    return task


def scope_paths(owners: dict[str, Any], scope: str) -> tuple[list[str], list[str]]:
    scopes = owners.get("scopes")
    data = scopes.get(scope) if isinstance(scopes, dict) else None
    if data is None:
        data = _lookup_by_scope(owners.get("allowed_paths"), scope)
    allowed, forbidden = _paths_from_scope_data(data)
    if not allowed:
        raise ConfigError(f"unknown scope or no allowed paths: {scope}")
    return allowed, forbidden


def verifier_plan(verifiers: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    plan = _list_of_maps(verifiers.get("default"))
    scoped = verifiers.get("scopes")
    if isinstance(scoped, dict):
        plan.extend(_list_of_maps(scoped.get(scope)))
    if not plan:
        plan = _list_of_maps(verifiers.get("verifiers"))
    normalized = [_normalize_verifier(item) for item in plan]
    if not normalized:
        raise ConfigError(f"no verifier configured for scope: {scope}")
    return normalized


def review_settings(root: Path) -> dict[str, Any]:
    raw = load_yaml(harness_dir(root) / "review.yaml")
    default_obj = raw.get("default")
    metrics_obj = raw.get("metrics")
    default: dict[str, Any] = default_obj if isinstance(default_obj, dict) else {}
    metrics: dict[str, Any] = metrics_obj if isinstance(metrics_obj, dict) else {}
    reviewers = default.get("reviewers") or ["reader-correctness", "reader-scope"]
    return {
        "quorum": _positive_int(default.get("quorum", 2), "review.quorum"),
        "reviewers": [str(item) for item in reviewers],
        "background_auto_run": bool(default.get("background_auto_run", True)),
        "blocking_labels": list(default.get("blocking_labels") or []),
        "reject_unexpected_actions": bool(metrics.get("reject_unexpected_actions", False)),
    }


def review_profile(root: Path, reviewer_id: str) -> dict[str, Any] | None:
    raw = load_yaml(harness_dir(root) / "review.yaml")
    profiles_obj = raw.get("profiles")
    profiles = profiles_obj if isinstance(profiles_obj, dict) else {}
    profile = profiles.get(reviewer_id)
    return profile if isinstance(profile, dict) else None


def mutation_profile(root: Path) -> dict[str, Any] | None:
    raw = load_yaml(harness_dir(root) / "review.yaml")
    mutation_obj = raw.get("mutation")
    if not isinstance(mutation_obj, dict) or mutation_obj.get("enabled", True) is False:
        return None
    command_obj = mutation_obj.get("command")
    if command_obj is None:
        return None
    if isinstance(command_obj, str):
        command = [command_obj]
    elif isinstance(command_obj, list) and command_obj:
        command = [str(item) for item in command_obj]
    else:
        raise ConfigError("mutation.command must be a non-empty string or list")
    return {
        "command": command,
        "timeout_s": int(mutation_obj.get("timeout_s", 900)),
    }


def _lookup_by_scope(value: object, scope: str) -> object:
    if isinstance(value, dict):
        return value.get(scope)
    return value


def _paths_from_scope_data(data: object) -> tuple[list[str], list[str]]:
    if isinstance(data, list):
        return [str(item) for item in data], []
    if not isinstance(data, dict):
        return [], []
    allowed = [str(item) for item in data.get("allowed_paths") or []]
    forbidden = [str(item) for item in data.get("forbidden_paths") or []]
    return allowed, forbidden


def _list_of_maps(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _normalize_verifier(item: dict[str, Any]) -> dict[str, Any]:
    if not item.get("id") or not item.get("command"):
        raise ConfigError("verifier entries require id and command")
    normalized = {
        "id": str(item["id"]),
        "command": str(item["command"]),
        "applies_to": list(item.get("applies_to") or ["**/*"]),
        "always": bool(item.get("always", True)),
    }
    if "timeout_s" in item:
        normalized["timeout_s"] = _positive_int(item["timeout_s"], "verifier.timeout_s")
    return normalized


def _positive_int(value: object, field: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ConfigError(f"{field} must be a positive integer")
    return parsed

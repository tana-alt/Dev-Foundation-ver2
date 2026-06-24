from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    pass


CONFIG_FILES = (
    "bottleneck.yaml",
    "owners.yaml",
    "policy.yaml",
    "verifiers.yaml",
    "review.yaml",
)
REVIEW_MODES = {"normal", "arch", "full"}


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


def task_path(root: Path, task_id: str) -> Path:
    base = harness_dir(root)
    legacy = base / "tasks" / task_id / "task.yaml"
    if legacy.is_file():
        return legacy
    matches = sorted(
        path
        for path in base.glob(f"*/tasks/{task_id}/task.yaml")
        if path.parts[-4] not in {"state", "generated"}
    )
    if len(matches) > 1:
        choices = ", ".join(str(path.relative_to(control_root(root))) for path in matches)
        raise ConfigError(f"task id is ambiguous across harness projects: {task_id}: {choices}")
    if matches:
        return matches[0]
    return legacy


def task_config_dir(root: Path, task_id: str) -> Path:
    path = task_path(root, task_id)
    if path.parent.parent.name == "tasks":
        return path.parent.parent.parent
    return harness_dir(root)


def config_path(root: Path, task_id: str, name: str) -> Path:
    project_dir = task_config_dir(root, task_id)
    if project_dir != harness_dir(root):
        candidate = project_dir / name
        if candidate.is_file():
            return candidate
    return harness_dir(root) / name


def task_relative_path(root: Path, task_id: str) -> str:
    return str(task_path(root, task_id).relative_to(control_root(root)))


def load_task(root: Path, task_id: str) -> dict[str, Any]:
    task = load_yaml(task_path(root, task_id))
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


def review_settings(root: Path, mode: str = "default") -> dict[str, Any]:
    raw = load_yaml(harness_dir(root) / "review.yaml")
    default_obj = _review_mode_mapping(raw, mode)
    metrics_obj = raw.get("metrics")
    default: dict[str, Any] = default_obj if isinstance(default_obj, dict) else {}
    metrics: dict[str, Any] = metrics_obj if isinstance(metrics_obj, dict) else {}
    fallback = ["reader-correctness", "reader-scope"] if mode == "default" else []
    reviewers = default.get("reviewers") or fallback
    return {
        "mode": mode,
        "quorum": _positive_int(default.get("quorum", 2), "review.quorum"),
        "reviewers": [str(item) for item in reviewers],
        "background_auto_run": bool(default.get("background_auto_run", mode == "default")),
        "blocking_labels": list(default.get("blocking_labels") or []),
        "reject_unexpected_actions": bool(metrics.get("reject_unexpected_actions", False)),
    }


def review_mode_names(root: Path) -> list[str]:
    raw = load_yaml(harness_dir(root) / "review.yaml")
    modes = raw.get("modes")
    if not isinstance(modes, dict):
        return []
    return [str(name) for name in modes if str(name) in REVIEW_MODES]


def configured_ai_reviewers(root: Path) -> set[str]:
    reviewers: set[str] = set()
    for mode in review_mode_names(root):
        reviewers.update(review_settings(root, mode=mode)["reviewers"])
    return reviewers


def review_profile(root: Path, reviewer_id: str) -> dict[str, Any] | None:
    raw = load_yaml(harness_dir(root) / "review.yaml")
    profiles_obj = raw.get("profiles")
    profiles = profiles_obj if isinstance(profiles_obj, dict) else {}
    profile = profiles.get(reviewer_id)
    return profile if isinstance(profile, dict) else None


def _review_mode_mapping(raw: dict[str, Any], mode: str) -> object:
    if mode == "default":
        return raw.get("default")
    if mode not in REVIEW_MODES:
        raise ConfigError(f"unknown review mode: {mode}")
    modes = raw.get("modes")
    if not isinstance(modes, dict):
        return {}
    return modes.get(mode)


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
    command = _normalize_command(item["command"], "verifier.command")
    normalized: dict[str, Any] = {
        "id": str(item["id"]),
        "command": command,
        "applies_to": list(item.get("applies_to") or ["**/*"]),
        "always": bool(item.get("always", True)),
        "shell": _normalize_shell(item.get("shell"), command),
    }
    if "timeout_s" in item:
        normalized["timeout_s"] = _positive_int(item["timeout_s"], "verifier.timeout_s")
    return normalized


def _normalize_command(value: object, field: str) -> str | list[str]:
    if isinstance(value, str):
        if not value.strip():
            raise ConfigError(f"{field} must be a non-empty string or list")
        return value
    if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
        return [str(item) for item in value]
    raise ConfigError(f"{field} must be a non-empty string or list")


def _normalize_shell(value: object, command: str | list[str]) -> bool:
    if value is not None:
        return bool(value)
    return isinstance(command, str)


def _positive_int(value: object, field: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ConfigError(f"{field} must be a positive integer")
    return parsed

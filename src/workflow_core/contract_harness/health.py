from __future__ import annotations

import shlex
import shutil
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.config import (
    ConfigError,
    config_path,
    load_task,
    load_yaml,
    review_mode_names,
    review_profile,
    review_settings,
    scope_paths,
    verifier_plan,
)

_REPO_PATH_PREFIXES = (
    ".harness/",
    "Plan/",
    "docs/",
    "scripts/",
    "src/",
    "templates/",
    "tests/",
)
_BUILT_IN_REVIEWERS = {"reader-correctness", "reader-scope"}


def config_health(root: Path, task_id: str) -> dict[str, Any]:
    missing_paths: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    review: dict[str, Any] = {}
    try:
        task = load_task(root, task_id)
        scope = str(task.get("scope") or "")
        _check_scope_paths(root, task_id, scope, missing_paths)
        _check_verifiers(root, task_id, scope, missing_paths)
        review = _review_health(root, warnings, missing_paths)
    except ConfigError as exc:
        warnings.append({"source": "config", "reason": str(exc)})
    status = "pass" if not missing_paths and not warnings else "warn"
    return {
        "status": status,
        "missing_paths": missing_paths,
        "warnings": warnings,
        "review": review,
    }


def _check_scope_paths(
    root: Path,
    task_id: str,
    scope: str,
    missing_paths: list[dict[str, str]],
) -> None:
    owners = load_yaml(config_path(root, task_id, "owners.yaml"))
    allowed, _forbidden = scope_paths(owners, scope)
    for path in allowed:
        _append_missing(root, missing_paths, "owners.yaml allowed_paths", path)


def _check_verifiers(
    root: Path,
    task_id: str,
    scope: str,
    missing_paths: list[dict[str, str]],
) -> None:
    verifiers = verifier_plan(load_yaml(config_path(root, task_id, "verifiers.yaml")), scope)
    for verifier in verifiers:
        verifier_id = str(verifier.get("id") or "unknown")
        for path in list(verifier.get("applies_to") or []):
            _append_missing(
                root,
                missing_paths,
                f"verifier {verifier_id} applies_to",
                str(path),
            )
        for path in _command_paths(str(verifier.get("command") or "")):
            _append_missing(
                root,
                missing_paths,
                f"verifier {verifier_id} command",
                path,
            )


def _review_health(
    root: Path,
    warnings: list[dict[str, str]],
    missing_paths: list[dict[str, str]],
) -> dict[str, Any]:
    settings = review_settings(root)
    reviewers = [str(reviewer) for reviewer in settings["reviewers"]]
    quorum = int(settings["quorum"])
    _check_review_settings(
        settings,
        reviewers,
        quorum,
        warnings,
        source="review",
        warn_manual=True,
    )
    mode_settings = {mode: review_settings(root, mode=mode) for mode in review_mode_names(root)}
    all_reviewers = set(reviewers)
    for mode, mode_config in mode_settings.items():
        mode_reviewers = [str(reviewer) for reviewer in mode_config["reviewers"]]
        all_reviewers.update(mode_reviewers)
        _check_review_settings(
            mode_config,
            mode_reviewers,
            int(mode_config["quorum"]),
            warnings,
            source=f"review.modes.{mode}",
            warn_manual=False,
        )
    for reviewer_id in sorted(all_reviewers):
        _check_reviewer_profile(root, reviewer_id, warnings, missing_paths)
    return {
        "background_auto_run": bool(settings["background_auto_run"]),
        "modes": {
            mode: {
                "quorum": mode_config["quorum"],
                "reviewers": mode_config["reviewers"],
            }
            for mode, mode_config in mode_settings.items()
        },
        "quorum": quorum,
        "reviewers": reviewers,
    }


def _check_review_settings(
    settings: dict[str, Any],
    reviewers: list[str],
    quorum: int,
    warnings: list[dict[str, str]],
    *,
    source: str,
    warn_manual: bool,
) -> None:
    if quorum > len(reviewers):
        warnings.append(
            {
                "source": f"{source}.quorum",
                "reason": f"quorum {quorum} exceeds reviewer count {len(reviewers)}",
            }
        )
    if warn_manual and settings["background_auto_run"] is False:
        warnings.append(
            {
                "source": f"{source}.background_auto_run",
                "reason": "manual reviewer runs required",
            }
        )


def _check_reviewer_profile(
    root: Path,
    reviewer_id: str,
    warnings: list[dict[str, str]],
    missing_paths: list[dict[str, str]],
) -> None:
    profile = review_profile(root, reviewer_id)
    if profile is None and reviewer_id not in _BUILT_IN_REVIEWERS:
        warnings.append(
            {
                "source": f"reviewer {reviewer_id}",
                "reason": "unknown reviewer profile",
            }
        )
        return
    if not isinstance(profile, dict) or profile.get("kind") != "command":
        return
    command = profile.get("command")
    if not isinstance(command, list) or not command:
        warnings.append(
            {
                "source": f"reviewer {reviewer_id} command",
                "reason": "missing command",
            }
        )
        return
    rendered = [_render_review_token(root, str(part)) for part in command]
    executable = rendered[0]
    if "/" not in executable and shutil.which(executable) is None:
        warnings.append(
            {
                "source": f"reviewer {reviewer_id} command",
                "reason": f"executable not found: {executable}",
            }
        )
    for path in _command_paths(rendered):
        _append_missing(root, missing_paths, f"reviewer {reviewer_id} command", path)


def _render_review_token(root: Path, value: str) -> str:
    return value.replace("{repo_root}", str(root))


def _command_paths(command: str | list[str]) -> list[str]:
    tokens = command if isinstance(command, list) else _split_command(command)
    paths: list[str] = []
    for token in tokens:
        normalized = _path_token(str(token))
        if normalized is not None:
            paths.append(normalized)
    return paths


def _split_command(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return []


def _path_token(token: str) -> str | None:
    if "{" in token or "}" in token:
        return None
    if token.startswith(tuple(_REPO_PATH_PREFIXES)):
        return token
    suffixes = (".py", ".yaml", ".yml", ".json", ".md", ".txt")
    if token.startswith("./") and token[2:].startswith(tuple(_REPO_PATH_PREFIXES)):
        return token[2:]
    if token.endswith(suffixes) and "/" in token and not token.startswith("-"):
        return token
    return None


def _append_missing(
    root: Path,
    missing_paths: list[dict[str, str]],
    source: str,
    path: str,
) -> None:
    if _path_exists(root, path):
        return
    row = {"source": source, "path": path}
    if row not in missing_paths:
        missing_paths.append(row)


def _path_exists(root: Path, pattern: str) -> bool:
    if any(char in pattern for char in "*?["):
        return any(root.glob(pattern))
    path = Path(pattern)
    if path.is_absolute():
        return path.exists()
    return (root / pattern).exists()

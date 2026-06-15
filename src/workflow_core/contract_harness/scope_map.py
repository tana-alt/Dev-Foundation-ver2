from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.contract import ensure_prepared, load_contract
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.paths import PathPolicy, paths_from_diff
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.snapshot import changed_repo_paths, snapshot_diff


def write_forward_scope_map(root: Path, task_id: str) -> dict[str, Any]:
    data = build_forward_scope_map(root, task_id)
    write_json(task_dir(root, task_id) / "scope-map-forward.json", data)
    return data


def write_reverse_scope_map(
    root: Path, task_id: str, *, diff_text: str | None = None
) -> dict[str, Any]:
    data = build_reverse_scope_map(root, task_id, diff_text=diff_text)
    write_json(task_dir(root, task_id) / "scope-map-reverse.json", data)
    return data


def build_forward_scope_map(root: Path, task_id: str) -> dict[str, Any]:
    lock = ensure_prepared(root, task_id)
    scope = _mapping(lock.get("scope_contract"))
    verifiers = [item for item in lock.get("verifier_plan", []) if isinstance(item, dict)]
    path_hints = [str(item) for item in scope.get("allowed_paths", [])]
    return {
        "task_id": task_id,
        "direction": "forward",
        "hard_constraint": False,
        "path_hints": path_hints,
        "forbidden_path_hints": [str(item) for item in scope.get("forbidden_paths", [])],
        "verifier_hints": [_verifier_hint(item) for item in verifiers],
        "likely_tests": _tests_for_patterns(root, path_hints),
        "confidence": "low" if not path_hints else "medium",
        "limitations": [
            "Static path and verifier map only.",
            "Writer may expand implementation scope when the task requires it.",
            "Actual implementation scope is observed later from candidate diff.",
        ],
        "generated_from": {
            "contract_semantic_sha256": lock.get("contract_semantic_sha256"),
            "prepared_base_sha": lock.get("prepared_base_sha"),
        },
    }


def build_reverse_scope_map(
    root: Path, task_id: str, *, diff_text: str | None = None
) -> dict[str, Any]:
    lock = (
        load_contract(root, task_id)
        if (task_dir(root, task_id) / "contract.lock.json").is_file()
        else ensure_prepared(root, task_id)
    )
    diff, source = _reverse_diff(root, task_id, lock, diff_text)
    changed_paths = paths_from_diff(diff)
    verifiers = [item for item in lock.get("verifier_plan", []) if isinstance(item, dict)]
    return {
        "task_id": task_id,
        "direction": "reverse",
        "hard_constraint": False,
        "observed_scope": {
            "source": source,
            "changed_paths": changed_paths,
        },
        "likely_affected": {
            "verifiers": _matching_verifier_ids(changed_paths, verifiers),
            "tests": _tests_for_changed_paths(root, changed_paths),
            "review_topics": _review_topics(changed_paths),
        },
        "confidence": "low" if not changed_paths else "medium",
        "limitations": [
            "Static diff impact map only.",
            "This map is review evidence, not a complete dependency graph.",
            "Do not treat map absence or omission as proof of no impact.",
        ],
        "generated_from": {
            "candidate_diff_sha256": _maybe_candidate_hash(root, task_id),
            "contract_semantic_sha256": lock.get("contract_semantic_sha256"),
            "prepared_base_sha": lock.get("prepared_base_sha"),
        },
    }


def scope_map_hash(root: Path, task_id: str, direction: str) -> str | None:
    path = _scope_map_path(root, task_id, direction)
    if not path.is_file():
        return None
    return file_hash(path)


def scope_map_result(root: Path, task_id: str, direction: str) -> dict[str, Any]:
    path = _scope_map_path(root, task_id, direction)
    if not path.is_file():
        return {"task_id": task_id, "direction": direction, "status": "absent"}
    return read_json(path)


def _scope_map_path(root: Path, task_id: str, direction: str) -> Path:
    if direction not in {"forward", "reverse"}:
        raise ValueError("scope map direction must be forward or reverse")
    return task_dir(root, task_id) / f"scope-map-{direction}.json"


def _reverse_diff(
    root: Path,
    task_id: str,
    lock: dict[str, Any],
    diff_text: str | None,
) -> tuple[str, str]:
    if diff_text is not None:
        return diff_text, "candidate.diff"
    candidate = task_dir(root, task_id) / "candidate.diff"
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8"), "candidate.diff"
    paths = changed_repo_paths(root, task_id=task_id)
    return snapshot_diff(root, str(lock["prepared_base_sha"]), paths), "working_tree"


def _maybe_candidate_hash(root: Path, task_id: str) -> str | None:
    candidate = task_dir(root, task_id) / "candidate.diff"
    return file_hash(candidate) if candidate.is_file() else None


def _verifier_hint(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id", "")),
        "applies_to": [str(value) for value in item.get("applies_to", [])],
        "always": bool(item.get("always", False)),
    }


def _matching_verifier_ids(changed_paths: list[str], verifiers: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for verifier in verifiers:
        verifier_id = str(verifier.get("id", ""))
        if not verifier_id:
            continue
        patterns = [str(value) for value in verifier.get("applies_to", [])]
        if bool(verifier.get("always", False)) or _matches_any(changed_paths, patterns):
            ids.append(verifier_id)
    return ids


def _matches_any(paths: list[str], patterns: list[str]) -> bool:
    if not paths:
        return False
    policy = PathPolicy(patterns or ["**/*"])
    return any(policy.matches(path) for path in paths)


def _tests_for_patterns(root: Path, patterns: list[str]) -> list[str]:
    if not (root / "tests").is_dir():
        return []
    candidates = _repo_tests(root)
    if not patterns:
        return candidates[:10]
    policy = PathPolicy(patterns)
    direct = [path for path in candidates if policy.matches(path)]
    return direct[:10]


def _tests_for_changed_paths(root: Path, changed_paths: list[str]) -> list[str]:
    candidates = _repo_tests(root)
    if not candidates:
        return []
    selected: set[str] = set()
    for changed in changed_paths:
        path = Path(changed)
        if changed.startswith("tests/"):
            selected.add(changed)
            continue
        if changed.startswith("src/workflow_core/contract_harness/"):
            _add_if_exists(root, selected, "tests/workflow_core/test_contract_harness.py")
        stem = path.stem
        if stem:
            for test in candidates:
                test_stem = Path(test).stem
                if test_stem in {f"test_{stem}", f"{stem}_test"} or stem in test_stem:
                    selected.add(test)
    return sorted(selected)[:10]


def _repo_tests(root: Path) -> list[str]:
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return []
    return [
        str(path.relative_to(root)).replace("\\", "/")
        for path in sorted(tests_dir.rglob("test*.py"))
        if path.is_file()
    ]


def _add_if_exists(root: Path, selected: set[str], rel_path: str) -> None:
    if (root / rel_path).is_file():
        selected.add(rel_path)


def _review_topics(changed_paths: list[str]) -> list[str]:
    topics = {_review_topic(path) for path in changed_paths}
    return sorted(topics)


def _review_topic(path: str) -> str:
    if path.startswith(".harness/"):
        return "harness contract or policy behavior"
    if path.startswith("src/workflow_core/contract_harness/"):
        return "contract harness runtime behavior"
    if path.startswith("src/"):
        return "source behavior"
    if path.startswith("tests/"):
        return "test coverage"
    if path.startswith("scripts/"):
        return "tool durability and reuse"
    if path.startswith("docs/"):
        return "documented operating contract"
    return "changed path impact"


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

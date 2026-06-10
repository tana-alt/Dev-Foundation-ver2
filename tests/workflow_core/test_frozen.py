from __future__ import annotations

from workflow_core.frozen import frozen_path_violations

FROZEN = ["tests/test_feature.py", "tests/acceptance/*.py", "spec/*.yaml"]


def test_flags_exact_and_glob_matches() -> None:
    changed = [
        "src/feature/core.py",
        "tests/test_feature.py",
        "tests/acceptance/test_login.py",
        "spec/login.yaml",
    ]
    violations = frozen_path_violations(changed, FROZEN)
    assert violations == [
        "tests/test_feature.py",
        "tests/acceptance/test_login.py",
        "spec/login.yaml",
    ]


def test_no_violation_when_changes_avoid_frozen() -> None:
    assert frozen_path_violations(["src/feature/core.py", "README.md"], FROZEN) == []


def test_empty_inputs() -> None:
    assert frozen_path_violations([], FROZEN) == []
    assert frozen_path_violations(["tests/test_feature.py"], []) == []

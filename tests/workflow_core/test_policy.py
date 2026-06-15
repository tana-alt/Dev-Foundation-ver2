from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow_core.policy import (
    PolicyError,
    allowed_policy_dir,
    condition_for_metric,
    load_policy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

POLICY = {
    "policy_version": 1,
    "conditions": [
        {"tool": "check", "metric": "overall", "require": "pass"},
        {
            "tool": "verdict",
            "metric": "bench.core.wall_ms",
            "mode": "non_regression",
            "threshold_pct": 5.0,
        },
    ],
    "on_inconclusive": "retry_then_fail",
    "max_retries": 2,
}


def write_policy(directory: Path, name: str = "p.json", text: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text if text is not None else json.dumps(POLICY), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# load_policy
# ---------------------------------------------------------------------------


def test_load_policy_roundtrip(tmp_path: Path) -> None:
    path = write_policy(tmp_path / "policies")
    policy, policy_hash = load_policy(path, allowed_dir=tmp_path / "policies")
    assert policy.policy_version == 1
    assert policy.max_retries == 2
    assert policy.on_inconclusive == "retry_then_fail"
    assert len(policy.conditions) == 2
    assert len(policy_hash) == 64


def test_policy_hash_ignores_formatting(tmp_path: Path) -> None:
    compact = write_policy(tmp_path / "policies", "a.json", json.dumps(POLICY))
    pretty = write_policy(tmp_path / "policies", "b.json", json.dumps(POLICY, indent=4))
    _, hash_a = load_policy(compact, allowed_dir=tmp_path / "policies")
    _, hash_b = load_policy(pretty, allowed_dir=tmp_path / "policies")
    assert hash_a == hash_b


def test_policy_outside_allowed_dir_rejected(tmp_path: Path) -> None:
    path = write_policy(tmp_path / "elsewhere")
    with pytest.raises(PolicyError, match="outside the allowed policy dir"):
        load_policy(path, allowed_dir=tmp_path / "policies")


def test_policy_bad_json_rejected(tmp_path: Path) -> None:
    path = write_policy(tmp_path / "policies", text="{not json")
    with pytest.raises(PolicyError, match="cannot load"):
        load_policy(path, allowed_dir=tmp_path / "policies")


def test_policy_unknown_field_rejected(tmp_path: Path) -> None:
    bad = {**POLICY, "threshold_pct": 5.0}
    path = write_policy(tmp_path / "policies", text=json.dumps(bad))
    with pytest.raises(PolicyError, match="invalid policy"):
        load_policy(path, allowed_dir=tmp_path / "policies")


# ---------------------------------------------------------------------------
# condition_for_metric / allowed_policy_dir
# ---------------------------------------------------------------------------


def test_condition_for_metric_skips_check_conditions(tmp_path: Path) -> None:
    path = write_policy(tmp_path / "policies")
    policy, _ = load_policy(path, allowed_dir=tmp_path / "policies")
    condition = condition_for_metric(policy, "bench.core.wall_ms")
    assert condition is not None
    assert condition.mode == "non_regression"
    assert condition_for_metric(policy, "overall") is None
    assert condition_for_metric(policy, "missing.metric") is None


def test_allowed_policy_dir_default_and_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FOUNDATION_POLICY_DIR", raising=False)
    assert allowed_policy_dir(tmp_path) == tmp_path / ".agents" / "policies"
    monkeypatch.setenv("FOUNDATION_POLICY_DIR", str(tmp_path / "ro"))
    assert allowed_policy_dir(tmp_path) == tmp_path / "ro"

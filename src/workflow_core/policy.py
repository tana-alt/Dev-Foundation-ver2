"""Quality-gate policy loading and anti-gaming guards (Plan-N0002 R5/R12).

Thresholds live only in policy files; verdict and gate take no threshold CLI
flag. Policies must resolve inside the allowed directory
(``FOUNDATION_POLICY_DIR``, default ``<root>/.agents/policies``) — in a
hardened deployment that env var points at a read-only mount outside the
agent's write area, so the measured code cannot edit its own thresholds.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from workflow_core.contracts import StrictModel
from workflow_core.hashing import canonical_hash
from workflow_core.verdict import Mode

OnInconclusive = Literal["retry_then_fail", "fail", "pass_with_warning"]


class PolicyError(ValueError):
    """Policy unusable: bad location, bad JSON, or bad shape (tool error)."""


class PolicyCondition(StrictModel):
    tool: str
    metric: str
    require: str | None = None
    mode: Mode | None = None
    threshold_pct: float | None = None
    statistic: str = "median"


class Policy(StrictModel):
    policy_version: int
    conditions: list[PolicyCondition]
    on_inconclusive: OnInconclusive = "fail"
    max_retries: int = 0


def allowed_policy_dir(root: Path) -> Path:
    raw = os.environ.get("FOUNDATION_POLICY_DIR", "")
    return Path(raw) if raw.strip() else root / ".agents" / "policies"


def load_policy(path: Path, *, allowed_dir: Path) -> tuple[Policy, str]:
    """Load and validate a policy; returns (policy, policy_hash)."""
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed_dir.resolve()):
        raise PolicyError(
            f"policy {resolved} is outside the allowed policy dir {allowed_dir} (R12)"
        )
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"cannot load policy {resolved}: {exc}") from exc
    try:
        policy = Policy.model_validate(data)
    except ValidationError as exc:
        raise PolicyError(f"invalid policy {resolved}: {exc}") from exc
    return policy, canonical_hash(data)


def condition_for_metric(policy: Policy, metric: str) -> PolicyCondition | None:
    """First non-check condition naming this metric (verdict threshold source)."""
    for condition in policy.conditions:
        if condition.tool != "check" and condition.metric == metric:
            return condition
    return None

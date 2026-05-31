"""Validate workflow agent skill and prompt assets."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_ROOT = REPO_ROOT / "src" / "prompts"

AGENT_ASSETS = {
    "EarningsQualityAnalyst": {
        "skill": "earnings-quality-analyst",
        "prompt": "financial/earnings_quality_analyst.md",
    },
    "CashFlowRiskAnalyst": {
        "skill": "cash-flow-risk-analyst",
        "prompt": "financial/cash_flow_risk_analyst.md",
    },
    "ManagementIntentAnalyst": {
        "skill": "management-intent-analyst",
        "prompt": "presentation/management_intent_analyst.md",
    },
    "GuidanceAnalyst": {
        "skill": "guidance-analyst",
        "prompt": "presentation/guidance_analyst.md",
    },
    "BullAgent": {"skill": "bull-agent", "prompt": "debate/bull_agent.md"},
    "BearAgent": {"skill": "bear-agent", "prompt": "debate/bear_agent.md"},
    "JudgeAgent": {"skill": "judge-agent", "prompt": "debate/judge_agent.md"},
}

SHARED_PROMPTS = (
    "shared/global_policy.md",
    "shared/evidence_policy.md",
    "shared/output_policy.md",
)


def validate_assets(repo_root: Path = REPO_ROOT) -> list[str]:
    skill_root = repo_root / ".agents" / "skills"
    prompt_root = repo_root / "src" / "prompts"
    errors: list[str] = []
    expected_skill_paths = [
        skill_root / asset["skill"] / "SKILL.md" for asset in AGENT_ASSETS.values()
    ]
    validate_local_skills = any(
        path.is_file() or path.parent.exists() for path in expected_skill_paths
    )

    for role, asset in AGENT_ASSETS.items():
        skill_path = skill_root / asset["skill"] / "SKILL.md"
        prompt_path = prompt_root / asset["prompt"]
        if validate_local_skills and not skill_path.is_file():
            errors.append(f"{role}: missing skill asset {skill_path.relative_to(repo_root)}")
        if not prompt_path.is_file():
            errors.append(f"{role}: missing prompt asset {prompt_path.relative_to(repo_root)}")
        elif "index" in prompt_path.relative_to(prompt_root).parts:
            errors.append(f"{role}: runtime prompt must not use index asset {asset['prompt']}")

    for relative_path in SHARED_PROMPTS:
        if not (prompt_root / relative_path).is_file():
            errors.append(f"missing shared prompt {relative_path}")

    return errors


def main() -> int:
    errors = validate_assets()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Validated 7 workflow agent prompt assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

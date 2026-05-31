"""Runtime prompt composition for workflow agents."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_ROOT = Path(__file__).resolve().parent / "prompts"
SKILL_ROOT = REPO_ROOT / ".agents" / "skills"
SHARED_PROMPT_FILES = (
    "shared/global_policy.md",
    "shared/evidence_policy.md",
    "shared/output_policy.md",
)

AGENT_PROMPT_FILES = {
    "EarningsQualityAnalyst": "financial/earnings_quality_analyst.md",
    "CashFlowRiskAnalyst": "financial/cash_flow_risk_analyst.md",
    "ManagementIntentAnalyst": "presentation/management_intent_analyst.md",
    "GuidanceAnalyst": "presentation/guidance_analyst.md",
    "BullAgent": "debate/bull_agent.md",
    "BearAgent": "debate/bear_agent.md",
    "JudgeAgent": "debate/judge_agent.md",
}

AGENT_SKILL_FILES = {
    "EarningsQualityAnalyst": "earnings-quality-analyst/SKILL.md",
    "CashFlowRiskAnalyst": "cash-flow-risk-analyst/SKILL.md",
    "ManagementIntentAnalyst": "management-intent-analyst/SKILL.md",
    "GuidanceAnalyst": "guidance-analyst/SKILL.md",
    "BullAgent": "bull-agent/SKILL.md",
    "BearAgent": "bear-agent/SKILL.md",
    "JudgeAgent": "judge-agent/SKILL.md",
}


class SkillAssetError(RuntimeError):
    """Raised when a configured local workflow skill target is invalid."""


def read_prompt(relative_path: str) -> str:
    path = (PROMPT_ROOT / relative_path).resolve()
    if PROMPT_ROOT not in path.parents:
        raise ValueError(f"prompt path escapes prompt root: {relative_path}")
    if "index" in path.relative_to(PROMPT_ROOT).parts:
        raise ValueError(f"runtime prompts cannot load index prompts: {relative_path}")
    return path.read_text(encoding="utf-8").strip()


def build_system_prompt(public_role: str, fallback_scope: str) -> str:
    """Compose shared policies plus exactly one runtime agent prompt."""

    try:
        agent_prompt_file = AGENT_PROMPT_FILES[public_role]
    except KeyError as exc:
        raise ValueError(f"unknown workflow agent role: {public_role}") from exc

    parts = [
        f"<!-- ROLE: {public_role} -->",
        f"あなたは米国株四半期決算レビューworkflowの {public_role} です。",
        f"責務: {fallback_scope}",
    ]
    parts.extend(read_prompt(path) for path in SHARED_PROMPT_FILES)
    parts.append(_mask_other_role_names(read_prompt(agent_prompt_file), public_role))
    return "\n\n".join(parts)


def resolve_skill_target(public_role: str, skill_root: Path | None = None) -> Path | None:
    """Resolve an optional local per-agent skill hook target.

    The public repository carries runtime prompts under ``src/prompts``.  Local
    ``.agents`` skill files are useful editor/agent hooks, but clean CI
    checkouts should not require them.
    """

    try:
        relative_path = AGENT_SKILL_FILES[public_role]
    except KeyError as exc:
        raise SkillAssetError(f"unknown workflow agent role: {public_role}") from exc

    skill_root_was_provided = skill_root is not None
    skill_root = skill_root or SKILL_ROOT
    root = skill_root.resolve()
    if not root.exists() and not skill_root_was_provided:
        return None
    path = (root / relative_path).resolve()
    if root not in path.parents:
        raise SkillAssetError(f"skill path escapes skill root: {relative_path}")
    if not path.is_file():
        if not skill_root_was_provided:
            return None
        raise SkillAssetError(f"{public_role} skill target is missing: {path}")
    return path


def _mask_other_role_names(text: str, public_role: str) -> str:
    """Keep role detection stable when prompt prose references peer agents."""

    for role in AGENT_PROMPT_FILES:
        if role != public_role:
            text = text.replace(
                role, role.replace("Analyst", " Analyst").replace("Agent", " Agent")
            )
    return text

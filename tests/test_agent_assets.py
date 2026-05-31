from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_agent_assets import AGENT_ASSETS, validate_assets
from src.llm import LLMProvider, LLMResponse
from src.prompt_loader import (
    AGENT_PROMPT_FILES,
    AGENT_SKILL_FILES,
    SkillAssetError,
    build_system_prompt,
    resolve_skill_target,
)
from src.workflow_agents import EarningsQualityAnalyst


def test_asset_validator_accepts_repo_assets():
    assert validate_assets() == []


def test_asset_validator_fails_on_missing_assets(tmp_path: Path):
    repo = tmp_path
    (repo / "src" / "prompts" / "shared").mkdir(parents=True)
    for shared in (
        "global_policy.md",
        "evidence_policy.md",
        "output_policy.md",
    ):
        (repo / "src" / "prompts" / "shared" / shared).write_text("policy", encoding="utf-8")

    errors = validate_assets(repo)

    assert errors
    assert any("missing prompt asset" in error for error in errors)


def test_asset_validator_tracks_seven_runtime_agents():
    assert set(AGENT_ASSETS) == {
        "EarningsQualityAnalyst",
        "CashFlowRiskAnalyst",
        "ManagementIntentAnalyst",
        "GuidanceAnalyst",
        "BullAgent",
        "BearAgent",
        "JudgeAgent",
    }


def test_runtime_prompt_mapping_has_exactly_seven_non_index_prompts():
    assert set(AGENT_PROMPT_FILES) == set(AGENT_ASSETS)
    assert set(AGENT_SKILL_FILES) == set(AGENT_ASSETS)
    assert len(AGENT_PROMPT_FILES) == 7
    assert all("index" not in Path(path).parts for path in AGENT_PROMPT_FILES.values())


def test_runtime_skill_targets_resolve_to_local_skill_files(tmp_path: Path):
    skill_root = tmp_path / "skills"
    for relative_path in AGENT_SKILL_FILES.values():
        path = skill_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# local skill", encoding="utf-8")

    for public_role in AGENT_SKILL_FILES:
        resolved = resolve_skill_target(public_role, skill_root)

        assert resolved is not None
        assert resolved.name == "SKILL.md"
        assert resolved.is_file()


def test_system_prompt_includes_shared_policy_and_one_agent_prompt():
    system = build_system_prompt("EarningsQualityAnalyst", "fallback scope")

    assert "<!-- ROLE: EarningsQualityAnalyst -->" in system
    assert "# Global Agent Policy" in system
    assert "# Evidence Policy" in system
    assert "# Output Policy" in system
    assert "# EarningsQualityAnalyst" in system
    assert "# CashFlowRiskAnalyst" not in system
    assert "src/prompts/index" not in system


def test_missing_skill_target_fails_before_llm_call(tmp_path: Path, monkeypatch):
    class CountingLLM(LLMProvider):
        calls = 0

        def complete(self, system, user, max_tokens=2048, temperature=0.7):
            self.calls += 1
            return LLMResponse(text="{}", input_tokens=0, output_tokens=0)

    llm = CountingLLM()
    missing_skill_root = tmp_path / "skills"
    missing_skill_root.mkdir()
    monkeypatch.setattr(
        "src.workflow_agents.resolve_skill_target",
        lambda role: resolve_skill_target(role, missing_skill_root),
    )

    with pytest.raises(SkillAssetError, match="skill target is missing"):
        EarningsQualityAnalyst(llm).run({})

    assert llm.calls == 0

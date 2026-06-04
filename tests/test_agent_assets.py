from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_agent_assets import AGENT_ASSETS, validate_assets
from src.llm import LLMProvider, LLMResponse
from src.prompt_loader import (
    AGENT_PROMPT_FILES,
    AGENT_SKILL_FILES,
    PROMPT_ROOT,
    SkillAssetError,
    build_system_prompt,
    resolve_skill_target,
)
from src.workflow_agents import EarningsQualityAnalyst, GuidanceAnalyst, ManagementIntentAnalyst
from src.workflow_models import BearCase, BullCase, PresentationMetricHint, VerdictLabel


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
    assert "human-readable narrative string in Japanese" in system
    assert "# EarningsQualityAnalyst" in system
    assert "# CashFlowRiskAnalyst" not in system
    assert "src/prompts/index" not in system


def test_evidence_policy_required_fields_match_evidence_item_schema():
    policy = Path("src/prompts/shared/evidence_policy.md").read_text(encoding="utf-8")

    assert "- `summary`" in policy
    assert "- `detail`" in policy
    assert "- `impact_areas`" in policy
    assert "- `source_ref`" in policy
    assert "- `polarity`" in policy
    assert "- `claim`" not in policy
    assert "- `quote_or_value`" not in policy
    assert "- `interpretation`" not in policy
    assert "- `source_type`" not in policy


def test_presentation_metric_hints_are_prompted_as_non_canonical_context():
    global_policy = Path("src/prompts/shared/global_policy.md").read_text(encoding="utf-8")
    evidence_policy = Path("src/prompts/shared/evidence_policy.md").read_text(encoding="utf-8")
    guidance_prompt = (PROMPT_ROOT / AGENT_PROMPT_FILES["GuidanceAnalyst"]).read_text(
        encoding="utf-8"
    )
    earnings_prompt = (PROMPT_ROOT / AGENT_PROMPT_FILES["EarningsQualityAnalyst"]).read_text(
        encoding="utf-8"
    )

    assert "presentation_metric_hints" in global_policy
    assert "canonical fact" in evidence_policy
    assert "presentation_metric_hints" in guidance_prompt
    assert "prior_sequential_period_actuals" in earnings_prompt
    assert "presentation_metric_hints" in GuidanceAnalyst.spec.context_keys
    assert "presentation_metric_hints" in ManagementIntentAnalyst.spec.context_keys
    assert "accepted" not in PresentationMetricHint.model_fields["hint_status"].annotation.__args__


def test_debate_prompt_agent_literals_match_schema():
    expectations = {
        "BullAgent": BullCase.model_fields["agent_name"].default,
        "BearAgent": BearCase.model_fields["agent_name"].default,
    }

    for public_role, expected_literal in expectations.items():
        prompt = (PROMPT_ROOT / AGENT_PROMPT_FILES[public_role]).read_text(encoding="utf-8")

        assert f'agent_name: Literal["{expected_literal}"]' in prompt


def test_judge_prompt_verdict_labels_match_schema():
    prompt = (PROMPT_ROOT / AGENT_PROMPT_FILES["JudgeAgent"]).read_text(encoding="utf-8")

    for label in VerdictLabel:
        assert label.value in prompt


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

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
from src.workflow_models import (
    BearCase,
    BullCase,
    CashFlowRiskFinding,
    ClaimRecord,
    ClaimType,
    DecisionUse,
    EarningsQualityFinding,
    EvidenceItem,
    EvidencePolarity,
    FactCheckStatus,
    GuidanceFinding,
    JudgeDecision,
    JudgeTreatment,
    ManagementIntentFinding,
    MissingDataItem,
    ReportMatrix,
    SourceRef,
    SourceType,
)


def _section_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


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


@pytest.mark.parametrize("public_role", sorted(AGENT_PROMPT_FILES))
def test_runtime_prompts_omit_provider_facing_pseudo_python_models(public_role: str):
    system = build_system_prompt(public_role, "fallback scope")

    assert "```python" not in system
    assert "Required Output Model" not in system


def test_runtime_prompts_name_report_matrix_contract_terms():
    system = build_system_prompt("EarningsQualityAnalyst", "fallback scope")
    contract_models = (
        ReportMatrix,
        EvidenceItem,
        ClaimRecord,
        DecisionUse,
        MissingDataItem,
        SourceRef,
    )

    assert "`source_index`" in system
    for model in contract_models:
        assert f"`{model.__name__}`" in system
        for field_name in model.model_fields:
            assert f"`{field_name}`" in system


def test_runtime_prompt_schema_literals_match_workflow_models():
    system = build_system_prompt("JudgeAgent", "fallback scope")

    for enum_type in (
        SourceType,
        EvidencePolarity,
        ClaimType,
        FactCheckStatus,
        JudgeTreatment,
    ):
        for member in enum_type:
            assert f"`{member.value}`" in system


@pytest.mark.parametrize(
    ("public_role", "output_model"),
    (
        ("EarningsQualityAnalyst", EarningsQualityFinding),
        ("CashFlowRiskAnalyst", CashFlowRiskFinding),
        ("ManagementIntentAnalyst", ManagementIntentFinding),
        ("GuidanceAnalyst", GuidanceFinding),
        ("BullAgent", BullCase),
        ("BearAgent", BearCase),
    ),
)
def test_runtime_prompt_agent_name_literals_match_workflow_models(
    public_role: str,
    output_model: type,
):
    expected_literal = output_model.model_fields["agent_name"].default
    system = build_system_prompt(public_role, "fallback scope")

    assert f"`agent_name`: `{expected_literal}`" in system


def test_judge_prompt_output_contract_matches_judge_decision_fields():
    system = build_system_prompt("JudgeAgent", "fallback scope")
    output_contract = _section_between(
        system,
        "## Required Output Contract",
        "## Validation Rules",
    )

    for field_name in JudgeDecision.model_fields:
        assert f"`{field_name}`" in output_contract
    assert "`missing_data`" not in output_contract


def test_judge_prompt_does_not_instruct_forbidden_missing_data_field():
    system = build_system_prompt("JudgeAgent", "fallback scope")
    normalized_system = " ".join(system.split())
    forbidden_directives = (
        "record it in `missing_data`",
        "explain the limitation in `missing_data`",
        "put the limitation in `missing_data`",
        "`missing_data` caveat",
        "matching `missing_data` explanation",
    )

    for directive in forbidden_directives:
        assert directive not in normalized_system
    assert "only when the role output contract includes `missing_data`" in normalized_system
    assert "describe material gaps inside allowed fields" in normalized_system


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

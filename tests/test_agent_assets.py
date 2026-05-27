from __future__ import annotations

from pathlib import Path

from scripts.validate_agent_assets import AGENT_ASSETS, validate_assets


def test_asset_validator_accepts_repo_assets():
    assert validate_assets() == []


def test_asset_validator_fails_on_missing_assets(tmp_path: Path):
    repo = tmp_path
    (repo / ".agents" / "skills").mkdir(parents=True)
    (repo / "src" / "prompts" / "shared").mkdir(parents=True)
    for shared in (
        "global_policy.md",
        "evidence_policy.md",
        "output_policy.md",
    ):
        (repo / "src" / "prompts" / "shared" / shared).write_text("policy", encoding="utf-8")

    errors = validate_assets(repo)

    assert errors
    assert any("missing skill asset" in error for error in errors)
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

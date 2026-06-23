from __future__ import annotations

from pathlib import Path

from workflow_core.contract_harness.agent_tools import role_agent_skills

ROOT = Path(__file__).resolve().parents[3]


def test_architecture_check_skill_is_compact_and_indexed() -> None:
    skill_path = ROOT / ".agents" / "skills" / "architecture-check" / "SKILL.md"
    index = (ROOT / ".agents" / "skills" / "SKILL_INDEX.md").read_text(encoding="utf-8")
    skill = skill_path.read_text(encoding="utf-8")

    assert "- `architecture-check`" in index
    assert "name: architecture-check" in skill
    assert len(skill.splitlines()) <= 80


def test_architecture_check_is_not_default_writer_skill() -> None:
    writer_skills = {item["name"] for item in role_agent_skills(ROOT, "writer")}

    assert "architecture-check" not in writer_skills

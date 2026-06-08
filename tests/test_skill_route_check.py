from pathlib import Path

from test_agent_operational_helpers import ROOT, run_operational_check, write_file


def test_skill_route_check_passes_current_repo() -> None:
    result = run_operational_check("check-skill-routes.py", ROOT)

    assert result.returncode == 0
    assert "skill route check: passed" in result.stdout


def test_skill_route_check_rejects_unindexed_operational_skill(tmp_path: Path) -> None:
    write_file(tmp_path / "AGENTS.md", "route placeholder\n")
    write_file(tmp_path / "docs/01-agent-operating-contract.md", "contract\n")
    write_file(tmp_path / "docs/02-output-verification-contract.md", "contract\n")
    write_file(tmp_path / "docs/03-repo-boundary-and-storage-contract.md", "contract\n")
    write_file(tmp_path / ".agents/skills/SKILL_INDEX.md", "# Index\n")
    write_file(
        tmp_path / ".agents/skills/scope-routing-governance/SKILL.md",
        """---
name: scope-routing-governance
description: Keep context bounded.
---

# Scope Routing Governance

## Purpose

## Use When

## Do Not Use When

## Read First

## Context Budget

## Method

## Output

## Stop / Carryover Conditions
""",
    )

    result = run_operational_check("check-skill-routes.py", tmp_path)

    assert result.returncode == 1
    assert "index entries must match skill directories" in result.stderr

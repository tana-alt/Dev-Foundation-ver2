from __future__ import annotations

from pathlib import Path

from workflow_core.contract_harness.architecture_gate import (
    canonical_architecture_gate,
    evaluate_architecture_gate,
)


def test_architecture_gate_passes_ordinary_source_diff(tmp_path: Path) -> None:
    gate = evaluate_architecture_gate(
        tmp_path,
        base_sha="base",
        changed_paths=["src/app.py"],
        diff_text="diff --git a/src/app.py b/src/app.py\n+print('ok')\n",
    )

    assert gate.status == "pass"
    assert gate.derived_significance == "none"
    assert gate.reason_codes == ()
    assert gate.oracle_requirements == ()


def test_architecture_gate_blocks_active_doc_expansion(tmp_path: Path) -> None:
    gate = evaluate_architecture_gate(
        tmp_path,
        base_sha="base",
        changed_paths=["docs/04-system-design-contract.md"],
        diff_text=(
            "diff --git a/docs/04-system-design-contract.md "
            "b/docs/04-system-design-contract.md\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/docs/04-system-design-contract.md\n"
            "+new active contract\n"
        ),
    )

    assert gate.status == "block"
    assert gate.reason_codes == ("ACTIVE_DOC_EXPANSION",)
    assert gate.check_kinds["ACTIVE_DOC_EXPANSION"] == "deterministic"


def test_architecture_gate_blocks_unindexed_skill(tmp_path: Path) -> None:
    skill = tmp_path / ".agents" / "skills" / "new-skill" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: new-skill\ndescription: test\n---\n\n# New Skill\n",
        encoding="utf-8",
    )
    index = tmp_path / ".agents" / "skills" / "SKILL_INDEX.md"
    index.write_text("# Index\n\n- `existing-skill`\n", encoding="utf-8")

    gate = evaluate_architecture_gate(
        tmp_path,
        base_sha="base",
        changed_paths=[".agents/skills/new-skill/SKILL.md"],
        diff_text=(
            "diff --git a/.agents/skills/new-skill/SKILL.md "
            "b/.agents/skills/new-skill/SKILL.md\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/.agents/skills/new-skill/SKILL.md\n"
            "+---\n"
        ),
    )

    assert gate.status == "block"
    assert gate.reason_codes == ("UNINDEXED_SKILL",)


def test_architecture_gate_blocks_compact_limit(tmp_path: Path) -> None:
    skill = tmp_path / ".agents" / "skills" / "large-skill" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("\n".join(["line"] * 81) + "\n", encoding="utf-8")

    gate = evaluate_architecture_gate(
        tmp_path,
        base_sha="base",
        changed_paths=[".agents/skills/large-skill/SKILL.md"],
        diff_text=(
            "diff --git a/.agents/skills/large-skill/SKILL.md "
            "b/.agents/skills/large-skill/SKILL.md\n"
        ),
    )

    assert gate.status == "block"
    assert gate.reason_codes == ("SKILL_COMPACT_LIMIT_EXCEEDED",)


def test_architecture_gate_blocks_external_write_heuristic(tmp_path: Path) -> None:
    gate = evaluate_architecture_gate(
        tmp_path,
        base_sha="base",
        changed_paths=["src/client.py"],
        diff_text=(
            "diff --git a/src/client.py b/src/client.py\n"
            "+++ b/src/client.py\n"
            "+requests.post('https://example.com/status', json={})\n"
        ),
    )

    assert gate.status == "block"
    assert gate.reason_codes == ("POSSIBLE_EXTERNAL_WRITE_PATH",)
    assert gate.requires_human_review is True
    assert gate.check_kinds["POSSIBLE_EXTERNAL_WRITE_PATH"] == "conservative_heuristic"


def test_architecture_gate_advisory_maps_to_oracle_requirement(
    tmp_path: Path,
) -> None:
    gate = evaluate_architecture_gate(
        tmp_path,
        base_sha="base",
        changed_paths=["src/workflow_core/contract_harness/agent_tools.py"],
        diff_text=(
            "diff --git a/src/workflow_core/contract_harness/agent_tools.py "
            "b/src/workflow_core/contract_harness/agent_tools.py\n"
            "+ROUTING_CHANGE = True\n"
        ),
    )

    assert gate.status == "advisory"
    assert gate.derived_significance == "local"
    assert gate.advisory_codes == (
        "HARNESS_ROLE_BOUNDARY_CHANGED",
        "ROUTING_OR_CONTEXT_BOUNDARY_CHANGED",
    )
    assert gate.oracle_requirements == ("T_UNION_COVERS_BEHAVIORAL_BOUNDARY",)


def test_canonical_architecture_gate_fails_closed_on_invalid_payload() -> None:
    canonical = canonical_architecture_gate({"status": "maybe"})

    assert canonical["status"] == "block"
    assert canonical["derived_significance"] == "unknown"
    assert canonical["reason_codes"] == ["ARCH_PREDICATE_INCONCLUSIVE"]

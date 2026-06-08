from pathlib import Path
from typing import Any

import pytest

from src.workflow_adapters.codex_sdk_adapter import (
    ApprovedWorkContract,
    CapturingCodexSDKClient,
    CodexRunConfig,
    CodexSDKExecutionAdapter,
    CodexSDKResult,
    ContractValidationError,
    build_headless_prompt,
)


def approved_contract_data() -> dict[str, Any]:
    return {
        "work_contract_id": "contract-001",
        "issue_id": "issue-001",
        "proposal_id": "proposal-001",
        "project_id": "project-001",
        "goal": "Implement a bounded local change.",
        "source_refs": ["AGENTS.md", "docs/01-agent-operating-contract.md"],
        "allowed_write_targets": ["src/workflow_adapters/codex_sdk_adapter.py"],
        "denied_context": ["secrets", "raw_codex_thread_bodies"],
        "verification": ["uv run pytest tests/workflow_adapters -q"],
        "human_gate": {"required": True, "status": "approved", "reason": "test fixture"},
        "risk_flags": ["real_sdk_smoke_human_gated"],
        "git_scope": {
            "mode": "parallel",
            "base_ref": "origin/main",
            "merge_target": "origin/main",
            "branch_target": "agent/workflow-ui-commondb-20260608/codex-runner/sdk-runner",
            "worktree_target": (
                "../worktrees/Dev-Foundation-ver2/workflow-ui-commondb-20260608-codex-runner"
            ),
            "sibling_branch_refs": [],
            "conflict_policy": "explicitly_scoped",
        },
    }


def test_build_headless_prompt_carries_contract_boundaries() -> None:
    contract = ApprovedWorkContract.from_mapping(approved_contract_data())

    prompt = build_headless_prompt(contract)

    assert "Work contract: contract-001" in prompt
    assert "- src/workflow_adapters/codex_sdk_adapter.py" in prompt
    assert "- secrets" in prompt
    assert "Do not merge, release, deploy, mutate CI/CD" in prompt
    expected_branch = "branch_target: agent/workflow-ui-commondb-20260608/codex-runner/sdk-runner"
    assert expected_branch in prompt


def test_adapter_invokes_injected_sdk_client_without_real_sdk() -> None:
    contract = ApprovedWorkContract.from_mapping(approved_contract_data())
    client = CapturingCodexSDKClient(
        result=CodexSDKResult(
            status="completed",
            summary="mocked",
            changed_paths=("src/workflow_adapters/codex_sdk_adapter.py",),
            verification_notes=("targeted tests mocked",),
        )
    )
    adapter = CodexSDKExecutionAdapter(
        client=client,
        config=CodexRunConfig(mode="mock", cwd=Path("/tmp/worktree"), model="mock-model"),
    )

    result = adapter.execute(contract)

    assert result.status == "completed"
    assert result.summary == "mocked"
    assert result.changed_paths == ("src/workflow_adapters/codex_sdk_adapter.py",)
    assert len(client.invocations) == 1
    assert client.invocations[0].cwd == Path("/tmp/worktree")
    assert client.invocations[0].model == "mock-model"


def test_unapproved_contract_is_rejected() -> None:
    data = approved_contract_data()
    data["human_gate"] = {"required": True, "status": "required", "reason": "not approved"}

    with pytest.raises(ContractValidationError, match="human_gate.status"):
        ApprovedWorkContract.from_mapping(data)


def test_reported_changed_paths_must_stay_inside_allowed_targets() -> None:
    contract = ApprovedWorkContract.from_mapping(approved_contract_data())
    client = CapturingCodexSDKClient(
        result=CodexSDKResult(
            status="completed",
            summary="mocked",
            changed_paths=("README.md",),
        )
    )
    adapter = CodexSDKExecutionAdapter(client=client, config=CodexRunConfig(mode="mock"))

    with pytest.raises(ContractValidationError, match="outside allowed targets"):
        adapter.execute(contract)


def test_sdk_mode_without_human_approval_returns_blocked_result() -> None:
    contract = ApprovedWorkContract.from_mapping(approved_contract_data())
    client = CapturingCodexSDKClient(
        result=CodexSDKResult(status="completed", summary="should not be called")
    )
    adapter = CodexSDKExecutionAdapter(
        client=client,
        config=CodexRunConfig(mode="sdk", allow_real_sdk=False),
    )

    result = adapter.execute(contract)

    assert result.status == "blocked"
    assert result.summary == "real Codex SDK execution requires explicit human approval"
    assert client.invocations == []

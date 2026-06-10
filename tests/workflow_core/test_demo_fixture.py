from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_fixture(relative_path: str) -> dict[str, Any]:
    data = yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return cast(dict[str, Any], data)


def test_demo_fixture_links_workflow_stages() -> None:
    workflow = load_fixture(
        "artifact/workflow-ui-commondb-20260608/output/demos/demo-workflow-001/workflow.yaml"
    )

    assert workflow["issue"]["candidate_id"] == workflow["issue_candidate"]["id"]
    assert (
        workflow["implementation_proposal"]["issue_id"]
        == workflow["approved_work_contract"]["issue_id"]
    )
    assert workflow["approval_decision"]["decision"] == "approved"
    assert (
        workflow["execution_run"]["work_contract_id"]
        == workflow["approved_work_contract"]["work_contract_id"]
    )
    assert workflow["verification_result"]["execution_run_id"] == workflow["execution_run"]["id"]
    assert (
        workflow["handoff_artifact"]["verification_result_id"]
        == workflow["verification_result"]["id"]
    )


def test_demo_fixture_context_result_is_sanitized() -> None:
    result = load_fixture(
        "artifact/workflow-ui-commondb-20260608/output/demos/demo-workflow-commondb-run/context-result.yaml"
    )
    text = yaml.safe_dump(result, sort_keys=True).lower()

    assert "/users/" not in text
    assert "file://" not in text
    assert "begin private key" not in text
    assert "api_key" not in text
    assert "access_token" not in text
    assert "raw_source:" not in text
    assert "raw_log:" not in text


def test_demo_checker_passes() -> None:
    completed = subprocess.run(
        ["uv", "run", "python", "scripts/check-demo-workflow.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "passed: sanitized demo workflow is valid" in completed.stdout

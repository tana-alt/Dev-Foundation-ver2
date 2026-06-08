#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WORKFLOW_PATH = (
    ROOT / "artifact/workflow-ui-commondb-20260608" / "output/demos/demo-workflow-001/workflow.yaml"
)
REQUEST_PATH = (
    ROOT
    / "artifact/workflow-ui-commondb-20260608"
    / "output/demos/demo-workflow-commondb-run/context-request.yaml"
)
RESULT_PATH = (
    ROOT
    / "artifact/workflow-ui-commondb-20260608"
    / "output/demos/demo-workflow-commondb-run/context-result.yaml"
)
REQUIRED_STAGES = (
    "issue_candidate",
    "issue",
    "implementation_proposal",
    "approval_decision",
    "approved_work_contract",
    "execution_run",
    "verification_result",
    "handoff_artifact",
)


class DemoWorkflowError(ValueError):
    pass


def main() -> int:
    try:
        validate_demo_workflow()
    except (ValueError, yaml.YAMLError) as error:
        print(f"failed: {error}")
        return 1

    print("passed: sanitized demo workflow is valid")
    return 0


def validate_demo_workflow() -> None:
    from src.workflow_adapters.commondb_context_adapter import (
        validate_context_request,
        validate_context_result,
    )

    workflow = _load_yaml(WORKFLOW_PATH)
    request = _load_yaml(REQUEST_PATH)
    result = _load_yaml(RESULT_PATH)

    validate_context_request(request)
    context_result = validate_context_result(_adapter_result_shape(result))

    _require(workflow.get("schema_version") == "0.1", "workflow schema_version must be 0.1")
    _require(workflow.get("record_type") == "demo_workflow", "workflow record_type mismatch")
    for stage in REQUIRED_STAGES:
        _require(isinstance(workflow.get(stage), dict), f"missing workflow stage: {stage}")

    issue_candidate = workflow["issue_candidate"]
    issue = workflow["issue"]
    proposal = workflow["implementation_proposal"]
    approval = workflow["approval_decision"]
    contract = workflow["approved_work_contract"]
    execution = workflow["execution_run"]
    verification = workflow["verification_result"]
    handoff = workflow["handoff_artifact"]

    _require(issue["candidate_id"] == issue_candidate["id"], "issue must reference candidate")
    _require(proposal["issue_id"] == issue["id"], "proposal must reference issue")
    _require(approval["proposal_id"] == proposal["id"], "approval must reference proposal")
    _require(approval["decision"] == "approved", "approval decision must be approved")
    _require(contract["proposal_id"] == proposal["id"], "contract must reference proposal")
    _require(contract["issue_id"] == issue["id"], "contract must reference issue")
    _require(contract.get("source_refs"), "contract source_refs are required")
    _require(contract.get("allowed_write_targets"), "contract allowed_write_targets are required")
    _require(contract.get("verification"), "contract verification requirements are required")
    _require(
        execution["work_contract_id"] == contract["work_contract_id"],
        "execution must reference contract",
    )
    _require(
        execution["context_result_id"] == context_result.result_id,
        "execution must reference context",
    )
    _require(
        verification["execution_run_id"] == execution["id"], "verification must reference execution"
    )
    _require(verification["status"] == "passed", "verification status must be passed")
    _require(
        handoff["verification_result_id"] == verification["id"],
        "handoff must reference verification",
    )

    _scan_runtime_record(workflow)
    _scan_runtime_record(request)
    _scan_runtime_record(result)


def _adapter_result_shape(result: dict[str, Any]) -> dict[str, Any]:
    shaped = dict(result)
    shaped["status"] = shaped.pop("context_status", None)
    return shaped


def _load_yaml(path: Path) -> dict[str, Any]:
    _require(path.exists(), f"missing fixture: {path.relative_to(ROOT)}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    _require(isinstance(data, dict), f"fixture must be a mapping: {path.relative_to(ROOT)}")
    return data


def _scan_runtime_record(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"denied_context"}:
                continue
            _scan_runtime_record(key)
            _scan_runtime_record(item)
        return

    if isinstance(value, list):
        for item in value:
            _scan_runtime_record(item)
        return

    if not isinstance(value, str):
        return

    forbidden_markers = (
        "/Users/",
        "/private/",
        "/tmp/",
        "file://",
        "BEGIN PRIVATE KEY",
        "api_key",
        "access_token",
        "password",
        "secret=",
        "raw_log:",
        "raw_source:",
    )
    lowered = value.lower()
    for marker in forbidden_markers:
        if marker.lower() in lowered:
            raise DemoWorkflowError(f"forbidden runtime boundary marker found: {marker}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DemoWorkflowError(message)


if __name__ == "__main__":
    raise SystemExit(main())

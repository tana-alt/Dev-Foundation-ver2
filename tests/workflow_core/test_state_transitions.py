from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from workflow_core.checks import WorkflowCheckError, check_execution_ready, check_transition
from workflow_core.contracts import WorkflowStatus

ROOT = Path(__file__).resolve().parents[2]


def valid_contract() -> dict[str, Any]:
    raw = yaml.safe_load((ROOT / "templates/approved-work-contract.yaml").read_text())
    assert isinstance(raw, dict)
    data = cast(dict[str, Any], raw)
    data.pop("schema_version")
    data.pop("record_type")
    data.pop("status")
    return data


def execution_record(status: str = "approved_work_contract") -> dict[str, object]:
    return {
        "record_type": "execution_run",
        "status": status,
        "approval": {"status": "approved"},
        "approved_work_contract": valid_contract(),
    }


def test_valid_transition_to_execution_run() -> None:
    check_transition("approved_work_contract", "execution_run")


def test_invalid_transition_skips_approval() -> None:
    with pytest.raises(WorkflowCheckError, match="invalid workflow transition"):
        check_transition("implementation_proposal", "execution_run")


@pytest.mark.parametrize(
    "status",
    [
        WorkflowStatus.CHANGES_REQUESTED.value,
        WorkflowStatus.BLOCKED.value,
        WorkflowStatus.REJECTED.value,
    ],
)
def test_execution_rejects_blocking_statuses(status: str) -> None:
    with pytest.raises(WorkflowCheckError, match="execution is blocked"):
        check_execution_ready(execution_record(status))


def test_execution_requires_approval() -> None:
    record = execution_record()
    record["approval"] = {"status": "required"}

    with pytest.raises(WorkflowCheckError, match="requires an approved"):
        check_execution_ready(record)


def test_execution_requires_contract_boundaries() -> None:
    record = execution_record()
    contract = valid_contract()
    contract["source_refs"] = []
    record["approved_work_contract"] = contract

    with pytest.raises(ValueError, match="source_refs"):
        check_execution_ready(record)

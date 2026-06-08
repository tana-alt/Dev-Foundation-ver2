from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from pydantic import ValidationError

from workflow_core.contracts import ApprovedWorkContract

ROOT = Path(__file__).resolve().parents[2]


def valid_contract() -> dict[str, Any]:
    raw = yaml.safe_load((ROOT / "templates/approved-work-contract.yaml").read_text())
    assert isinstance(raw, dict)
    data = cast(dict[str, Any], raw)
    data.pop("schema_version")
    data.pop("record_type")
    data.pop("status")
    return data


def test_approved_work_contract_template_is_valid() -> None:
    ApprovedWorkContract.model_validate(valid_contract())


@pytest.mark.parametrize("field", ["source_refs", "allowed_write_targets", "verification"])
def test_approved_work_contract_rejects_empty_execution_boundaries(field: str) -> None:
    data = valid_contract()
    data[field] = []

    with pytest.raises(ValidationError, match=field):
        ApprovedWorkContract.model_validate(data)

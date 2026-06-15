"""Tests for workflow_core.checks that aren't already covered in test_state_transitions.py.

test_state_transitions.py covers:
  - check_transition happy path (approved_work_contract -> execution_run)
  - check_transition invalid transition (implementation_proposal -> execution_run)
  - check_execution_ready with blocking statuses
  - check_execution_ready without approval
  - check_execution_ready with contract boundary violations

New coverage here:
  - check_transition with an unknown current or next status string
  - check_execution_ready with a completely unknown status
  - check_workflow_document happy path
  - check_workflow_document transition-mapping-not-dict error
"""

from __future__ import annotations

import pytest

from workflow_core.checks import WorkflowCheckError, check_transition, check_workflow_document

# ---------------------------------------------------------------------------
# check_transition -- unknown status strings
# ---------------------------------------------------------------------------


def test_check_transition_unknown_current_status_raises() -> None:
    with pytest.raises(WorkflowCheckError, match="unknown workflow status"):
        check_transition("not_a_real_status", "execution_run")


def test_check_transition_unknown_next_status_raises() -> None:
    with pytest.raises(WorkflowCheckError, match="unknown workflow status"):
        check_transition("approved_work_contract", "also_not_real")


def test_check_transition_both_unknown_raises() -> None:
    with pytest.raises(WorkflowCheckError, match="unknown workflow status"):
        check_transition("bogus_from", "bogus_to")


# ---------------------------------------------------------------------------
# check_execution_ready -- unknown status
# ---------------------------------------------------------------------------


def test_check_execution_ready_bogus_status_raises() -> None:
    from workflow_core.checks import check_execution_ready

    with pytest.raises(WorkflowCheckError, match="unknown workflow status"):
        check_execution_ready({"status": "bogus"})


# ---------------------------------------------------------------------------
# check_workflow_document
# ---------------------------------------------------------------------------


def test_check_workflow_document_no_transition_no_execute_passes() -> None:
    """A document with neither a transition nor execution intent is a no-op."""
    check_workflow_document({"record_type": "note", "content": "something"})


def test_check_workflow_document_with_valid_transition_passes() -> None:
    check_workflow_document(
        {
            "transition": {
                "from": "approved_work_contract",
                "to": "execution_run",
            }
        }
    )


def test_check_workflow_document_with_invalid_transition_raises() -> None:
    with pytest.raises(WorkflowCheckError, match="invalid workflow transition"):
        check_workflow_document(
            {
                "transition": {
                    "from": "implementation_proposal",
                    "to": "execution_run",
                }
            }
        )


def test_check_workflow_document_transition_not_dict_raises() -> None:
    with pytest.raises(WorkflowCheckError, match="transition must be a mapping"):
        check_workflow_document({"transition": "approved_work_contract -> execution_run"})


def test_check_workflow_document_transition_not_dict_list_raises() -> None:
    with pytest.raises(WorkflowCheckError, match="transition must be a mapping"):
        check_workflow_document({"transition": ["from", "to"]})

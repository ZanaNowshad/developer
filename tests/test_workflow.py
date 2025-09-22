import asyncio
import asyncio
import json

from developer.schemas import WorkflowParams
from developer.workflow import Workflow


def test_workflow_success() -> None:
    workflow = Workflow(True, None, False)
    params = WorkflowParams.from_dict(
        {
            "step_description": "Initial step",
            "step_number": 1,
            "total_steps": 3,
            "next_step_needed": True,
        }
    )
    result = asyncio.run(workflow.execute_step(params))
    assert result.success is True
    payload = json.loads(result.content[0].text)
    assert payload["step_number"] == 1


def test_workflow_branch_validation() -> None:
    workflow = Workflow(False, None, False)
    params = WorkflowParams.from_dict(
        {
            "step_description": "Branch attempt",
            "step_number": 2,
            "total_steps": 2,
            "next_step_needed": False,
            "branch_from_step": 1,
            "branch_id": "feature",
        }
    )
    result = asyncio.run(workflow.execute_step(params))
    assert result.success is False
    assert "Branching is disabled" in result.error


def test_workflow_revision_validation() -> None:
    workflow = Workflow(True, None, False)
    params = WorkflowParams.from_dict(
        {
            "step_description": "Revision",
            "step_number": 1,
            "total_steps": 1,
            "next_step_needed": False,
            "revises_step": 1,
        }
    )
    result = asyncio.run(workflow.execute_step(params))
    assert result.success is False
    assert "revises_step" in result.error

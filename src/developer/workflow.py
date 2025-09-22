"""Workflow management implementation."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .content import CallToolResult, Content
from .errors import ToolError
from .schemas import WorkflowParams

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class WorkflowStep:
    step_description: str
    step_number: int
    total_steps: int
    next_step_needed: bool
    is_step_revision: Optional[bool]
    revises_step: Optional[int]
    branch_from_step: Optional[int]
    branch_id: Optional[str]
    needs_more_steps: Optional[bool]


@dataclass(slots=True)
class WorkflowState:
    step_history: List[WorkflowStep] = field(default_factory=list)
    branches: Dict[str, List[WorkflowStep]] = field(default_factory=dict)
    current_branch: Optional[str] = None


class Workflow:
    def __init__(
        self,
        allow_branches: bool,
        max_steps: Optional[int],
        log_steps: bool,
    ) -> None:
        self._state = WorkflowState()
        self._lock = asyncio.Lock()
        self._allow_branches = allow_branches
        self._max_steps = max_steps
        self._log_steps = log_steps

    async def execute_step(self, args: WorkflowParams) -> CallToolResult:
        payload = args.model_dump() if hasattr(args, "model_dump") else asdict(args)
        payload.pop("model_config", None)
        step = WorkflowStep(**payload)
        if self._max_steps is not None and step.step_number > self._max_steps:
            message = (
                f"Step number {step.step_number} exceeds configured maximum of {self._max_steps}"
            )
            return CallToolResult.error_result(message)

        async with self._lock:
            return await self._execute_locked(step)

    async def _execute_locked(self, step: WorkflowStep) -> CallToolResult:
        if self._log_steps:
            LOGGER.debug("Workflow step arguments received", extra={"workflow_step_args": step})

        if step.step_number > step.total_steps:
            if self._log_steps:
                LOGGER.info(
                    "Adjusting total_steps to match current step_number as it was greater.",
                    extra={
                        "old_total_steps": step.total_steps,
                        "new_total_steps": step.step_number,
                        "step_number": step.step_number,
                    },
                )
            step.total_steps = step.step_number

        if step.revises_step is not None and not step.is_step_revision:
            message = (
                "When specifying revises_step, is_step_revision must be set to true"
            )
            return CallToolResult.error_result(message)

        if step.branch_id is not None and step.branch_from_step is None:
            message = "When creating a branch (branch_id), you must specify branch_from_step"
            return CallToolResult.error_result(message)

        state = self._state
        if step.branch_id and step.branch_from_step is not None:
            if not self._allow_branches:
                return CallToolResult.error_result(
                    "Branching is disabled in current configuration"
                )
            if step.branch_from_step <= 0 or step.branch_from_step > len(state.step_history):
                return CallToolResult.error_result(
                    f"branch_from_step {step.branch_from_step} does not exist in step history"
                )
            if self._log_steps:
                LOGGER.info(
                    "Processing branch step.",
                    extra={
                        "branch_id": step.branch_id,
                        "branch_from_step": step.branch_from_step,
                        "step_number": step.step_number,
                    },
                )
            state.current_branch = step.branch_id
            state.branches.setdefault(step.branch_id, []).append(step)
        elif state.current_branch and not step.branch_id:
            if self._log_steps:
                LOGGER.info(
                    "Moving from branch back to main history (or default).",
                    extra={"previous_branch": state.current_branch, "step_number": step.step_number},
                )
            state.current_branch = None

        state.step_history.append(step)

        if self._log_steps:
            LOGGER.info(
                "Workflow step processed successfully.",
                extra={
                    "step_number": step.step_number,
                    "total_steps": step.total_steps,
                    "description": step.step_description,
                    "is_revision": step.is_step_revision,
                    "revises_step": step.revises_step,
                    "branch_id": step.branch_id,
                    "next_step_needed": step.next_step_needed,
                    "needs_more_steps": step.needs_more_steps,
                },
            )

        status = await self._build_status(state, step)
        try:
            payload = json.dumps(status, indent=2)
        except TypeError as exc:  # pragma: no cover - unexpected serialization errors
            raise ToolError.internal_error(f"Failed to serialize response: {exc}") from exc
        return CallToolResult.success_result([Content.text_content(payload)])

    async def _build_status(self, state: WorkflowState, step: WorkflowStep) -> Dict[str, Any]:
        branches = sorted(state.branches.keys())
        return {
            "step_number": step.step_number,
            "total_steps": step.total_steps,
            "next_step_needed": step.next_step_needed,
            "last_step_description": step.step_description,
            "current_branch": state.current_branch,
            "branches": branches,
            "step_history_length": len(state.step_history),
        }

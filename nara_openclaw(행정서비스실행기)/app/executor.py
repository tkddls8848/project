from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .schemas import ExecutionRequest, ExecutionStep, StepDryRun, StepExecutionResult

SENSITIVE_KEYS = {"name", "resident_id", "phone", "email", "identity_token", "documents"}


def mask_inputs(values: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in values.items():
        if key in SENSITIVE_KEYS:
            masked[key] = "***"
        else:
            masked[key] = value
    return masked


def render_payload(template: dict[str, Any], user_inputs: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in template.items():
        if isinstance(value, str) and value.startswith("$"):
            payload[key] = user_inputs.get(value[1:])
        else:
            payload[key] = value
    return payload


def build_step_dry_run(step: ExecutionStep, user_inputs: dict[str, Any]) -> StepDryRun:
    missing = [key for key in step.required_inputs if key not in user_inputs or user_inputs[key] in (None, "")]
    warnings: list[str] = []

    if step.execution_mode == "api" and not step.target_url:
        warnings.append("API execution step has no target_url.")
    if step.execution_mode == "linkout" and not step.target_url:
        warnings.append("Linkout step has no target_url.")

    request_preview = render_payload(step.payload_template, user_inputs)
    status = "blocked" if missing or warnings else "ready"

    return StepDryRun(
        step_id=step.step_id,
        title=step.title,
        execution_mode=step.execution_mode,
        action=step.action,
        status=status,
        missing_inputs=missing,
        requires_user_approval=step.requires_user_approval,
        target_url=step.target_url,
        method=step.method,
        request_preview=mask_inputs(request_preview),
        warnings=warnings,
    )


def build_dry_run(req: ExecutionRequest):
    from .schemas import DryRunResponse

    steps = [build_step_dry_run(step, req.user_inputs) for step in req.plan.steps]
    blockers: list[str] = []
    for step in steps:
        for missing in step.missing_inputs:
            blockers.append(f"{step.step_id}: missing input '{missing}'")
        for warning in step.warnings:
            blockers.append(f"{step.step_id}: {warning}")

    approval_required = any(step.requires_user_approval for step in req.plan.steps)
    return DryRunResponse(
        plan_id=req.plan.plan_id,
        goal=req.plan.goal,
        executable=not blockers,
        approval_required=approval_required,
        blockers=blockers,
        warnings=req.plan.warnings,
        steps=steps,
    )


class DummyGovernmentExecutor:
    """Dry-run safe executor that mimics government system outcomes."""

    def execute_step(self, step: ExecutionStep, user_inputs: dict[str, Any]) -> StepExecutionResult:
        if step.execution_mode == "manual":
            return StepExecutionResult(
                step_id=step.step_id,
                title=step.title,
                execution_mode=step.execution_mode,
                status="completed",
                message="Manual checklist generated. User action is required outside OpenClaw.",
                response_data={"checklist": step.manual_instructions},
            )

        if step.execution_mode == "linkout":
            return StepExecutionResult(
                step_id=step.step_id,
                title=step.title,
                execution_mode=step.execution_mode,
                status="completed",
                message="Government service link prepared for user handoff.",
                target_url=step.target_url,
                response_data={"handoff_required": True},
            )

        receipt_id = f"DUMMY-GOV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"
        return StepExecutionResult(
            step_id=step.step_id,
            title=step.title,
            execution_mode=step.execution_mode,
            status="completed",
            message="Dummy government API call completed. Replace this adapter with a real connector for production.",
            receipt_id=receipt_id,
            target_url=step.target_url,
            response_data={
                "method": step.method,
                "submitted_payload": mask_inputs(render_payload(step.payload_template, user_inputs)),
            },
        )

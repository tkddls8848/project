from typing import Any, Literal

from pydantic import BaseModel, Field


ExecutionMode = Literal["api", "linkout", "manual"]
StepAction = Literal["lookup", "eligibility", "apply", "reserve", "notify", "document", "manual"]
RiskLevel = Literal["low", "medium", "high"]
StepStatus = Literal["ready", "blocked", "skipped", "completed", "failed"]


class ExecutionStep(BaseModel):
    step_id: str
    title: str
    service_id: str | None = None
    action: StepAction
    execution_mode: ExecutionMode
    target_url: str | None = None
    method: str = "POST"
    required_inputs: list[str] = Field(default_factory=list)
    payload_template: dict[str, Any] = Field(default_factory=dict)
    requires_user_approval: bool = True
    risk_level: RiskLevel = "medium"
    manual_instructions: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    plan_id: str
    goal: str
    source: str = "nara_combiner"
    steps: list[ExecutionStep]
    warnings: list[str] = Field(default_factory=list)


class Approval(BaseModel):
    approved: bool = False
    approver: str | None = None
    approval_token: str | None = None


class ExecutionRequest(BaseModel):
    plan: ExecutionPlan
    user_inputs: dict[str, Any] = Field(default_factory=dict)
    approval: Approval = Field(default_factory=Approval)


class StepDryRun(BaseModel):
    step_id: str
    title: str
    execution_mode: ExecutionMode
    action: StepAction
    status: StepStatus
    missing_inputs: list[str] = Field(default_factory=list)
    requires_user_approval: bool
    target_url: str | None = None
    method: str
    request_preview: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class DryRunResponse(BaseModel):
    plan_id: str
    goal: str
    executable: bool
    approval_required: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    steps: list[StepDryRun]


class StepExecutionResult(BaseModel):
    step_id: str
    title: str
    execution_mode: ExecutionMode
    status: StepStatus
    message: str
    receipt_id: str | None = None
    target_url: str | None = None
    response_data: dict[str, Any] = Field(default_factory=dict)


class RunRecord(BaseModel):
    run_id: str
    plan_id: str
    goal: str
    status: Literal["completed", "blocked", "partial", "failed"]
    # 차단 사유 코드: dry_run_blocked / approval_missing / approver_missing
    status_reason: str | None = None
    # 실행 어댑터 종류. "dummy"는 실제 기관 제출이 아님을 뜻한다.
    executor_mode: str = "dummy"
    approved_by: str | None = None
    approved_at: str | None = None
    created_at: str
    dry_run: DryRunResponse
    executed_steps: list[StepExecutionResult] = Field(default_factory=list)
    user_inputs: dict[str, Any] = Field(default_factory=dict)

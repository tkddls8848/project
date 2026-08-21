from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .approvals import hash_json


SAFE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
INPUT_REF_PATTERN = r"^user_input\.[A-Za-z][A-Za-z0-9_]{0,63}$"


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, max_length=128, pattern=SAFE_ID_PATTERN)
    verified_at: datetime
    validation_result: Literal["verified"]


class ExecutionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1, max_length=128, pattern=SAFE_ID_PATTERN)
    operation_id: str = Field(min_length=1, max_length=128, pattern=SAFE_ID_PATTERN)
    operation_version: str = Field(min_length=1, max_length=32, pattern=r"^[0-9]+(?:\.[0-9]+){0,2}$")
    depends_on: list[str] = Field(default_factory=list, max_length=64)
    input_refs: dict[str, str] = Field(default_factory=dict, max_length=64)
    risk_level: Literal["low", "medium", "high"]
    timeout_seconds: float = Field(gt=0, le=300)

    @field_validator("depends_on")
    @classmethod
    def validate_dependencies(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("duplicate step dependency")
        for value in values:
            if not value or len(value) > 128:
                raise ValueError("invalid step dependency")
        return values

    @field_validator("input_refs")
    @classmethod
    def validate_input_refs(cls, values: dict[str, str]) -> dict[str, str]:
        import re

        for field, reference in values.items():
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", field):
                raise ValueError("invalid adapter input field")
            if not re.fullmatch(INPUT_REF_PATTERN, reference):
                raise ValueError("input references must use user_input.<name>")
        return values


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    plan_id: str = Field(min_length=1, max_length=128, pattern=SAFE_ID_PATTERN)
    plan_version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_scenario_id: str = Field(min_length=1, max_length=128, pattern=SAFE_ID_PATTERN)
    created_at: datetime
    expires_at: datetime
    steps: list[ExecutionStep] = Field(min_length=1, max_length=64)
    required_approval_policy: Literal["session_reauth"]
    evidence_refs: list[EvidenceRef] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_plan_graph_and_hash(self) -> "ExecutionPlan":
        if self.expires_at <= self.created_at or self.expires_at <= datetime.now(timezone.utc):
            raise ValueError("execution plan is expired")
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("duplicate step_id")
        known = set(step_ids)
        for step in self.steps:
            if step.step_id in step.depends_on or not set(step.depends_on) <= known:
                raise ValueError("invalid step dependency")

        visiting: set[str] = set()
        visited: set[str] = set()
        by_id = {step.step_id: step for step in self.steps}

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError("cyclic step dependency")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in by_id[step_id].depends_on:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in step_ids:
            visit(step_id)
        if self.content_hash != execution_plan_hash(self):
            raise ValueError("content_hash does not match plan")
        return self


def execution_plan_hash(plan: ExecutionPlan) -> str:
    material = plan.model_dump(mode="python")
    material.pop("content_hash", None)

    def normalize(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    return hash_json(normalize(material))

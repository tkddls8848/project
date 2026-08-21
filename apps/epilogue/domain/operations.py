from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .plans import ExecutionPlan


class OperationInputField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["string", "integer", "boolean"]
    required: bool = True
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=1, le=4096)
    pattern: str | None = None


class OperationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    version: str
    adapter: Literal["dummy"]
    institution: str
    execution_mode: Literal["api", "manual", "linkout"]
    method: Literal["GET", "POST"]
    allowed_host: str | None = None
    allowed_path: str | None = None
    input_fields: dict[str, OperationInputField]
    result_fields: list[str]
    write_operation: bool
    risk_level: Literal["low", "medium", "high"]
    required_permission: Literal["epilogue"]
    approval_policy: Literal["session_reauth"]
    dry_run_supported: bool
    idempotency_supported: bool
    safe_retry: bool
    max_attempts: int = Field(default=1, ge=1, le=3)
    success_confirmation: str
    recovery_guidance: str
    dummy_behavior: Literal["success", "fail", "timeout", "manual", "linkout", "unknown", "transient"]
    dummy_delay_seconds: float = Field(default=0, ge=0, le=5)
    server_link: str | None = None

    @model_validator(mode="after")
    def validate_server_owned_target(self) -> "OperationSpec":
        if self.execution_mode in {"api", "linkout"}:
            if not self.allowed_host or not re.fullmatch(r"[A-Za-z0-9.-]+", self.allowed_host):
                raise ValueError("API/linkout operations require a reviewed host")
            if not self.allowed_path or not self.allowed_path.startswith("/") or ".." in self.allowed_path:
                raise ValueError("API/linkout operations require a reviewed absolute path")
        if self.execution_mode == "manual" and (self.allowed_host or self.allowed_path or self.server_link):
            raise ValueError("manual operations cannot declare a network target")
        return self


class OperationValidationError(ValueError):
    pass


_ATTACK_PATTERNS = (
    re.compile(r"(?:https?|ftp|file)://", re.IGNORECASE),
    re.compile(r"(?:^|[\\/])\.\.(?:[\\/]|$)"),
    re.compile(r"^[A-Za-z]:[\\/]"),
    re.compile(r"^/(?:etc|proc|sys|var|usr|home|root|tmp)(?:/|$)", re.IGNORECASE),
    re.compile(r"(?:;|&&|\|\||`|\$\()"),
    re.compile(r"[\r\n]"),
)


def _reject_unsafe_value(value: Any) -> None:
    if isinstance(value, str) and any(pattern.search(value) for pattern in _ATTACK_PATTERNS):
        raise OperationValidationError("unsafe input rejected")
    if isinstance(value, dict):
        for nested in value.values():
            _reject_unsafe_value(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_unsafe_value(nested)


class OperationRegistry:
    def __init__(self, specs: list[OperationSpec]):
        self._specs = {(spec.operation_id, spec.version): spec for spec in specs}

    @classmethod
    def from_json(cls, path: Path) -> "OperationRegistry":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls([OperationSpec.model_validate(item) for item in raw["operations"]])

    def get(self, operation_id: str, version: str) -> OperationSpec:
        try:
            return self._specs[(operation_id, version)]
        except KeyError as exc:
            raise OperationValidationError("operation is not registered") from exc

    def validate_plan(self, plan: ExecutionPlan, user_inputs: dict[str, Any]) -> list[dict[str, Any]]:
        _reject_unsafe_value(user_inputs)
        referenced_user_fields: set[str] = set()
        impact: list[dict[str, Any]] = []
        for step in plan.steps:
            spec = self.get(step.operation_id, step.operation_version)
            if step.risk_level != spec.risk_level:
                raise OperationValidationError("risk level differs from registered operation")
            if not spec.dry_run_supported:
                raise OperationValidationError("operation does not support dry-run")
            if set(step.input_refs) != set(spec.input_fields):
                raise OperationValidationError("operation inputs differ from registered schema")
            for adapter_field, reference in step.input_refs.items():
                source = reference.removeprefix("user_input.")
                referenced_user_fields.add(source)
                field_spec = spec.input_fields[adapter_field]
                value = user_inputs.get(source)
                if value is None:
                    if field_spec.required:
                        raise OperationValidationError("required input is missing")
                    continue
                self._validate_field(field_spec, value)
            impact.append(
                {
                    "step_id": step.step_id,
                    "operation_id": spec.operation_id,
                    "institution": spec.institution,
                    "execution_mode": spec.execution_mode,
                    "write_operation": spec.write_operation,
                    "risk_level": spec.risk_level,
                    "requires_approval": True,
                }
            )
        if set(user_inputs) != referenced_user_fields:
            raise OperationValidationError("unexpected input fields")
        return impact

    @staticmethod
    def _validate_field(field: OperationInputField, value: Any) -> None:
        expected = {"string": str, "integer": int, "boolean": bool}[field.type]
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            raise OperationValidationError("input type mismatch")
        if isinstance(value, str):
            if field.min_length is not None and len(value) < field.min_length:
                raise OperationValidationError("input is too short")
            if field.max_length is not None and len(value) > field.max_length:
                raise OperationValidationError("input is too long")
            if field.pattern and not re.fullmatch(field.pattern, value):
                raise OperationValidationError("input format rejected")

    def resolve_inputs(self, plan: ExecutionPlan, step_id: str, user_inputs: dict[str, Any]) -> dict[str, Any]:
        step = next(item for item in plan.steps if item.step_id == step_id)
        return {field: user_inputs[reference.removeprefix("user_input.")] for field, reference in step.input_refs.items()}

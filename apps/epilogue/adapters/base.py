from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from domain.operations import OperationSpec


@dataclass(frozen=True)
class AdapterResult:
    status: Literal["succeeded", "failed", "outcome_unknown", "awaiting_user", "retryable"]
    receipt: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None


class Adapter(Protocol):
    def execute(self, spec: OperationSpec, inputs: dict[str, Any], idempotency_key: str) -> AdapterResult: ...

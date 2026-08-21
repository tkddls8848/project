from __future__ import annotations

import threading
import time
from collections import Counter
from uuid import uuid4

from domain.operations import OperationSpec

from .base import AdapterResult


class DummyAdapter:
    """Deterministic, no-network adapter used to verify execution controls."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = threading.Lock()

    def invocation_count(self, operation_id: str) -> int:
        with self._lock:
            return self._counts[operation_id]

    def execute(self, spec: OperationSpec, inputs: dict[str, object], idempotency_key: str) -> AdapterResult:
        del inputs
        with self._lock:
            self._counts[spec.operation_id] += 1
            attempt = self._counts[spec.operation_id]
        if spec.dummy_delay_seconds:
            time.sleep(spec.dummy_delay_seconds)
        receipt = {
            "receipt_code": f"DUMMY-{uuid4().hex[:16].upper()}",
            "operation_id": spec.operation_id,
        }
        if spec.dummy_behavior == "fail":
            return AdapterResult(status="failed", error_code="dummy_rejected")
        if spec.dummy_behavior == "manual":
            return AdapterResult(status="awaiting_user", receipt={"instructions": "Complete the reviewed manual checklist."})
        if spec.dummy_behavior == "linkout":
            return AdapterResult(status="awaiting_user", receipt={"handoff_required": True})
        if spec.dummy_behavior == "unknown":
            return AdapterResult(status="outcome_unknown", receipt={**receipt, "reconciled_status": "succeeded"})
        if spec.dummy_behavior == "transient" and attempt == 1:
            return AdapterResult(status="retryable", error_code="dummy_transient")
        return AdapterResult(status="succeeded", receipt=receipt)

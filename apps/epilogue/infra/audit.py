from __future__ import annotations

from typing import Any


ALLOWED_AUDIT_DATA_FIELDS = {
    "reason",
    "step_id",
    "operation_id",
    "worker_id",
    "receipt_id",
    "recovered_from",
    "manual_recovery_required",
}


def safe_audit_data(values: dict[str, Any] | None) -> dict[str, Any]:
    values = values or {}
    return {key: values[key] for key in ALLOWED_AUDIT_DATA_FIELDS if key in values}

from __future__ import annotations

from typing import Any


SENSITIVE_NAMES = {
    "password",
    "token",
    "secret",
    "service_key",
    "resident_id",
    "birth_date",
    "phone",
    "email",
    "address",
    "documents",
}
SENSITIVE_SUFFIXES = ("_password", "_token", "_secret", "_key")


def is_sensitive_name(name: str) -> bool:
    lowered = name.casefold()
    return lowered in SENSITIVE_NAMES or lowered.endswith(SENSITIVE_SUFFIXES)


def safe_input_summary(values: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return only structural presence metadata, never user-provided values."""
    return {key: {"present": value is not None, "type": type(value).__name__} for key, value in sorted(values.items())}


def allowlisted_result(values: dict[str, Any], allowed_fields: list[str]) -> dict[str, Any]:
    return {field: values[field] for field in allowed_fields if field in values and not is_sensitive_name(field)}

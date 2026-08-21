from __future__ import annotations


class InvalidTransition(ValueError):
    """Raised when a persisted run attempts an unsupported state change."""


TERMINAL_STATES = {
    "succeeded",
    "partially_succeeded",
    "failed",
    "outcome_unknown",
    "awaiting_user",
    "cancelled",
}

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"validating", "cancelled"}),
    "validating": frozenset({"blocked", "awaiting_approval", "cancelled"}),
    "blocked": frozenset(),
    "awaiting_approval": frozenset({"approved", "blocked", "cancelled"}),
    "approved": frozenset({"queued", "awaiting_approval", "cancelled"}),
    "queued": frozenset({"running", "cancelled"}),
    "running": frozenset(
        {
            "succeeded",
            "partially_succeeded",
            "failed",
            "outcome_unknown",
            "awaiting_user",
            "cancelled",
        }
    ),
    # Reconciliation is the only path out of an unknown outcome.
    "outcome_unknown": frozenset({"succeeded", "partially_succeeded", "failed", "awaiting_user"}),
    "succeeded": frozenset(),
    "partially_succeeded": frozenset(),
    "failed": frozenset(),
    "awaiting_user": frozenset(),
    "cancelled": frozenset(),
}


def require_transition(current: str, target: str) -> None:
    if current not in ALLOWED_TRANSITIONS or target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"unsupported execution state transition: {current} -> {target}")

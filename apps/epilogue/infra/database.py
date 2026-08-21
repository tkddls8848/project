from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from domain.approvals import canonical_json, hash_json, new_opaque_token, token_hash
from domain.plans import ExecutionPlan, execution_plan_hash
from domain.state_machine import require_transition
from infra.audit import safe_audit_data
from infra.secrets import safe_input_summary


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


class DatabaseError(RuntimeError):
    pass


class NotFound(DatabaseError):
    pass


class Forbidden(DatabaseError):
    pass


class Conflict(DatabaseError):
    pass


class ApprovalBindingChanged(Conflict):
    def __init__(self, challenge: str):
        super().__init__("approval binding changed")
        self.challenge = challenge


SCHEMA = r"""
CREATE TABLE IF NOT EXISTS execution_plans (
    plan_id TEXT NOT NULL,
    plan_version INTEGER NOT NULL,
    content_hash TEXT NOT NULL CHECK(length(content_hash) = 64),
    plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (plan_id, plan_version),
    UNIQUE (content_hash)
);

CREATE TABLE IF NOT EXISTS execution_runs (
    run_id TEXT PRIMARY KEY,
    owner_principal TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    plan_version INTEGER NOT NULL,
    plan_hash TEXT NOT NULL CHECK(length(plan_hash) = 64),
    input_json TEXT NOT NULL,
    input_hash TEXT NOT NULL CHECK(length(input_hash) = 64),
    status TEXT NOT NULL,
    status_reason TEXT,
    approval_challenge_expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    lease_owner TEXT,
    lease_expires_at TEXT,
    worker_attempts INTEGER NOT NULL DEFAULT 0,
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0, 1)),
    manual_recovery_required INTEGER NOT NULL DEFAULT 0 CHECK(manual_recovery_required IN (0, 1)),
    recovery_guidance TEXT,
    FOREIGN KEY (plan_id, plan_version) REFERENCES execution_plans(plan_id, plan_version)
);

CREATE TABLE IF NOT EXISTS step_runs (
    step_run_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES execution_runs(run_id),
    step_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    operation_version TEXT NOT NULL,
    step_idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    timeout_seconds REAL NOT NULL,
    result_json TEXT,
    error_code TEXT,
    started_at TEXT,
    finished_at TEXT,
    UNIQUE(run_id, step_id)
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES execution_runs(run_id),
    challenge_hash TEXT NOT NULL UNIQUE,
    principal_id TEXT,
    plan_hash TEXT,
    input_hash TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    approved_at TEXT,
    consumed_at TEXT,
    invalidated_at TEXT
);
CREATE INDEX IF NOT EXISTS approvals_run_idx ON approvals(run_id, created_at DESC);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES execution_runs(run_id),
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    actor_principal TEXT,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, sequence)
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    principal_id TEXT NOT NULL,
    plan_hash TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES execution_runs(run_id),
    created_at TEXT NOT NULL,
    PRIMARY KEY(principal_id, plan_hash, idempotency_key)
);

CREATE TABLE IF NOT EXISTS adapter_receipts (
    receipt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES execution_runs(run_id),
    step_id TEXT NOT NULL,
    step_idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    receipt_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    session_hash TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TRIGGER IF NOT EXISTS audit_events_no_update
BEFORE UPDATE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
BEFORE DELETE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS execution_plans_no_update
BEFORE UPDATE ON execution_plans BEGIN
    SELECT RAISE(ABORT, 'validated plans are immutable');
END;
CREATE TRIGGER IF NOT EXISTS execution_plans_no_delete
BEFORE DELETE ON execution_plans BEGIN
    SELECT RAISE(ABORT, 'validated plans are immutable');
END;
CREATE TRIGGER IF NOT EXISTS execution_runs_status_requires_audit_context
BEFORE UPDATE OF status ON execution_runs
WHEN epilogue_audit_context() != 1 BEGIN
    SELECT RAISE(ABORT, 'run status changes require audited transaction');
END;
CREATE TRIGGER IF NOT EXISTS step_runs_status_requires_audit_context
BEFORE UPDATE OF status ON step_runs
WHEN epilogue_audit_context() != 1 BEGIN
    SELECT RAISE(ABORT, 'step status changes require audited transaction');
END;
"""


class Database:
    def __init__(self, path: Path, *, approval_ttl_seconds: int = 300):
        self.path = Path(path)
        self.approval_ttl_seconds = approval_ttl_seconds
        self._thread_state = threading.local()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(SCHEMA)
            connection.commit()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        connection.create_function("epilogue_audit_context", 0, lambda: int(getattr(self._thread_state, "audit", False)))
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self, *, audited: bool = False) -> Iterator[sqlite3.Connection]:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            old = getattr(self._thread_state, "audit", False)
            self._thread_state.audit = audited
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                self._thread_state.audit = old

    def _audit(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        event_type: str,
        *,
        actor: str | None,
        from_status: str | None = None,
        to_status: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM audit_events WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO audit_events
               (run_id, sequence, event_type, from_status, to_status, actor_principal, data_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, sequence, event_type, from_status, to_status, actor, canonical_json(safe_audit_data(data)), iso_now()),
        )

    def _transition(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        current: str,
        target: str,
        *,
        actor: str | None,
        reason: str | None = None,
        event_type: str = "state_changed",
        extra_updates: str = "",
        extra_parameters: tuple[Any, ...] = (),
        data: dict[str, Any] | None = None,
    ) -> None:
        require_transition(current, target)
        now = iso_now()
        connection.execute(
            f"UPDATE execution_runs SET status = ?, status_reason = ?, updated_at = ? {extra_updates} WHERE run_id = ? AND status = ?",
            (target, reason, now, *extra_parameters, run_id, current),
        )
        self._audit(
            connection,
            run_id,
            event_type,
            actor=actor,
            from_status=current,
            to_status=target,
            data={"reason": reason, **(data or {})},
        )

    def save_validated_plan(self, plan: ExecutionPlan) -> None:
        serialized = canonical_json(plan.model_dump(mode="json"))
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT content_hash FROM execution_plans WHERE plan_id = ? AND plan_version = ?",
                (plan.plan_id, plan.plan_version),
            ).fetchone()
            if existing:
                if existing["content_hash"] != plan.content_hash:
                    raise Conflict("plan version is immutable")
                return
            connection.execute(
                "INSERT INTO execution_plans(plan_id, plan_version, content_hash, plan_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (plan.plan_id, plan.plan_version, plan.content_hash, serialized, iso_now()),
            )

    def get_plan(self, plan_id: str, plan_version: int, content_hash: str | None = None) -> ExecutionPlan:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM execution_plans WHERE plan_id = ? AND plan_version = ?", (plan_id, plan_version)
            ).fetchone()
        if not row or (content_hash is not None and row["content_hash"] != content_hash):
            raise NotFound("validated plan not found")
        return ExecutionPlan.model_validate_json(row["plan_json"])

    def create_session(self, principal_id: str, ttl_seconds: int) -> str:
        token = new_opaque_token()
        now = utc_now()
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO auth_sessions(session_hash, principal_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token_hash(token), principal_id, now.isoformat(), (now + timedelta(seconds=ttl_seconds)).isoformat()),
            )
        return token

    def resolve_session(self, token: str) -> str | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT principal_id FROM auth_sessions
                   WHERE session_hash = ? AND revoked_at IS NULL AND expires_at > ?""",
                (token_hash(token), iso_now()),
            ).fetchone()
        return row["principal_id"] if row else None

    def create_run(
        self,
        principal_id: str,
        plan: ExecutionPlan,
        user_inputs: dict[str, Any],
        idempotency_key: str,
    ) -> tuple[dict[str, Any], bool]:
        if not idempotency_key or len(idempotency_key) > 128:
            raise Conflict("valid Idempotency-Key is required")
        input_hash = hash_json(user_inputs)
        request_hash = hash_json(
            {
                "principal_id": principal_id,
                "plan_hash": plan.content_hash,
                "input_hash": input_hash,
                "idempotency_key": idempotency_key,
            }
        )
        challenge = new_opaque_token()
        run_id = f"run_{uuid4().hex}"
        now = utc_now()
        expires = now + timedelta(seconds=self.approval_ttl_seconds)
        with self._transaction(audited=True) as connection:
            existing = connection.execute(
                """SELECT request_hash, run_id FROM idempotency_keys
                   WHERE principal_id = ? AND plan_hash = ? AND idempotency_key = ?""",
                (principal_id, plan.content_hash, idempotency_key),
            ).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise Conflict("idempotency key was already used with different inputs")
                return self._read_run(connection, existing["run_id"], principal_id, include_internal=False), False

            connection.execute(
                """INSERT INTO execution_runs
                   (run_id, owner_principal, plan_id, plan_version, plan_hash, input_json, input_hash,
                    status, approval_challenge_expires_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)""",
                (
                    run_id,
                    principal_id,
                    plan.plan_id,
                    plan.plan_version,
                    plan.content_hash,
                    canonical_json(user_inputs),
                    input_hash,
                    expires.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            self._audit(connection, run_id, "run_created", actor=principal_id, to_status="draft")
            self._transition(connection, run_id, "draft", "validating", actor=principal_id)
            self._transition(connection, run_id, "validating", "awaiting_approval", actor=principal_id)
            for step in plan.steps:
                step_key = hash_json({"run_id": run_id, "plan_hash": plan.content_hash, "step_id": step.step_id})
                connection.execute(
                    """INSERT INTO step_runs
                       (step_run_id, run_id, step_id, operation_id, operation_version,
                        step_idempotency_key, status, timeout_seconds)
                       VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                    (
                        f"step_run_{uuid4().hex}",
                        run_id,
                        step.step_id,
                        step.operation_id,
                        step.operation_version,
                        step_key,
                        step.timeout_seconds,
                    ),
                )
            connection.execute(
                """INSERT INTO approvals
                   (approval_id, run_id, challenge_hash, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (f"approval_{uuid4().hex}", run_id, token_hash(challenge), now.isoformat(), expires.isoformat()),
            )
            connection.execute(
                """INSERT INTO idempotency_keys
                   (principal_id, plan_hash, idempotency_key, request_hash, run_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (principal_id, plan.content_hash, idempotency_key, request_hash, run_id, now.isoformat()),
            )
            response = self._read_run(connection, run_id, principal_id, include_internal=False)
            response["approval_challenge"] = challenge
            return response, True

    def _owned_row(self, connection: sqlite3.Connection, run_id: str, principal_id: str | None) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM execution_runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            raise NotFound("run not found")
        if principal_id is not None and row["owner_principal"] != principal_id:
            raise Forbidden("run belongs to another principal")
        return row

    def _read_run(
        self, connection: sqlite3.Connection, run_id: str, principal_id: str | None, *, include_internal: bool
    ) -> dict[str, Any]:
        row = self._owned_row(connection, run_id, principal_id)
        steps = [dict(item) for item in connection.execute("SELECT * FROM step_runs WHERE run_id = ? ORDER BY rowid", (run_id,))]
        result = {
            "run_id": row["run_id"],
            "plan_id": row["plan_id"],
            "plan_version": row["plan_version"],
            "plan_hash": row["plan_hash"],
            "status": row["status"],
            "status_reason": row["status_reason"],
            "owner_principal": row["owner_principal"],
            "input_summary": safe_input_summary(json.loads(row["input_json"])),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "cancel_requested": bool(row["cancel_requested"]),
            "manual_recovery_required": bool(row["manual_recovery_required"]),
            "recovery_guidance": row["recovery_guidance"],
            "approval_challenge": None,
            "steps": [
                {
                    "step_id": step["step_id"],
                    "operation_id": step["operation_id"],
                    "status": step["status"],
                    "attempts": step["attempts"],
                    "error_code": step["error_code"],
                    "result": json.loads(step["result_json"]) if step["result_json"] else None,
                }
                for step in steps
            ],
        }
        if include_internal:
            plan_row = connection.execute(
                "SELECT plan_json FROM execution_plans WHERE plan_id = ? AND plan_version = ?",
                (row["plan_id"], row["plan_version"]),
            ).fetchone()
            result.update(
                {
                    "input_json": json.loads(row["input_json"]),
                    "input_hash": row["input_hash"],
                    "plan": ExecutionPlan.model_validate_json(plan_row["plan_json"]),
                    "lease_owner": row["lease_owner"],
                    "lease_expires_at": row["lease_expires_at"],
                }
            )
        return result

    def get_run(self, run_id: str, principal_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            return self._read_run(connection, run_id, principal_id, include_internal=False)

    def get_run_internal(self, run_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            return self._read_run(connection, run_id, None, include_internal=True)

    def list_events(self, run_id: str, principal_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            self._owned_row(connection, run_id, principal_id)
            rows = connection.execute("SELECT * FROM audit_events WHERE run_id = ? ORDER BY sequence", (run_id,)).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "sequence": row["sequence"],
                "event_type": row["event_type"],
                "from_status": row["from_status"],
                "to_status": row["to_status"],
                "actor_principal": row["actor_principal"],
                "data": json.loads(row["data_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def approve(self, run_id: str, principal_id: str, challenge: str) -> dict[str, Any]:
        with self._transaction(audited=True) as connection:
            run = self._owned_row(connection, run_id, principal_id)
            if run["status"] != "awaiting_approval":
                raise Conflict("approval challenge cannot be replayed")
            approval = connection.execute(
                "SELECT * FROM approvals WHERE run_id = ? ORDER BY created_at DESC LIMIT 1", (run_id,)
            ).fetchone()
            if (
                not approval
                or approval["challenge_hash"] != token_hash(challenge)
                or approval["approved_at"] is not None
                or approval["invalidated_at"] is not None
                or approval["expires_at"] <= iso_now()
            ):
                raise Conflict("approval challenge is invalid or expired")
            now = iso_now()
            connection.execute(
                """UPDATE approvals SET principal_id = ?, plan_hash = ?, input_hash = ?, approved_at = ?
                   WHERE approval_id = ?""",
                (principal_id, run["plan_hash"], run["input_hash"], now, approval["approval_id"]),
            )
            self._transition(connection, run_id, "awaiting_approval", "approved", actor=principal_id, event_type="approval_granted")
            return self._read_run(connection, run_id, principal_id, include_internal=False)

    def _new_approval_challenge(self, connection: sqlite3.Connection, run_id: str) -> str:
        challenge = new_opaque_token()
        now = utc_now()
        expires = now + timedelta(seconds=self.approval_ttl_seconds)
        connection.execute(
            """INSERT INTO approvals(approval_id, run_id, challenge_hash, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (f"approval_{uuid4().hex}", run_id, token_hash(challenge), now.isoformat(), expires.isoformat()),
        )
        connection.execute(
            "UPDATE execution_runs SET approval_challenge_expires_at = ? WHERE run_id = ?",
            (expires.isoformat(), run_id),
        )
        return challenge

    def queue_run(self, run_id: str, principal_id: str) -> dict[str, Any]:
        changed: ApprovalBindingChanged | None = None
        with self._transaction(audited=True) as connection:
            run = self._owned_row(connection, run_id, principal_id)
            if run["status"] in {"queued", "running", "succeeded", "partially_succeeded", "awaiting_user", "outcome_unknown"}:
                return self._read_run(connection, run_id, principal_id, include_internal=False)
            if run["status"] != "approved":
                raise Conflict("run is not approved")
            approval = connection.execute(
                """SELECT * FROM approvals WHERE run_id = ? AND approved_at IS NOT NULL
                   ORDER BY approved_at DESC LIMIT 1""",
                (run_id,),
            ).fetchone()
            plan_row = connection.execute(
                "SELECT plan_json FROM execution_plans WHERE plan_id = ? AND plan_version = ?",
                (run["plan_id"], run["plan_version"]),
            ).fetchone()
            stored_plan = ExecutionPlan.model_validate_json(plan_row["plan_json"])
            plan_matches = execution_plan_hash(stored_plan) == run["plan_hash"] == approval["plan_hash"]
            inputs_match = hash_json(json.loads(run["input_json"])) == run["input_hash"] == approval["input_hash"]
            expired = approval["expires_at"] <= iso_now()
            if not plan_matches or not inputs_match or expired or approval["consumed_at"] is not None:
                connection.execute("UPDATE approvals SET invalidated_at = ? WHERE approval_id = ?", (iso_now(), approval["approval_id"]))
                reason = "approval_expired" if expired else "approval_binding_changed"
                self._transition(connection, run_id, "approved", "awaiting_approval", actor=principal_id, reason=reason, event_type="approval_invalidated")
                challenge = self._new_approval_challenge(connection, run_id)
                changed = ApprovalBindingChanged(challenge)
            else:
                connection.execute("UPDATE approvals SET consumed_at = ? WHERE approval_id = ?", (iso_now(), approval["approval_id"]))
                self._transition(connection, run_id, "approved", "queued", actor=principal_id, event_type="run_queued")
                return self._read_run(connection, run_id, principal_id, include_internal=False)
        if changed:
            raise changed
        raise Conflict("approval could not be consumed")

    def cancel(self, run_id: str, principal_id: str) -> dict[str, Any]:
        with self._transaction(audited=True) as connection:
            run = self._owned_row(connection, run_id, principal_id)
            if run["status"] == "cancelled":
                return self._read_run(connection, run_id, principal_id, include_internal=False)
            if run["status"] in {"draft", "validating", "awaiting_approval", "approved", "queued"}:
                self._transition(connection, run_id, run["status"], "cancelled", actor=principal_id, event_type="run_cancelled")
            elif run["status"] == "running":
                connection.execute("UPDATE execution_runs SET cancel_requested = 1, updated_at = ? WHERE run_id = ?", (iso_now(), run_id))
                self._audit(connection, run_id, "cancellation_requested", actor=principal_id)
            else:
                raise Conflict("run can no longer be cancelled")
            return self._read_run(connection, run_id, principal_id, include_internal=False)

    def acquire_next_run(self, worker_id: str, *, lease_seconds: float = 30) -> dict[str, Any] | None:
        now = utc_now()
        expires = now + timedelta(seconds=lease_seconds)
        with self._transaction(audited=True) as connection:
            row = connection.execute(
                """SELECT * FROM execution_runs
                   WHERE status = 'queued' OR (status = 'running' AND lease_expires_at <= ?)
                   ORDER BY CASE status WHEN 'running' THEN 0 ELSE 1 END, created_at LIMIT 1""",
                (now.isoformat(),),
            ).fetchone()
            if not row:
                return None
            if row["status"] == "queued":
                self._transition(
                    connection,
                    row["run_id"],
                    "queued",
                    "running",
                    actor=worker_id,
                    event_type="worker_started",
                    extra_updates=", lease_owner = ?, lease_expires_at = ?, worker_attempts = worker_attempts + 1",
                    extra_parameters=(worker_id, expires.isoformat()),
                    data={"worker_id": worker_id},
                )
            else:
                previous = row["lease_owner"]
                connection.execute(
                    """UPDATE execution_runs SET lease_owner = ?, lease_expires_at = ?,
                       worker_attempts = worker_attempts + 1, updated_at = ? WHERE run_id = ?""",
                    (worker_id, expires.isoformat(), now.isoformat(), row["run_id"]),
                )
                self._audit(
                    connection,
                    row["run_id"],
                    "lease_recovered",
                    actor=worker_id,
                    data={"worker_id": worker_id, "recovered_from": previous},
                )
            return self._read_run(connection, row["run_id"], None, include_internal=True)

    def renew_lease(self, run_id: str, worker_id: str, lease_seconds: float) -> bool:
        expires = (utc_now() + timedelta(seconds=lease_seconds)).isoformat()
        with self._transaction() as connection:
            changed = connection.execute(
                """UPDATE execution_runs SET lease_expires_at = ?, updated_at = ?
                   WHERE run_id = ? AND status = 'running' AND lease_owner = ?""",
                (expires, iso_now(), run_id, worker_id),
            ).rowcount
        return bool(changed)

    def prepare_step_attempt(self, run_id: str, step_id: str, worker_id: str) -> tuple[str, dict[str, Any] | None]:
        with self._transaction(audited=True) as connection:
            run = self._owned_row(connection, run_id, None)
            if run["status"] != "running" or run["lease_owner"] != worker_id:
                raise Conflict("worker does not own the active lease")
            step = connection.execute("SELECT * FROM step_runs WHERE run_id = ? AND step_id = ?", (run_id, step_id)).fetchone()
            receipt = connection.execute(
                "SELECT * FROM adapter_receipts WHERE step_idempotency_key = ?", (step["step_idempotency_key"],)
            ).fetchone()
            if receipt:
                return receipt["status"], json.loads(receipt["receipt_json"])
            connection.execute(
                """UPDATE step_runs SET status = 'running', attempts = attempts + 1, started_at = ?
                   WHERE step_run_id = ?""",
                (iso_now(), step["step_run_id"]),
            )
            receipt_id = f"receipt_{uuid4().hex}"
            connection.execute(
                """INSERT INTO adapter_receipts
                   (receipt_id, run_id, step_id, step_idempotency_key, status, receipt_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'in_flight', '{}', ?, ?)""",
                (receipt_id, run_id, step_id, step["step_idempotency_key"], iso_now(), iso_now()),
            )
            self._audit(
                connection,
                run_id,
                "step_started",
                actor=worker_id,
                data={"worker_id": worker_id, "step_id": step_id, "operation_id": step["operation_id"], "receipt_id": receipt_id},
            )
            return "execute", {"receipt_id": receipt_id, "step_idempotency_key": step["step_idempotency_key"]}

    def finish_step(
        self,
        run_id: str,
        step_id: str,
        worker_id: str,
        *,
        status: str,
        receipt: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        with self._transaction(audited=True) as connection:
            run = self._owned_row(connection, run_id, None)
            if run["status"] != "running" or run["lease_owner"] != worker_id:
                raise Conflict("worker lost the active lease")
            step = connection.execute("SELECT * FROM step_runs WHERE run_id = ? AND step_id = ?", (run_id, step_id)).fetchone()
            connection.execute(
                """UPDATE step_runs SET status = ?, result_json = ?, error_code = ?, finished_at = ?
                   WHERE step_run_id = ?""",
                (status, canonical_json(receipt), error_code, iso_now(), step["step_run_id"]),
            )
            connection.execute(
                """UPDATE adapter_receipts SET status = ?, receipt_json = ?, updated_at = ?
                   WHERE step_idempotency_key = ?""",
                (status, canonical_json(receipt), iso_now(), step["step_idempotency_key"]),
            )
            self._audit(
                connection,
                run_id,
                "step_finished",
                actor=worker_id,
                data={"worker_id": worker_id, "step_id": step_id, "operation_id": step["operation_id"]},
            )

    def block_step(self, run_id: str, step_id: str, worker_id: str, reason: str) -> None:
        with self._transaction(audited=True) as connection:
            step = connection.execute("SELECT * FROM step_runs WHERE run_id = ? AND step_id = ?", (run_id, step_id)).fetchone()
            if step["status"] != "pending":
                return
            connection.execute(
                "UPDATE step_runs SET status = 'blocked', error_code = ?, finished_at = ? WHERE step_run_id = ?",
                (reason, iso_now(), step["step_run_id"]),
            )
            self._audit(connection, run_id, "step_blocked", actor=worker_id, data={"step_id": step_id, "reason": reason})

    def finalize_run(self, run_id: str, worker_id: str, target: str, *, guidance: str | None = None) -> None:
        with self._transaction(audited=True) as connection:
            run = self._owned_row(connection, run_id, None)
            if run["status"] != "running" or run["lease_owner"] != worker_id:
                raise Conflict("worker does not own the active lease")
            manual = target in {"partially_succeeded", "outcome_unknown", "awaiting_user"}
            self._transition(
                connection,
                run_id,
                "running",
                target,
                actor=worker_id,
                event_type="run_finished",
                extra_updates=", lease_owner = NULL, lease_expires_at = NULL, manual_recovery_required = ?, recovery_guidance = ?",
                extra_parameters=(int(manual), guidance),
                data={"worker_id": worker_id, "manual_recovery_required": manual},
            )

    def is_cancel_requested(self, run_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute("SELECT cancel_requested FROM execution_runs WHERE run_id = ?", (run_id,)).fetchone()
        return bool(row and row["cancel_requested"])

    def count_receipts(self, run_id: str) -> int:
        with self._connection() as connection:
            return connection.execute("SELECT COUNT(*) FROM adapter_receipts WHERE run_id = ?", (run_id,)).fetchone()[0]

    def reconcile_from_receipt(self, run_id: str, principal_id: str) -> dict[str, Any]:
        with self._transaction(audited=True) as connection:
            run = self._owned_row(connection, run_id, principal_id)
            if run["status"] != "outcome_unknown":
                raise Conflict("run does not require reconciliation")
            receipt = connection.execute(
                """SELECT * FROM adapter_receipts WHERE run_id = ? AND status = 'outcome_unknown'
                   ORDER BY created_at DESC LIMIT 1""",
                (run_id,),
            ).fetchone()
            if not receipt:
                raise Conflict("no adapter receipt is available")
            projected = json.loads(receipt["receipt_json"])
            target = projected.get("reconciled_status")
            if target not in {"succeeded", "failed", "awaiting_user"}:
                raise Conflict("receipt cannot determine the outcome")
            step = connection.execute(
                "SELECT * FROM step_runs WHERE run_id = ? AND step_id = ?", (run_id, receipt["step_id"])
            ).fetchone()
            connection.execute(
                "UPDATE step_runs SET status = ?, finished_at = ? WHERE step_run_id = ?",
                (target, iso_now(), step["step_run_id"]),
            )
            self._audit(
                connection,
                run_id,
                "receipt_reconciled",
                actor=principal_id,
                data={"step_id": receipt["step_id"], "receipt_id": receipt["receipt_id"]},
            )
            self._transition(connection, run_id, "outcome_unknown", target, actor=principal_id, event_type="reconciliation_finished")
            connection.execute(
                "UPDATE adapter_receipts SET status = ?, updated_at = ? WHERE receipt_id = ?",
                (target, iso_now(), receipt["receipt_id"]),
            )
            return self._read_run(connection, run_id, principal_id, include_internal=False)

    # Explicit internal revision hook for future trusted plan-management code. It is not exposed over HTTP.
    # Start still rechecks the approval binding, so even trusted revisions cannot reuse an approval.
    def revise_run_material(
        self, run_id: str, *, user_inputs: dict[str, Any] | None = None, plan_hash: str | None = None
    ) -> None:
        with self._transaction() as connection:
            if user_inputs is not None:
                connection.execute(
                    "UPDATE execution_runs SET input_json = ?, updated_at = ? WHERE run_id = ?",
                    (canonical_json(user_inputs), iso_now(), run_id),
                )
            if plan_hash is not None:
                connection.execute(
                    "UPDATE execution_runs SET plan_hash = ?, updated_at = ? WHERE run_id = ?",
                    (plan_hash, iso_now(), run_id),
                )

    def force_challenge_expired(self, run_id: str) -> None:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE approvals SET expires_at = ? WHERE approval_id = (SELECT approval_id FROM approvals WHERE run_id = ? ORDER BY created_at DESC LIMIT 1)",
                ((utc_now() - timedelta(seconds=1)).isoformat(), run_id),
            )

    def renew_approval_challenge(self, run_id: str, principal_id: str) -> dict[str, Any]:
        with self._transaction(audited=True) as connection:
            run = self._owned_row(connection, run_id, principal_id)
            if run["status"] != "awaiting_approval":
                raise Conflict("run is not awaiting approval")
            connection.execute(
                "UPDATE approvals SET invalidated_at = ? WHERE run_id = ? AND invalidated_at IS NULL",
                (iso_now(), run_id),
            )
            challenge = self._new_approval_challenge(connection, run_id)
            self._audit(connection, run_id, "approval_challenge_issued", actor=principal_id)
            response = self._read_run(connection, run_id, principal_id, include_internal=False)
            response["approval_challenge"] = challenge
            return response

    def force_lease_expired(self, run_id: str) -> None:
        with self._transaction() as connection:
            connection.execute(
                "UPDATE execution_runs SET lease_expires_at = ? WHERE run_id = ?",
                ((utc_now() - timedelta(seconds=1)).isoformat(), run_id),
            )

from __future__ import annotations

import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from conftest import approve_run, build_plan, create_run, login, plan_hash, start_run


def test_execution_surface_does_not_enable_cors(client):
    response = client.options(
        "/execution-runs",
        headers={"Origin": "https://attacker.invalid", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_state_machine_rejects_invalid_transition():
    from domain.state_machine import InvalidTransition, require_transition

    with pytest.raises(InvalidTransition):
        require_transition("awaiting_approval", "running")


@pytest.mark.parametrize("field,value", [("target_url", "http://127.0.0.1/admin"), ("method", "DELETE"), ("code", "import os")])
def test_plan_rejects_client_controlled_targets(field, value, client):
    headers = login(client)
    plan = build_plan()
    plan["steps"][0][field] = value
    plan["content_hash"] = plan_hash(plan)
    response = client.post("/execution-plans/validate", headers=headers, json={"plan": plan, "user_inputs": {"subject": "safe"}})
    assert response.status_code == 422


def test_unregistered_operation_is_blocked(client):
    headers = login(client)
    plan = build_plan(["not.registered.v1"])
    response = client.post("/execution-plans/validate", headers=headers, json={"plan": plan, "user_inputs": {"subject": "safe"}})
    assert response.status_code == 400
    assert response.json()["detail"] == "plan validation failed"


def test_unauthenticated_create_approve_and_read_are_blocked(client):
    headers = login(client)
    run, _ = create_run(client, headers)
    create_response = client.post(
        "/execution-runs",
        headers={"Idempotency-Key": "unauthenticated"},
        json={"plan_id": run["plan_id"], "plan_version": 1, "content_hash": run["plan_hash"], "user_inputs": {"subject": "safe"}},
    )
    assert create_response.status_code == 401
    assert client.get(f"/execution-runs/{run['run_id']}").status_code == 401
    assert client.post(f"/execution-runs/{run['run_id']}/approvals", json={"challenge": "x", "reauth_password": "x"}).status_code == 401
    assert client.post(f"/execution-runs/{run['run_id']}/start").status_code == 401


def test_other_principal_cannot_read_or_approve(client):
    alice = login(client, "alice")
    bob = login(client, "bob")
    run, _ = create_run(client, alice)
    assert client.get(f"/execution-runs/{run['run_id']}", headers=bob).status_code == 403
    response = client.post(
        f"/execution-runs/{run['run_id']}/approvals",
        headers=bob,
        json={"challenge": run["approval_challenge"], "reauth_password": "bob-password"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("changed", ["inputs", "plan"])
def test_approval_is_invalidated_when_bound_material_changes(client, app, changed):
    headers = login(client)
    run, _ = create_run(client, headers)
    approve_run(client, headers, run)
    if changed == "inputs":
        app.state.database.revise_run_material(run["run_id"], user_inputs={"subject": "revised request"})
    else:
        app.state.database.revise_run_material(run["run_id"], plan_hash="f" * 64)
    response = client.post(f"/execution-runs/{run['run_id']}/start", headers=headers)
    assert response.status_code == 409
    current = client.get(f"/execution-runs/{run['run_id']}", headers=headers).json()
    assert current["status"] == "awaiting_approval"
    assert current["status_reason"] == "approval_binding_changed"


def test_approval_expiry_and_replay_are_blocked(client, app):
    headers = login(client)
    replay_run, _ = create_run(client, headers)
    approve_run(client, headers, replay_run)
    replay = client.post(
        f"/execution-runs/{replay_run['run_id']}/approvals",
        headers=headers,
        json={"challenge": replay_run["approval_challenge"], "reauth_password": "alice-password"},
    )
    assert replay.status_code == 409

    expired_run, _ = create_run(client, headers)
    app.state.database.force_challenge_expired(expired_run["run_id"])
    expired = client.post(
        f"/execution-runs/{expired_run['run_id']}/approvals",
        headers=headers,
        json={"challenge": expired_run["approval_challenge"], "reauth_password": "alice-password"},
    )
    assert expired.status_code == 409
    renewed = client.post(f"/execution-runs/{expired_run['run_id']}/approval-challenges", headers=headers)
    assert renewed.status_code == 201
    approve_run(client, headers, renewed.json())

    approved_then_expired, _ = create_run(client, headers)
    approve_run(client, headers, approved_then_expired)
    app.state.database.force_challenge_expired(approved_then_expired["run_id"])
    start = client.post(f"/execution-runs/{approved_then_expired['run_id']}/start", headers=headers)
    assert start.status_code == 409
    current = client.get(f"/execution-runs/{approved_then_expired['run_id']}", headers=headers).json()
    assert current["status"] == "awaiting_approval"
    assert current["status_reason"] == "approval_expired"


def test_same_idempotency_key_concurrently_creates_and_executes_once(app):
    with TestClient(app) as setup_client:
        headers = login(setup_client)
        plan = build_plan()
        inputs = {"subject": "concurrent request"}
        validated = setup_client.post("/execution-plans/validate", headers=headers, json={"plan": plan, "user_inputs": inputs})
        assert validated.status_code == 200

        def request_run() -> tuple[int, dict]:
            with TestClient(app) as concurrent_client:
                response = concurrent_client.post(
                    "/execution-runs",
                    headers={**headers, "Idempotency-Key": "same-key"},
                    json={"plan_id": plan["plan_id"], "plan_version": 1, "content_hash": plan["content_hash"], "user_inputs": inputs},
                )
                return response.status_code, response.json()

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: request_run(), range(8)))
        assert {body["run_id"] for _, body in results}.__len__() == 1
        assert {status for status, _ in results} <= {200, 201}
        created_body = next(body for status, body in results if status == 201)
        run_id = created_body["run_id"]
        run = created_body
        approve_run(setup_client, headers, run)
        start_run(setup_client, headers, run_id)

        from worker.runner import WorkerRunner

        runners = [WorkerRunner(app.state.database, app.state.operation_registry, worker_id=f"worker-{index}") for index in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda runner: runner.run_once(), runners))
        assert app.state.operation_registry.adapter.invocation_count("dummy.write.v1") == 1
        assert app.state.database.count_receipts(run_id) == 1


def test_expired_worker_lease_is_recovered_without_duplicate_execution(client, app):
    headers = login(client)
    run, _ = create_run(client, headers)
    approve_run(client, headers, run)
    start_run(client, headers, run["run_id"])
    leased = app.state.database.acquire_next_run("dead-worker", lease_seconds=30)
    assert leased and leased["status"] == "running"
    app.state.database.force_lease_expired(run["run_id"])

    from worker.runner import WorkerRunner

    assert WorkerRunner(app.state.database, app.state.operation_registry, worker_id="recovery-worker").run_once()
    current = client.get(f"/execution-runs/{run['run_id']}", headers=headers).json()
    assert current["status"] == "succeeded"
    events = client.get(f"/execution-runs/{run['run_id']}/events", headers=headers).json()
    assert any(event["event_type"] == "lease_recovered" for event in events)
    assert app.state.operation_registry.adapter.invocation_count("dummy.write.v1") == 1


def test_crash_after_attempt_marker_becomes_unknown_without_resubmission(client, app):
    headers = login(client)
    run, _ = create_run(client, headers)
    approve_run(client, headers, run)
    start_run(client, headers, run["run_id"])
    leased = app.state.database.acquire_next_run("dead-during-call", lease_seconds=30)
    assert leased
    state, _ = app.state.database.prepare_step_attempt(run["run_id"], "step-1", "dead-during-call")
    assert state == "execute"
    app.state.database.force_lease_expired(run["run_id"])

    from worker.runner import WorkerRunner

    WorkerRunner(app.state.database, app.state.operation_registry, worker_id="uncertain-recovery").run_once()
    current = client.get(f"/execution-runs/{run['run_id']}", headers=headers).json()
    assert current["status"] == "outcome_unknown"
    assert current["steps"][0]["error_code"] == "crash_during_adapter_call"
    assert app.state.operation_registry.adapter.invocation_count("dummy.write.v1") == 0


def test_timeout_write_is_not_retried(client, app):
    headers = login(client)
    run, _ = create_run(client, headers, plan=build_plan(["dummy.timeout-write.v1"], timeout_seconds=0.02))
    approve_run(client, headers, run)
    start_run(client, headers, run["run_id"])

    from worker.runner import WorkerRunner

    runner = WorkerRunner(app.state.database, app.state.operation_registry, worker_id="timeout-worker")
    assert runner.run_once()
    assert not runner.run_once()
    current = client.get(f"/execution-runs/{run['run_id']}", headers=headers).json()
    assert current["status"] == "outcome_unknown"
    assert app.state.operation_registry.adapter.invocation_count("dummy.timeout-write.v1") == 1


def test_registered_safe_retry_reuses_step_key_and_succeeds(client, app):
    headers = login(client)
    run, _ = create_run(client, headers, plan=build_plan(["dummy.transient.v1"]))
    approve_run(client, headers, run)
    start_run(client, headers, run["run_id"])

    from worker.runner import WorkerRunner

    WorkerRunner(app.state.database, app.state.operation_registry, worker_id="retry-worker").run_once()
    current = client.get(f"/execution-runs/{run['run_id']}", headers=headers).json()
    assert current["status"] == "succeeded"
    assert app.state.operation_registry.adapter.invocation_count("dummy.transient.v1") == 2
    assert app.state.database.count_receipts(run["run_id"]) == 1


def test_failed_dependency_blocks_following_step(client, app):
    headers = login(client)
    plan = build_plan(["dummy.fail.v1", "dummy.write.v1"], dependencies=[[], ["step-1"]])
    run, _ = create_run(client, headers, plan=plan)
    approve_run(client, headers, run)
    start_run(client, headers, run["run_id"])

    from worker.runner import WorkerRunner

    WorkerRunner(app.state.database, app.state.operation_registry, worker_id="dependency-worker").run_once()
    current = client.get(f"/execution-runs/{run['run_id']}", headers=headers).json()
    statuses = {step["step_id"]: step["status"] for step in current["steps"]}
    assert statuses == {"step-1": "failed", "step-2": "blocked"}
    assert app.state.operation_registry.adapter.invocation_count("dummy.write.v1") == 0


def test_partial_success_has_manual_recovery_guidance(client, app):
    headers = login(client)
    plan = build_plan(["dummy.write.v1", "dummy.fail.v1"])
    run, _ = create_run(client, headers, plan=plan)
    approve_run(client, headers, run)
    start_run(client, headers, run["run_id"])

    from worker.runner import WorkerRunner

    WorkerRunner(app.state.database, app.state.operation_registry, worker_id="partial-worker").run_once()
    current = client.get(f"/execution-runs/{run['run_id']}", headers=headers).json()
    assert current["status"] == "partially_succeeded"
    assert current["manual_recovery_required"] is True
    assert current["recovery_guidance"]


def test_secret_and_pii_do_not_leak_to_response_error_audit_or_logs(client, caplog):
    headers = login(client)
    raw_secret = "VERY-SECRET-12345"
    caplog.set_level(logging.DEBUG)
    plan = build_plan()
    response = client.post(
        "/execution-plans/validate",
        headers=headers,
        json={"plan": plan, "user_inputs": {"subject": "safe", "password": raw_secret, "resident_id": "900101-1234567"}},
    )
    assert response.status_code == 400
    combined = response.text + caplog.text
    assert raw_secret not in combined
    assert "900101-1234567" not in combined

    plan["password"] = raw_secret
    reflected = client.post(
        "/execution-plans/validate",
        headers=headers,
        json={"plan": plan, "user_inputs": {"subject": "safe"}},
    )
    assert reflected.status_code == 422
    assert raw_secret not in reflected.text


def test_audit_events_are_append_only_and_status_cannot_bypass_audit(client, app):
    headers = login(client)
    run, _ = create_run(client, headers)
    before = client.get(f"/execution-runs/{run['run_id']}/events", headers=headers).json()
    approve_run(client, headers, run)
    after = client.get(f"/execution-runs/{run['run_id']}/events", headers=headers).json()
    assert len(after) > len(before)
    assert [event["sequence"] for event in after] == list(range(1, len(after) + 1))
    with sqlite3.connect(app.state.database.path) as connection:
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("UPDATE audit_events SET event_type = 'tampered'")
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("DELETE FROM audit_events")
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("UPDATE execution_runs SET status = 'succeeded' WHERE run_id = ?", (run["run_id"],))
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("UPDATE execution_plans SET plan_json = '{}' WHERE plan_id = ?", (run["plan_id"],))


@pytest.mark.parametrize(
    "attack",
    ["http://169.254.169.254/latest/meta-data", "../../Windows/System32", "safe; whoami", "$(Get-ChildItem)", "C:\\Windows\\win.ini"],
)
def test_ssrf_path_traversal_and_command_injection_inputs_are_blocked(client, attack):
    headers = login(client)
    plan = build_plan()
    response = client.post("/execution-plans/validate", headers=headers, json={"plan": plan, "user_inputs": {"subject": attack}})
    assert response.status_code == 400
    assert attack not in response.text


@pytest.mark.parametrize("operation_id", ["dummy.manual.v1", "dummy.linkout.v1"])
def test_manual_and_linkout_are_awaiting_user_not_succeeded(client, app, operation_id):
    headers = login(client)
    run, _ = create_run(client, headers, plan=build_plan([operation_id]))
    approve_run(client, headers, run)
    start_run(client, headers, run["run_id"])

    from worker.runner import WorkerRunner

    WorkerRunner(app.state.database, app.state.operation_registry, worker_id="handoff-worker").run_once()
    current = client.get(f"/execution-runs/{run['run_id']}", headers=headers).json()
    assert current["status"] == "awaiting_user"
    assert current["steps"][0]["status"] == "awaiting_user"


def test_adapter_receipt_drives_reconciliation(client, app):
    headers = login(client)
    run, _ = create_run(client, headers, plan=build_plan(["dummy.unknown-reconcilable.v1"]))
    approve_run(client, headers, run)
    start_run(client, headers, run["run_id"])

    from worker.runner import WorkerRunner

    WorkerRunner(app.state.database, app.state.operation_registry, worker_id="unknown-worker").run_once()
    assert client.get(f"/execution-runs/{run['run_id']}", headers=headers).json()["status"] == "outcome_unknown"
    reconciled = client.post(f"/execution-runs/{run['run_id']}/reconcile", headers=headers)
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["status"] == "succeeded"
    events = client.get(f"/execution-runs/{run['run_id']}/events", headers=headers).json()
    assert any(event["event_type"] == "receipt_reconciled" for event in events)


def test_queued_run_can_be_cancelled_before_adapter_execution(client, app):
    headers = login(client)
    run, _ = create_run(client, headers)
    approve_run(client, headers, run)
    start_run(client, headers, run["run_id"])
    cancelled = client.post(f"/execution-runs/{run['run_id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    from worker.runner import WorkerRunner

    assert not WorkerRunner(app.state.database, app.state.operation_registry, worker_id="cancel-worker").run_once()
    assert app.state.operation_registry.adapter.invocation_count("dummy.write.v1") == 0

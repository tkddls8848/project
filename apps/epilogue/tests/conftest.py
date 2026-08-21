from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def plan_hash(plan: dict) -> str:
    material = dict(plan)
    material.pop("content_hash", None)
    return hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest()


def build_plan(
    operation_ids: list[str] | None = None,
    *,
    dependencies: list[list[str]] | None = None,
    timeout_seconds: float = 1.0,
) -> dict:
    operation_ids = operation_ids or ["dummy.write.v1"]
    dependencies = dependencies or [[] for _ in operation_ids]
    now = datetime.now(timezone.utc)
    steps = []
    for index, operation_id in enumerate(operation_ids):
        step_id = f"step-{index + 1}"
        steps.append(
            {
                "step_id": step_id,
                "operation_id": operation_id,
                "operation_version": "1.0",
                "depends_on": dependencies[index],
                "input_refs": {"subject": "user_input.subject"},
                "risk_level": "high" if "write" in operation_id else "medium",
                "timeout_seconds": timeout_seconds,
            }
        )
    plan = {
        "schema_version": "1.0",
        "plan_id": f"plan-{uuid4().hex}",
        "plan_version": 1,
        "content_hash": "",
        "source_scenario_id": "scenario-test-1",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "steps": steps,
        "required_approval_policy": "session_reauth",
        "evidence_refs": [
            {
                "document_id": "doc-1",
                "verified_at": now.isoformat(),
                "validation_result": "verified",
            }
        ],
    }
    plan["content_hash"] = plan_hash(plan)
    return plan


@pytest.fixture
def app(tmp_path):
    from api.main import create_app

    return create_app(
        database_path=tmp_path / "executor.sqlite3",
        local_users={"alice": "alice-password", "bob": "bob-password"},
        approval_ttl_seconds=60,
        session_ttl_seconds=3600,
    )


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, username: str = "alice", password: str | None = None) -> dict[str, str]:
    password = password or f"{username}-password"
    response = client.post("/auth/sessions", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_run(
    client: TestClient,
    headers: dict[str, str],
    *,
    plan: dict | None = None,
    inputs: dict | None = None,
    idempotency_key: str | None = None,
) -> tuple[dict, dict]:
    plan = plan or build_plan()
    inputs = inputs or {"subject": "safe request"}
    validated = client.post(
        "/execution-plans/validate",
        headers=headers,
        json={"plan": plan, "user_inputs": inputs},
    )
    assert validated.status_code == 200, validated.text
    response = client.post(
        "/execution-runs",
        headers={**headers, "Idempotency-Key": idempotency_key or f"idem-{uuid4().hex}"},
        json={
            "plan_id": plan["plan_id"],
            "plan_version": plan["plan_version"],
            "content_hash": plan["content_hash"],
            "user_inputs": inputs,
        },
    )
    assert response.status_code in {200, 201}, response.text
    return response.json(), plan


def approve_run(client: TestClient, headers: dict[str, str], run: dict, password: str = "alice-password") -> dict:
    response = client.post(
        f"/execution-runs/{run['run_id']}/approvals",
        headers=headers,
        json={"challenge": run["approval_challenge"], "reauth_password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


def start_run(client: TestClient, headers: dict[str, str], run_id: str) -> dict:
    response = client.post(f"/execution-runs/{run_id}/start", headers=headers)
    assert response.status_code == 202, response.text
    return response.json()

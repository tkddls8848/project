import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ExecutionPlan


FIXTURE_PLAN = Path(__file__).resolve().parent.parent / "data" / "demo_execution_plan.json"


def build_payload(approved: bool = False, include_all_inputs: bool = True):
    plan = ExecutionPlan(**json.loads(FIXTURE_PLAN.read_text(encoding="utf-8")))
    user_inputs = {
        "applicant_name": "홍길동",
        "birth_date": "1940-01-01",
        "region": "서울특별시 종로구",
        "income_type": "기초연금",
        "identity_token": "dummy-identity-token",
    }
    if not include_all_inputs:
        user_inputs.pop("identity_token")
    return {
        "plan": plan.model_dump(),
        "user_inputs": user_inputs,
        "approval": {
            "approved": approved,
            "approver": "tester",
            "approval_token": "dummy-approval-token" if approved else None,
        },
    }


def test_dry_run_detects_missing_inputs():
    client = TestClient(app)
    response = client.post("/execute/dry-run", json=build_payload(include_all_inputs=False))
    assert response.status_code == 200
    body = response.json()
    assert body["executable"] is False
    assert "prepare_gov24_application: missing input 'identity_token'" in body["blockers"]


def test_execute_requires_approval():
    client = TestClient(app)
    response = client.post("/execute", json=build_payload(approved=False))
    assert response.status_code == 403
    assert response.json()["detail"]["status"] == "blocked"


def test_execute_with_approval_writes_run_record():
    client = TestClient(app)
    response = client.post("/execute", json=build_payload(approved=True))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert len(body["executed_steps"]) == 3
    assert body["user_inputs"]["identity_token"] == "***"

    run_response = client.get(f"/runs/{body['run_id']}")
    assert run_response.status_code == 200
    assert run_response.json()["run_id"] == body["run_id"]


def test_demo_plan_endpoint():
    client = TestClient(app)
    response = client.get("/demo/plan")
    assert response.status_code == 200
    assert response.json()["plan_id"] == "demo-parent-medical-transport-001"

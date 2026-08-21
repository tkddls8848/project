"""승인 게이트 세분화·마스킹 범위·감사 기록 격리 테스트."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.executor import mask_inputs
from app.main import app
from app.schemas import ExecutionPlan

FIXTURE_PLAN = Path(__file__).resolve().parent.parent / "data" / "demo_execution_plan.json"

FULL_INPUTS = {
    "applicant_name": "홍길동",
    "birth_date": "1940-01-01",
    "region": "서울특별시 종로구",
    "income_type": "기초연금",
    "identity_token": "dummy-identity-token",
}


def load_plan() -> ExecutionPlan:
    return ExecutionPlan(**json.loads(FIXTURE_PLAN.read_text(encoding="utf-8")))


def build_payload(approved=True, approver="tester", inputs=None):
    return {
        "plan": load_plan().model_dump(),
        "user_inputs": dict(FULL_INPUTS if inputs is None else inputs),
        "approval": {
            "approved": approved,
            "approver": approver,
            "approval_token": "dummy-approval-token" if approved else None,
        },
    }


# ── 승인 게이트 세분화 ───────────────────────────────────────────────────────

def test_execute_approved_without_approver_is_blocked():
    client = TestClient(app)
    response = client.post("/execute", json=build_payload(approved=True, approver=None))
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["status"] == "blocked"
    assert detail["status_reason"] == "approver_missing"
    assert detail["executed_steps"] == []


def test_execute_approved_with_blank_approver_is_blocked():
    client = TestClient(app)
    response = client.post("/execute", json=build_payload(approved=True, approver="   "))
    assert response.status_code == 403
    assert response.json()["detail"]["status_reason"] == "approver_missing"


def test_execute_not_approved_reports_reason():
    client = TestClient(app)
    response = client.post("/execute", json=build_payload(approved=False))
    assert response.status_code == 403
    assert response.json()["detail"]["status_reason"] == "approval_missing"


def test_execute_with_missing_input_is_400_dry_run_blocked():
    inputs = dict(FULL_INPUTS)
    inputs.pop("identity_token")
    client = TestClient(app)
    response = client.post("/execute", json=build_payload(inputs=inputs))
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["status_reason"] == "dry_run_blocked"
    assert any("identity_token" in blocker for blocker in detail["dry_run"]["blockers"])


def test_api_step_without_target_url_blocks_dry_run():
    plan = load_plan()
    plan.steps[0].target_url = None
    payload = build_payload()
    payload["plan"] = plan.model_dump()
    client = TestClient(app)
    response = client.post("/execute/dry-run", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["executable"] is False
    assert any("no target_url" in blocker for blocker in body["blockers"])


# ── 차단도 감사 기록을 남긴다 ────────────────────────────────────────────────

def test_blocked_execution_still_writes_audit_record(isolated_runs_dir):
    client = TestClient(app)
    response = client.post("/execute", json=build_payload(approved=False))
    run_id = response.json()["detail"]["run_id"]
    saved = json.loads((isolated_runs_dir / f"{run_id}.json").read_text(encoding="utf-8"))
    assert saved["status"] == "blocked"
    assert saved["user_inputs"]["identity_token"] == "***"


# ── dummy 실행 명시 ──────────────────────────────────────────────────────────

def test_run_record_marks_dummy_executor():
    client = TestClient(app)
    response = client.post("/execute", json=build_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["executor_mode"] == "dummy"
    api_steps = [s for s in body["executed_steps"] if s["execution_mode"] == "api"]
    assert api_steps and api_steps[0]["receipt_id"].startswith("DUMMY-GOV-")


def test_health_and_index_expose_dummy_mode():
    client = TestClient(app)
    assert client.get("/health").json()["mode"] == "dummy"
    root = client.get("/").json()
    assert root["executor_mode"] == "dummy"
    assert "No real government submission" in root["notice"]


# ── 마스킹 범위 ──────────────────────────────────────────────────────────────

def test_mask_inputs_handles_nested_structures():
    masked = mask_inputs(
        {
            "region": "서울",
            "profile": {
                "phone": "010-0000-0000",
                "nickname": "gildong",
                "contacts": [{"email": "a@b.c", "label": "home"}],
            },
            "attachments": [{"documents": ["소득증빙"], "note": "ok"}],
        }
    )
    assert masked["region"] == "서울"
    assert masked["profile"]["phone"] == "***"
    assert masked["profile"]["nickname"] == "gildong"
    assert masked["profile"]["contacts"][0]["email"] == "***"
    assert masked["profile"]["contacts"][0]["label"] == "home"
    assert masked["attachments"][0]["documents"] == "***"
    assert masked["attachments"][0]["note"] == "ok"


def test_mask_inputs_covers_credential_suffixes():
    masked = mask_inputs(
        {
            "service_key": "raw-api-key",
            "session_token": "raw-token",
            "db_password": "raw-pass",
            "client_secret": "raw-secret",
            "count": 3,
        }
    )
    assert masked["service_key"] == "***"
    assert masked["session_token"] == "***"
    assert masked["db_password"] == "***"
    assert masked["client_secret"] == "***"
    assert masked["count"] == 3


def test_completed_run_masks_pii_in_record_and_payload():
    client = TestClient(app)
    body = client.post("/execute", json=build_payload()).json()
    assert body["user_inputs"]["applicant_name"] == "***"
    assert body["user_inputs"]["birth_date"] == "***"
    assert body["user_inputs"]["identity_token"] == "***"
    assert body["user_inputs"]["region"] == "서울특별시 종로구"
    api_step = next(s for s in body["executed_steps"] if s["execution_mode"] == "api")
    submitted = api_step["response_data"]["submitted_payload"]
    assert submitted["name"] == "***"
    assert "홍길동" not in json.dumps(body, ensure_ascii=False)
    assert "dummy-identity-token" not in json.dumps(body, ensure_ascii=False)


# ── run 조회 ─────────────────────────────────────────────────────────────────

def test_get_missing_run_returns_404():
    client = TestClient(app)
    assert client.get("/runs/run_does_not_exist").status_code == 404

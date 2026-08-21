from fastapi.testclient import TestClient

from app.agent import _Run
from app.main import agent_runs, app
from app.schemas import AgentRunRequest, DesignResponse, StageRecord


def make_completed_run(run_id: str) -> _Run:
    result = DesignResponse(
        query="미세먼지 알림 서비스",
        selected_service_ids=["openapi_new:1"],
        search={"results": [{"service_id": "openapi_new:1"}]},
        details=[{"service_id": "openapi_new:1", "name": "대기오염 정보"}],
        stages=[StageRecord(name="search", status="completed", message="-")],
    )
    return _Run(run_id=run_id, request=AgentRunRequest(query=result.query),
                status="completed", result=result)


def test_root_serves_orchestrator_front_page():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Nara Hermes Orchestrator" in response.text
    assert "Hermes가 Nara MCP" in response.text
    assert "데이터 리빌드" in response.text
    assert "/static/run_summary.js" in response.text


def test_static_assets_are_served():
    client = TestClient(app)

    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/run_summary.js").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_rebuild_endpoints_proxy_search_service(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def rebuild_search_index(self):
            return {"ok": True, "message": "CPU 빌드를 시작했습니다."}

        async def rebuild_status(self):
            return {"state": "running", "step": 2, "progress": 3, "total": 10}

    monkeypatch.setattr("app.main.NaraClient", FakeClient)
    client = TestClient(app)

    assert client.post("/data/rebuild").json()["ok"] is True
    assert client.get("/data/rebuild/status").json()["state"] == "running"


def test_favicon_is_handled_without_not_found():
    response = TestClient(app).get("/favicon.ico")

    assert response.status_code == 204


def test_flow_export_requires_a_known_run():
    response = TestClient(app).get("/agent/design-runs/unknown/flow")

    assert response.status_code == 404


def test_flow_export_rejects_unfinished_runs():
    run = make_completed_run("stillrunning01")
    run.status = "running"
    agent_runs._runs[run.run_id] = run
    try:
        response = TestClient(app).get(f"/agent/design-runs/{run.run_id}/flow")
    finally:
        agent_runs._runs.pop(run.run_id, None)

    assert response.status_code == 409


def test_flow_export_downloads_a_dashboard_flow_json():
    run = make_completed_run("abc123def456")
    agent_runs._runs[run.run_id] = run
    try:
        response = TestClient(app).get(f"/agent/design-runs/{run.run_id}/flow")
    finally:
        agent_runs._runs.pop(run.run_id, None)

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="nara-agent-abc123de.flow.json"'
    )
    flow = response.json()
    assert flow["format"] == "nara-dashboard-flow"
    assert flow["version"] == 1
    assert [node["data"]["apiId"] for node in flow["nodes"]] == ["1"]

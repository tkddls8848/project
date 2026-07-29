from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_root_serves_unified_workbench():
    response = client.get("/")
    assert response.status_code == 200
    assert response.encoding == "utf-8"
    assert "나라 API 워크벤치" in response.text
    assert "API를 찾고, 관계를 검토하고" in response.text


def test_static_assets_are_served():
    css = client.get("/static/styles.css")
    javascript = client.get("/static/app.js")
    assert css.status_code == 200
    assert javascript.status_code == 200
    assert css.headers["cache-control"] == "no-store, max-age=0"
    assert javascript.headers["cache-control"] == "no-store, max-age=0"
    assert "--accent: #0f9f72" in css.text
    assert ".analysis-status" in css.text
    assert "refreshRelations" in javascript.text
    assert "top_k: 20" in javascript.text
    assert "MAX_COMPOSE_SERVICES = 3" in javascript.text
    assert "beginAnalysisStatus" in javascript.text


def test_compose_ui_exposes_thinking_status_and_three_item_limit():
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="selectedCount">0 / 3' in response.text
    assert 'id="analysisStatus"' in response.text
    assert "QWEN 3.5 · THINKING ON" in response.text


def test_spa_fallback_and_missing_asset():
    assert client.get("/workspace").status_code == 200
    assert client.get("/missing.js").status_code == 404


def test_unavailable_upstream_has_stable_error_contract(monkeypatch):
    monkeypatch.setitem(main.UPSTREAMS, "search", "http://127.0.0.1:9")
    response = client.get("/api/search/health")
    assert response.status_code == 503
    assert response.json() == {
        "ok": False,
        "error_code": "UPSTREAM_UNAVAILABLE",
        "service": "search",
        "message": "문서 검색 서비스에 연결할 수 없습니다. 통합 실행기의 서비스 상태를 확인하세요.",
    }


def test_workspace_health_reports_offline_services(monkeypatch):
    monkeypatch.setitem(main.UPSTREAMS, "search", "http://127.0.0.1:9")
    monkeypatch.setitem(main.UPSTREAMS, "combiner", "http://127.0.0.1:9")
    response = client.get("/api/workspace/health")
    payload = response.json()
    assert response.status_code == 200
    assert payload["state"] == "offline"
    assert payload["services"]["search"]["reachable"] is False
    assert payload["services"]["combiner"]["reachable"] is False

"""MCP 서버 도구 등록·계약 테스트."""
import anyio
import httpx
import pytest

import server
from clients.search_client import SearchClient


@pytest.fixture(autouse=True)
def reset_client():
    server._client = None
    yield
    server._client = None


def install_fake_upstream(monkeypatch, handler):
    fake = SearchClient("http://search.test", timeout=1.0, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(server, "_client", fake)
    return fake


def list_tool_names() -> set[str]:
    tools = anyio.run(server.mcp.list_tools)
    return {tool.name for tool in tools}


def test_exactly_three_read_only_tools_registered():
    names = list_tool_names()
    assert names == {"search_public_services", "get_service_detail", "get_index_health"}


def test_no_write_or_execute_tools_exposed():
    forbidden = {"build", "execute", "compose", "write", "delete", "run"}
    for name in list_tool_names():
        for word in forbidden:
            assert word not in name.lower()


def test_tool_descriptions_mention_contract():
    tools = anyio.run(server.mcp.list_tools)
    detail = next(tool for tool in tools if tool.name == "get_service_detail")
    assert "openapi_new" in detail.description


def test_search_tool_returns_upstream_results(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={
            "query": "미세먼지",
            "results": [{"service_id": "openapi_new:15000001", "name": "대기오염정보"}],
            "diagnostics": {},
        })

    install_fake_upstream(monkeypatch, handler)
    payload = server.search_public_services("미세먼지", top_k=3)
    assert payload["ok"] is True
    assert payload["results"][0]["service_id"] == "openapi_new:15000001"


def test_search_then_detail_flow(monkeypatch):
    """검색 결과 service_id를 그대로 상세조회에 넣는 핵심 흐름."""
    def handler(request):
        if request.url.path == "/search":
            return httpx.Response(200, json={
                "query": "미세먼지",
                "results": [{"service_id": "openapi_new:15000001"}],
                "diagnostics": {},
            })
        assert request.url.path == "/services/openapi_new:15000001"
        return httpx.Response(200, json={"service_id": "openapi_new:15000001", "name": "대기오염정보"})

    install_fake_upstream(monkeypatch, handler)
    search_payload = server.search_public_services("미세먼지")
    service_id = search_payload["results"][0]["service_id"]
    detail_payload = server.get_service_detail(service_id)
    assert detail_payload["ok"] is True
    assert detail_payload["name"] == "대기오염정보"


def test_search_offline_returns_clear_connection_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("refused")

    install_fake_upstream(monkeypatch, handler)
    payload = server.search_public_services("미세먼지")
    assert payload["ok"] is False
    assert payload["error_code"] == "CONNECTION_FAILED"
    assert payload["retryable"] is True


def test_health_tool(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"ok": False, "services_total": 0, "index_error": "인덱스 없음", "diagnostics": {"index_exists": False}})

    install_fake_upstream(monkeypatch, handler)
    payload = server.get_index_health()
    assert payload["services_total"] == 0
    assert payload["diagnostics"]["index_exists"] is False

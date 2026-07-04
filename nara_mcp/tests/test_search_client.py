"""SearchClient의 성공·오류 변환 계약 테스트 (실제 네트워크 없이 MockTransport 사용)."""
import httpx
import pytest

from clients.search_client import SearchClient

BASE_URL = "http://search.test"


def make_client(handler) -> SearchClient:
    return SearchClient(BASE_URL, timeout=1.0, transport=httpx.MockTransport(handler))


# ── 성공 경로 ────────────────────────────────────────────────────────────────

def test_search_success_passthrough():
    def handler(request):
        assert request.url.path == "/search"
        assert request.method == "POST"
        return httpx.Response(200, json={
            "query": "미세먼지",
            "results": [{"service_id": "openapi_new:15000001", "name": "대기오염정보"}],
            "diagnostics": {"vector_candidates": 1},
        })

    payload = make_client(handler).search("미세먼지", top_k=5)
    assert payload["ok"] is True
    assert payload["service"] == "nara_search"
    assert payload["results"][0]["service_id"] == "openapi_new:15000001"


def test_detail_success_passthrough():
    def handler(request):
        assert request.url.path == "/services/openapi_new:15000001"
        return httpx.Response(200, json={"service_id": "openapi_new:15000001", "name": "대기오염정보"})

    payload = make_client(handler).get_service_detail("openapi_new:15000001")
    assert payload["ok"] is True
    assert payload["service_id"] == "openapi_new:15000001"


def test_health_success():
    def handler(request):
        assert request.url.path == "/health"
        return httpx.Response(200, json={"ok": True, "services_total": 3526, "build_state": "idle"})

    payload = make_client(handler).health()
    assert payload["ok"] is True
    assert payload["services_total"] == 3526


# ── 클라이언트 측 인자 검증 (upstream 호출 없음) ─────────────────────────────

def test_search_query_too_short_is_invalid_argument():
    def handler(request):  # 호출되면 실패
        raise AssertionError("upstream must not be called")

    payload = make_client(handler).search("a")
    assert payload["ok"] is False
    assert payload["error_code"] == "INVALID_ARGUMENT"


@pytest.mark.parametrize("top_k", [0, 21])
def test_search_top_k_out_of_range(top_k):
    def handler(request):
        raise AssertionError("upstream must not be called")

    payload = make_client(handler).search("미세먼지", top_k=top_k)
    assert payload["error_code"] == "INVALID_ARGUMENT"


def test_detail_empty_id_is_invalid_argument():
    def handler(request):
        raise AssertionError("upstream must not be called")

    payload = make_client(handler).get_service_detail("  ")
    assert payload["error_code"] == "INVALID_ARGUMENT"


# ── upstream 오류 변환 ───────────────────────────────────────────────────────

def test_search_error_contract_propagated():
    def handler(request):
        return httpx.Response(404, json={"ok": False, "error_code": "NOT_FOUND", "message": "service_id not found"})

    payload = make_client(handler).get_service_detail("openapi_new:99999999")
    assert payload["ok"] is False
    assert payload["error_code"] == "NOT_FOUND"
    assert payload["message"] == "service_id not found"
    assert payload["retryable"] is False


def test_unsupported_source_propagated():
    def handler(request):
        return httpx.Response(400, json={"ok": False, "error_code": "UNSUPPORTED_SOURCE", "message": "unsupported source prefix: filedata"})

    payload = make_client(handler).get_service_detail("filedata:123")
    assert payload["error_code"] == "UNSUPPORTED_SOURCE"


def test_service_unavailable_is_retryable():
    def handler(request):
        return httpx.Response(503, json={"ok": False, "error_code": "SERVICE_UNAVAILABLE", "message": "no detail data source"})

    payload = make_client(handler).get_service_detail("openapi_new:15000001")
    assert payload["error_code"] == "SERVICE_UNAVAILABLE"
    assert payload["retryable"] is True


def test_validation_422_is_invalid_argument():
    def handler(request):
        return httpx.Response(422, json={"detail": [{"loc": ["body", "query"], "msg": "too short"}]})

    payload = make_client(handler).search("정상 질의")
    assert payload["error_code"] == "INVALID_ARGUMENT"


def test_non_json_response_is_bad_upstream():
    def handler(request):
        return httpx.Response(200, content=b"<html>not json</html>")

    payload = make_client(handler).health()
    assert payload["ok"] is False
    assert payload["error_code"] == "BAD_UPSTREAM_RESPONSE"


def test_connect_error_is_clear_and_retryable():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    payload = make_client(handler).search("미세먼지")
    assert payload["ok"] is False
    assert payload["error_code"] == "CONNECTION_FAILED"
    assert payload["retryable"] is True
    assert "nara_search" in payload["message"]
    # 원문 예외·스택이 아니라 안내 문구만 노출한다
    assert "Traceback" not in payload["message"]


def test_timeout_is_retryable():
    def handler(request):
        raise httpx.ReadTimeout("timed out")

    payload = make_client(handler).search("미세먼지")
    assert payload["error_code"] == "TIMEOUT"
    assert payload["retryable"] is True


def test_plain_500_is_upstream_error():
    def handler(request):
        return httpx.Response(500, json={"detail": "internal"})

    payload = make_client(handler).health()
    assert payload["error_code"] == "UPSTREAM_ERROR"
    assert payload["retryable"] is True

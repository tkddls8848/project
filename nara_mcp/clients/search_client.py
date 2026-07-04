"""nara_search HTTP client.

Search의 Python 모듈을 import하지 않고 HTTP 계약만 사용한다.
모든 실패는 짧은 구조화 오류 dict로 변환한다:

    {"ok": false, "service": "nara_search", "error_code": "...",
     "message": "...", "retryable": bool}

stack trace, 로컬 절대 경로, 원문 예외는 반환하지 않는다.
"""
from typing import Any

import httpx

SERVICE_NAME = "nara_search"


def _error(error_code: str, message: str, retryable: bool = False) -> dict[str, Any]:
    return {
        "ok": False,
        "service": SERVICE_NAME,
        "error_code": error_code,
        "message": message,
        "retryable": retryable,
    }


class SearchClient:
    def __init__(self, base_url: str, timeout: float = 10.0, transport: httpx.BaseTransport | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    # ── HTTP 공통 처리 ───────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.ConnectError:
            return _error(
                "CONNECTION_FAILED",
                f"Search 서비스에 연결할 수 없습니다 ({self._base_url}). nara_search가 실행 중인지 확인하세요.",
                retryable=True,
            )
        except httpx.TimeoutException:
            return _error(
                "TIMEOUT",
                f"Search 응답 시간 초과 ({self._base_url}).",
                retryable=True,
            )
        except httpx.HTTPError as exc:
            return _error("TRANSPORT_ERROR", f"HTTP 호출 실패: {type(exc).__name__}", retryable=True)

        return self._to_payload(response)

    def _to_payload(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            return _error(
                "BAD_UPSTREAM_RESPONSE",
                f"Search가 JSON이 아닌 응답을 반환했습니다 (HTTP {response.status_code}).",
                retryable=response.status_code >= 500,
            )

        if response.status_code < 400:
            if isinstance(body, dict):
                return {"ok": True, "service": SERVICE_NAME, **body}
            return {"ok": True, "service": SERVICE_NAME, "data": body}

        # Search 오류 계약({ok,error_code,message}) 우선 전달
        if isinstance(body, dict) and body.get("error_code"):
            return _error(
                str(body["error_code"]),
                str(body.get("message") or "upstream error"),
                retryable=response.status_code >= 500,
            )

        # FastAPI validation(422) 등 detail 기반 오류
        if response.status_code == 422:
            return _error("INVALID_ARGUMENT", "요청 인자가 계약을 벗어났습니다 (query 2~300자, top_k 1~20).")
        if isinstance(body, dict) and body.get("detail"):
            detail = body["detail"]
            message = detail if isinstance(detail, str) else "upstream rejected the request"
            return _error("UPSTREAM_ERROR", str(message)[:200], retryable=response.status_code >= 500)

        return _error(
            "UPSTREAM_ERROR",
            f"Search 오류 (HTTP {response.status_code}).",
            retryable=response.status_code >= 500,
        )

    # ── 도구별 호출 ──────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5, use_vector: bool = True) -> dict[str, Any]:
        query = (query or "").strip()
        if not (2 <= len(query) <= 300):
            return _error("INVALID_ARGUMENT", "query는 2~300자여야 합니다.")
        if not (1 <= int(top_k) <= 20):
            return _error("INVALID_ARGUMENT", "top_k는 1~20이어야 합니다.")
        return self._request(
            "POST",
            "/search",
            json={"query": query, "top_k": int(top_k), "use_vector": bool(use_vector)},
        )

    def get_service_detail(self, service_id: str) -> dict[str, Any]:
        service_id = (service_id or "").strip()
        if not service_id:
            return _error("INVALID_ARGUMENT", "service_id가 비어 있습니다.")
        return self._request("GET", f"/services/{service_id}")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

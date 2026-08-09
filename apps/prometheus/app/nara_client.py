"""Async HTTP client for the existing Nara services."""

from __future__ import annotations

from types import TracebackType
from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings, get_settings


class NaraServiceError(RuntimeError):
    def __init__(self, service: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.service = service
        self.status_code = status_code


class NaraClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings or get_settings()
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=self.settings.request_timeout
        )

    async def __aenter__(self) -> "NaraClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def _request(
        self, service: str, method: str, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        try:
            response = await self._http.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise NaraServiceError(
                service, f"{service} 응답 시간 초과: 제한 시간을 확인하세요."
            ) from exc
        except httpx.HTTPError as exc:
            raise NaraServiceError(service, f"{service} 연결 실패: {exc}") from exc

        if response.is_error:
            try:
                body = response.json()
                message = (
                    body.get("message")
                    or body.get("detail")
                    or body.get("error")
                    or response.text
                )
            except ValueError:
                message = response.text or response.reason_phrase
            raise NaraServiceError(
                service,
                f"{service} 응답 오류: {message}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise NaraServiceError(
                service, f"{service}가 JSON이 아닌 응답을 반환했습니다."
            ) from exc

    async def health(self) -> dict[str, Any]:
        search = await self._request(
            "nara-search", "GET", f"{self.settings.search_url}/health"
        )
        combiner = await self._request(
            "nara-combiner", "GET", f"{self.settings.combiner_url}/health"
        )
        return {"search": search, "combiner": combiner}

    async def search(
        self, query: str, top_k: int = 5, use_vector: bool = True
    ) -> dict[str, Any]:
        return await self._request(
            "nara-search",
            "POST",
            f"{self.settings.search_url}/search",
            json={"query": query, "top_k": top_k, "use_vector": use_vector},
        )

    async def detail(self, service_id: str) -> dict[str, Any]:
        encoded_id = quote(service_id, safe=":")
        return await self._request(
            "nara-search",
            "GET",
            f"{self.settings.search_url}/services/{encoded_id}",
        )

    async def relations(self, service_ids: list[str]) -> dict[str, Any]:
        if not 2 <= len(service_ids) <= 20:
            raise ValueError("관계 조회에는 2~20개의 service_id가 필요합니다.")
        return await self._request(
            "nara-search",
            "GET",
            f"{self.settings.search_url}/relations",
            params={"ids": ",".join(service_ids)},
        )

    async def compose(
        self, service_ids: list[str], question: str
    ) -> dict[str, Any]:
        if not 1 <= len(service_ids) <= 3:
            raise ValueError("조합에는 1~3개의 service_id가 필요합니다.")
        return await self._request(
            "nara-combiner",
            "POST",
            f"{self.settings.combiner_url}/compose",
            json={"service_ids": service_ids, "question": question},
            timeout=self.settings.compose_timeout,
        )

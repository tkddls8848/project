from __future__ import annotations

import asyncio

import httpx

from app.config import Settings
from app.nara_client import NaraClient, NaraServiceError


def test_client_uses_existing_nara_contracts():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "query": "청년 지원",
                    "results": [{"service_id": "openapi_new:15000001"}],
                    "diagnostics": {"fusion": "rrf"},
                },
            )
        if request.url.path == "/services/openapi_new:15000001":
            return httpx.Response(
                200, json={"service_id": "openapi_new:15000001"}
            )
        if request.url.path == "/relations":
            return httpx.Response(200, json={"relations": [{"type": "shared"}]})
        if request.url.path == "/compose":
            return httpx.Response(200, json={"suggestion": "계획 초안"})
        return httpx.Response(404)

    async def scenario():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            client = NaraClient(
                Settings("http://search", "http://combiner", 1), http
            )
            await client.search("청년 지원", top_k=7, use_vector=False)
            await client.detail("openapi_new:15000001")
            await client.relations(
                ["openapi_new:15000001", "openapi_new:15000002"]
            )
            await client.compose(["openapi_new:15000001"], "계획해줘")

    asyncio.run(scenario())

    assert [request.url.path for request in requests] == [
        "/search",
        "/services/openapi_new:15000001",
        "/relations",
        "/compose",
    ]
    assert requests[0].read()
    assert "ids=openapi_new%3A15000001%2Copenapi_new%3A15000002" in str(
        requests[2].url
    )


def test_client_wraps_upstream_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "Ollama 연결 실패"})

    async def scenario():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            client = NaraClient(
                Settings("http://search", "http://combiner", 1), http
            )
            try:
                await client.compose(["openapi_new:1"], "계획")
            except NaraServiceError as exc:
                assert exc.service == "nara-combiner"
                assert exc.status_code == 503
                assert "Ollama 연결 실패" in str(exc)
            else:
                raise AssertionError("NaraServiceError가 발생해야 합니다.")

    asyncio.run(scenario())


def test_compose_uses_dedicated_long_timeout():
    observed_timeout = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_timeout
        observed_timeout = request.extensions["timeout"]["read"]
        return httpx.Response(200, json={"suggestion": "계획"})

    async def scenario():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            client = NaraClient(
                Settings(
                    "http://search",
                    "http://combiner",
                    request_timeout=5,
                    compose_timeout=240,
                ),
                http,
            )
            await client.compose(["openapi_new:1"], "계획")

    asyncio.run(scenario())
    assert observed_timeout == 240

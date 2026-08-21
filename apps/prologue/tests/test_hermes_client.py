from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.config import Settings
from app.hermes_client import HermesGatewayClient, HermesGatewayError


def test_runs_api_create_stream_and_status_contract():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer secret"
        if request.method == "POST" and request.url.path == "/v1/runs":
            body = json.loads(request.content)
            assert body["model"] == "model-1"
            assert body["instructions"] == "policy"
            return httpx.Response(202, json={"run_id": "run_1", "status": "started"})
        if request.method == "GET" and request.url.path == "/v1/runs/run_1/events":
            events = [
                {"event": "tool.started", "tool": "mcp__nara__search_api_docs"},
                {"event": "tool.completed", "tool": "mcp__nara__search_api_docs"},
                {"event": "run.completed", "output": "{}", "usage": {"total_tokens": 7}},
            ]
            content = "".join(f"data: {json.dumps(event)}\n\n" for event in events)
            return httpx.Response(200, text=content, headers={"content-type": "text/event-stream"})
        if request.method == "GET" and request.url.path == "/v1/runs/run_1":
            return httpx.Response(200, json={
                "object": "hermes.run", "run_id": "run_1", "status": "completed",
                "session_id": "session-1", "output": "{}", "usage": {"total_tokens": 7},
            })
        return httpx.Response(404)

    async def scenario():
        settings = Settings(
            hermes_api_url="http://gateway", hermes_api_key="secret",
            hermes_model="model-1", hermes_run_timeout=5,
        )
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(base_url="http://gateway", transport=transport) as http:
            async with HermesGatewayClient(settings, client=http) as gateway:
                run_id = await gateway.create_run("input", "policy", "session-1")
                result = await gateway.wait(run_id)
        assert result.status == "completed"
        assert result.tool_calls == ["mcp__nara__search_api_docs"]
        assert result.usage["total_tokens"] == 7

    asyncio.run(scenario())
    assert [request.url.path for request in requests] == [
        "/v1/runs", "/v1/runs/run_1/events", "/v1/runs/run_1",
    ]


def test_tool_budget_stops_the_gateway_run():
    stopped = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal stopped
        if request.method == "GET" and request.url.path.endswith("/events"):
            content = "".join(
                f'data: {{"event":"tool.started","tool":"tool-{index}"}}\n\n'
                for index in range(2)
            )
            return httpx.Response(200, text=content)
        if request.method == "POST" and request.url.path.endswith("/stop"):
            stopped = True
            return httpx.Response(200, json={"status": "stopping"})
        return httpx.Response(404)

    async def scenario():
        settings = Settings(
            hermes_api_url="http://gateway", hermes_api_key="secret",
            hermes_max_tool_calls=1, hermes_run_timeout=5,
        )
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(base_url="http://gateway", transport=transport) as http:
            async with HermesGatewayClient(settings, client=http) as gateway:
                with pytest.raises(HermesGatewayError, match="상한 1회"):
                    await gateway.wait("run_1")

    asyncio.run(scenario())
    assert stopped

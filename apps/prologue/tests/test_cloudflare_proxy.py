from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

from app.cloudflare_proxy import (
    ProxySettings,
    create_app,
    normalize_chat_completion_payload,
    normalize_sse_line,
)


SETTINGS = ProxySettings(
    account_id="account-1",
    cloudflare_token="cloudflare-secret",
    proxy_key="proxy-secret",
)


def test_stream_delta_content_numbers_become_json_text():
    payload = {
        "choices": [{
            "delta": {
                "content": 27,
                "tool_calls": [{
                    "id": 3,
                    "function": {"name": "lookup", "arguments": {"id": 27}},
                }],
            }
        }]
    }

    normalized, changed = normalize_chat_completion_payload(payload)

    assert changed == 3
    delta = normalized["choices"][0]["delta"]
    assert delta["content"] == "27"
    assert delta["tool_calls"][0]["id"] == "3"
    assert delta["tool_calls"][0]["function"]["arguments"] == '{"id":27}'


def test_sse_normalization_preserves_control_and_malformed_lines():
    line = 'data: {"choices":[{"delta":{"content":12}}]}'
    normalized, changed = normalize_sse_line(line)

    assert changed == 1
    assert json.loads(normalized[5:].strip())["choices"][0]["delta"]["content"] == "12"
    assert normalize_sse_line("data: [DONE]") == ("data: [DONE]", 0)
    assert normalize_sse_line(": keepalive") == (": keepalive", 0)
    assert normalize_sse_line("data: not-json") == ("data: not-json", 0)


def test_proxy_normalizes_stream_and_keeps_cloudflare_token_upstream_only():
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        content = (
            'data: {"choices":[{"delta":{"content":"openapi_new:"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":123}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            200,
            text=content,
            headers={"content-type": "text/event-stream", "cf-ray": "ray-1"},
        )

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app(SETTINGS, upstream)
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer proxy-secret"},
            json={"model": "model-1", "stream": True, "messages": []},
        )
        health = client.get("/health").json()

    assert response.status_code == 200
    assert '"content":"123"' in response.text
    assert observed[0].url == (
        "https://api.cloudflare.com/client/v4/accounts/"
        "account-1/ai/v1/chat/completions"
    )
    assert observed[0].headers["authorization"] == "Bearer cloudflare-secret"
    assert "proxy-secret" not in observed[0].headers["authorization"]
    assert health["upstream_requests"] == 1
    assert health["normalized_fields"] == 1


def test_proxy_rejects_bad_local_credentials_without_calling_upstream():
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app(SETTINGS, upstream)
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer wrong"},
            json={"stream": False},
        )

    assert response.status_code == 401
    assert not called


def test_health_reports_missing_configuration_without_exposing_values():
    app = create_app(ProxySettings("", "", ""))
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["configured"] == {
        "account_id": False,
        "cloudflare_token": False,
        "proxy_key": False,
    }

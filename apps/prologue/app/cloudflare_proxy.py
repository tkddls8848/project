"""Loopback-only compatibility proxy for Cloudflare's OpenAI API.

Cloudflare occasionally emits non-string values in fields that the OpenAI
chat-completions schema declares as strings.  Hermes consumes those fields as
stream fragments and joins them, so one integer fragment can abort the whole
agent turn.  This proxy normalizes only the affected response fields and
otherwise preserves the upstream response.
"""

from __future__ import annotations

import hmac
import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse


SERVICE_NAME = "nara-cloudflare-compat-proxy"
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
FORWARDED_RESPONSE_HEADERS = {
    "cache-control",
    "cf-ray",
    "content-type",
    "openai-processing-ms",
    "request-id",
    "x-request-id",
}


@dataclass(frozen=True)
class ProxySettings:
    account_id: str
    cloudflare_token: str
    proxy_key: str

    @classmethod
    def from_env(cls) -> "ProxySettings":
        return cls(
            account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip(),
            cloudflare_token=os.getenv("CLOUDFLARE_API_TOKEN", "").strip(),
            proxy_key=os.getenv("NARA_CLOUDFLARE_PROXY_KEY", "").strip(),
        )

    @property
    def configured(self) -> bool:
        return bool(self.account_id and self.cloudflare_token and self.proxy_key)

    @property
    def upstream_base_url(self) -> str:
        return (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/v1"
        )


def _json_text(value: Any) -> str:
    """Render a non-string JSON value as a valid compact JSON fragment."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _normalize_string_field(container: dict[str, Any], field: str) -> int:
    value = container.get(field)
    if value is None or isinstance(value, str):
        return 0
    container[field] = _json_text(value)
    return 1


def _normalize_message(message: Any) -> int:
    if not isinstance(message, dict):
        return 0

    changed = 0
    for field in ("content", "reasoning", "reasoning_content"):
        changed += _normalize_string_field(message, field)

    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return changed
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        changed += _normalize_string_field(tool_call, "id")
        function = tool_call.get("function")
        if isinstance(function, dict):
            changed += _normalize_string_field(function, "name")
            changed += _normalize_string_field(function, "arguments")
    return changed


def normalize_chat_completion_payload(payload: Any) -> tuple[Any, int]:
    """Normalize string-typed response fields in one OpenAI-compatible payload."""
    if not isinstance(payload, dict):
        return payload, 0

    changed = 0
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return payload, changed
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        changed += _normalize_message(choice.get("delta"))
        changed += _normalize_message(choice.get("message"))
    return payload, changed


def normalize_sse_line(line: str) -> tuple[str, int]:
    """Normalize a single SSE data line, preserving comments and malformed data."""
    if not line.startswith("data:"):
        return line, 0
    raw = line[5:].strip()
    if not raw or raw == "[DONE]":
        return line, 0
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return line, 0
    payload, changed = normalize_chat_completion_payload(payload)
    if not changed:
        return line, 0
    normalized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"data: {normalized}", changed


def _response_headers(response: httpx.Response) -> dict[str, str]:
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() in FORWARDED_RESPONSE_HEADERS
        and key.lower() not in HOP_BY_HOP_HEADERS
    }


def _authorized(request: Request, expected_key: str) -> bool:
    if not expected_key:
        return False
    scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
    return scheme.lower() == "bearer" and hmac.compare_digest(supplied, expected_key)


def create_app(
    settings: ProxySettings | None = None,
    client: httpx.AsyncClient | None = None,
) -> FastAPI:
    resolved = settings or ProxySettings.from_env()
    owns_client = client is None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.http = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, read=None),
            follow_redirects=False,
        )
        app.state.upstream_requests = 0
        app.state.normalized_fields = 0
        try:
            yield
        finally:
            if owns_client:
                await app.state.http.aclose()

    proxy = FastAPI(title="Nara Cloudflare Compatibility Proxy", lifespan=lifespan)

    @proxy.get("/health")
    async def health() -> JSONResponse:
        status_code = 200 if resolved.configured else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": resolved.configured,
                "service": SERVICE_NAME,
                "configured": {
                    "account_id": bool(resolved.account_id),
                    "cloudflare_token": bool(resolved.cloudflare_token),
                    "proxy_key": bool(resolved.proxy_key),
                },
                "upstream_requests": proxy.state.upstream_requests,
                "normalized_fields": proxy.state.normalized_fields,
            },
        )

    @proxy.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        if not resolved.configured:
            return JSONResponse(
                status_code=503,
                content={"error": {"message": "Cloudflare proxy is not configured"}},
            )
        if not _authorized(request, resolved.proxy_key):
            return JSONResponse(
                status_code=401,
                content={"error": {"message": "Invalid proxy credentials"}},
            )

        body = await request.body()
        try:
            request_payload = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return JSONResponse(
                status_code=400,
                content={"error": {"message": "Request body must be valid JSON"}},
            )

        headers = {
            "Authorization": f"Bearer {resolved.cloudflare_token}",
            "Content-Type": "application/json",
            "Accept": request.headers.get("accept", "application/json"),
        }
        user_agent = request.headers.get("user-agent")
        if user_agent:
            headers["User-Agent"] = user_agent

        upstream_request = proxy.state.http.build_request(
            "POST",
            f"{resolved.upstream_base_url}/chat/completions",
            headers=headers,
            content=body,
        )
        proxy.state.upstream_requests += 1
        try:
            upstream = await proxy.state.http.send(upstream_request, stream=True)
        except httpx.HTTPError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "error": {
                        "message": "Cloudflare upstream connection failed",
                        "type": type(exc).__name__,
                    }
                },
            )

        response_headers = _response_headers(upstream)
        is_stream = bool(request_payload.get("stream")) or "text/event-stream" in upstream.headers.get(
            "content-type", ""
        ).lower()
        if is_stream:
            async def event_stream() -> AsyncIterator[str]:
                try:
                    async for line in upstream.aiter_lines():
                        normalized, changed = normalize_sse_line(line)
                        proxy.state.normalized_fields += changed
                        yield normalized + "\n"
                finally:
                    await upstream.aclose()

            response_headers["content-type"] = "text/event-stream"
            return StreamingResponse(
                event_stream(),
                status_code=upstream.status_code,
                headers=response_headers,
                media_type="text/event-stream",
            )

        try:
            content = await upstream.aread()
        finally:
            await upstream.aclose()
        if "application/json" in upstream.headers.get("content-type", "").lower():
            try:
                payload = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                pass
            else:
                payload, changed = normalize_chat_completion_payload(payload)
                proxy.state.normalized_fields += changed
                if changed:
                    content = json.dumps(
                        payload, ensure_ascii=False, separators=(",", ":")
                    ).encode("utf-8")
        return Response(
            content=content,
            status_code=upstream.status_code,
            headers=response_headers,
        )

    return proxy


app = create_app()


__all__ = [
    "ProxySettings",
    "app",
    "create_app",
    "normalize_chat_completion_payload",
    "normalize_sse_line",
]

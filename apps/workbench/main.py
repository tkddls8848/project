"""Nara Workbench single-origin gateway and static web application."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

UPSTREAMS = {
    "search": os.getenv("NARA_SEARCH_URL", "http://127.0.0.1:8000").rstrip("/"),
    "combiner": os.getenv("NARA_COMBINER_URL", "http://127.0.0.1:8003").rstrip("/"),
}

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
}

app = FastAPI(
    title="Nara API Workbench",
    version="0.1.0",
    description="공공 API 문서 검색, 관계 분석, 조합 설계를 한 화면에 제공하는 통합 앱",
)


@app.middleware("http")
async def disable_ui_asset_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _upstream_error(service: str, message: str, status_code: int = 503) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error_code": "UPSTREAM_UNAVAILABLE",
            "service": service,
            "message": message,
        },
    )


async def _health_one(service: str) -> dict[str, Any]:
    url = f"{UPSTREAMS[service]}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers={"Accept": "application/json"})
        payload = response.json() if response.content else {}
        return {
            "service": service,
            "reachable": response.is_success,
            "status_code": response.status_code,
            "payload": payload,
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "service": service,
            "reachable": False,
            "status_code": 0,
            "error": str(exc),
        }


@app.get("/api/workspace/health")
async def workspace_health() -> dict[str, Any]:
    search, combiner = await asyncio.gather(
        _health_one("search"),
        _health_one("combiner"),
    )
    reachable = sum(int(item["reachable"]) for item in (search, combiner))
    state = "ready" if reachable == 2 else ("degraded" if reachable else "offline")
    return {
        "ok": reachable == 2,
        "state": state,
        "services": {"search": search, "combiner": combiner},
    }


async def _proxy_request(service: str, path: str, request: Request) -> Response:
    base_url = UPSTREAMS[service]
    url = f"{base_url}/{path.lstrip('/')}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    body = await request.body()
    request_headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() in {"accept", "content-type"}
    }
    timeout = httpx.Timeout(240.0 if service == "combiner" else 60.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                url,
                content=body or None,
                headers=request_headers,
            )
    except httpx.HTTPError:
        label = "문서 검색" if service == "search" else "조합 분석"
        return _upstream_error(
            service,
            f"{label} 서비스에 연결할 수 없습니다. 통합 실행기의 서비스 상태를 확인하세요.",
        )

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }
    content_type = upstream.headers.get("content-type", "")
    if content_type.startswith("application/json") and "charset=" not in content_type:
        response_headers["content-type"] = f"{content_type}; charset=utf-8"
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )


@app.api_route(
    "/api/search/{path:path}",
    methods=["GET", "POST"],
)
async def proxy_search(path: str, request: Request) -> Response:
    return await _proxy_request("search", path, request)


@app.api_route(
    "/api/combiner/{path:path}",
    methods=["GET", "POST"],
)
async def proxy_combiner(path: str, request: Request) -> Response:
    return await _proxy_request("combiner", path, request)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/{path:path}")
async def spa_fallback(path: str) -> Response:
    candidate = (STATIC_DIR / path).resolve()
    try:
        candidate.relative_to(STATIC_DIR.resolve())
    except ValueError:
        return JSONResponse({"ok": False, "message": "not found"}, status_code=404)
    if candidate.is_file():
        return FileResponse(candidate)
    if "." not in Path(path).name:
        return FileResponse(STATIC_DIR / "index.html")
    return JSONResponse({"ok": False, "message": "not found"}, status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8010, reload=True)

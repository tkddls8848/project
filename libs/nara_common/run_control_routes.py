"""crawler와 refresher 제어 UI가 공유하는 HTTP 라우트 골격.

요청 검증과 HTTP 예외 변환은 서비스 endpoint가 맡는다. 이 모듈은 앱 수명주기,
정적 UI, 실행 조회·중단, SSE 전송처럼 두 제어 UI에서 같은 표면만 등록한다.

FastAPI는 함수 호출 시에만 가져온다. 따라서 ``nara_common`` 자체는 계속 표준
라이브러리만으로 import할 수 있고, 이 factory를 쓰는 제어 UI만 FastAPI가 필요하다.
"""

import json
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any


def create_run_control_app(
    *,
    title: str,
    version: str,
    description: str,
    static_dir: Path,
    manager_provider: Callable[[], Any],
    health_endpoint: Callable[..., Any],
    preview_endpoint: Callable[..., Any],
    create_endpoint: Callable[..., Any],
    run_not_found_message: str,
):
    """공통 제어 라우트를 등록한 FastAPI 앱을 만든다.

    ``manager_provider``는 라우트 호출 시점에 실행기를 찾는다. 테스트나 임베딩
    환경에서 서비스 모듈의 실행기를 바꿔도 수명주기와 라우트가 같은 대상을 보게 한다.
    """
    try:
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.responses import FileResponse, Response, StreamingResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover - 소비 서비스의 설치 오류
        raise RuntimeError("run-control 라우트를 쓰려면 FastAPI가 필요합니다.") from exc

    app = FastAPI(title=title, version=version, description=description)

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            await manager_provider().shutdown()

    app.router.lifespan_context = lifespan

    static_dir = Path(static_dir)
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    async def index():
        return FileResponse(static_dir / "index.html")

    async def favicon():
        return Response(status_code=204)

    async def list_runs():
        manager = manager_provider()
        return {"active_run_id": manager.active_run_id(), "runs": manager.recent()}

    async def get_run(run_id: str):
        try:
            return manager_provider().snapshot(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=run_not_found_message) from exc

    async def stop_run(run_id: str):
        try:
            return await manager_provider().stop(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=run_not_found_message) from exc

    async def run_events(
        run_id: str, request: Request, after: int = 0
    ) -> StreamingResponse:
        async def event_stream():
            try:
                async for event in manager_provider().stream(run_id, after=after):
                    if await request.is_disconnected():
                        return
                    data = json.dumps(event, ensure_ascii=False)
                    yield f"id: {event['sequence']}\nevent: progress\ndata: {data}\n\n"
            except KeyError:
                data = json.dumps(
                    {"message": run_not_found_message}, ensure_ascii=False
                )
                yield f"event: error\ndata: {data}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    app.add_api_route("/", index, methods=["GET"], include_in_schema=False)
    app.add_api_route(
        "/favicon.ico", favicon, methods=["GET"], include_in_schema=False
    )
    app.add_api_route("/health", health_endpoint, methods=["GET"])
    app.add_api_route("/runs/preview", preview_endpoint, methods=["POST"])
    app.add_api_route("/runs", create_endpoint, methods=["POST"], status_code=202)
    app.add_api_route("/runs", list_runs, methods=["GET"])
    app.add_api_route("/runs/{run_id}", get_run, methods=["GET"])
    app.add_api_route("/runs/{run_id}/stop", stop_run, methods=["POST"])
    app.add_api_route("/runs/{run_id}/events", run_events, methods=["GET"])
    return app


__all__ = ["create_run_control_app"]

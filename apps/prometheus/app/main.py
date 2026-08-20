"""FastAPI surface for the Nara Hermes orchestration service."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.agent import AgentRunManager
    from app.flow_export import design_to_flow
    from app.hermes_client import HermesGatewayClient, HermesGatewayError
    from app.nara_client import NaraClient, NaraServiceError
    from app.schemas import AgentRunRequest, AgentRunResponse
    from app.summary_image import design_to_summary_svg
else:
    from .agent import AgentRunManager
    from .flow_export import design_to_flow
    from .hermes_client import HermesGatewayClient, HermesGatewayError
    from .nara_client import NaraClient, NaraServiceError
    from .schemas import AgentRunRequest, AgentRunResponse
    from .summary_image import design_to_summary_svg

app = FastAPI(
    title="Nara Hermes Orchestration Service",
    version="1.0.0",
    description="Hermes Gateway와 Nara MCP를 결합한 읽기·계획 전용 오케스트레이션 서비스",
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
agent_runs = AgentRunManager()


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.exception_handler(NaraServiceError)
async def nara_service_error_handler(_, exc: NaraServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={
            "ok": False,
            "error_code": "NARA_SERVICE_ERROR",
            "service": exc.service,
            "upstream_status": exc.status_code,
            "message": str(exc),
        },
    )


@app.get("/health")
async def health():
    async with NaraClient() as client:
        services = await client.health()
    return {"ok": True, "service": "nara-hermes-orchestrator", "upstreams": services}


@app.get("/agent/health")
async def agent_health():
    try:
        async with HermesGatewayClient(agent_runs.settings) as gateway:
            readiness = await gateway.health()
        return {
            "ok": readiness.get("status") == "ok",
            "mode": "gateway-runs-api",
            "profile": agent_runs.settings.hermes_profile,
            "model": agent_runs.settings.hermes_model,
            "gateway": readiness,
        }
    except HermesGatewayError as exc:
        return {
            "ok": False,
            "mode": "gateway-runs-api",
            "profile": agent_runs.settings.hermes_profile,
            "model": agent_runs.settings.hermes_model,
            "error": str(exc),
        }


@app.post("/data/rebuild")
async def rebuild_search_data():
    """Rebuild the Search index from the current nara_storage snapshot."""
    async with NaraClient() as client:
        return await client.rebuild_search_index()


@app.get("/data/rebuild/status")
async def search_data_rebuild_status():
    async with NaraClient() as client:
        return await client.rebuild_status()


@app.post("/agent/design-runs", response_model=AgentRunResponse, status_code=202)
async def create_agent_design_run(request: AgentRunRequest) -> AgentRunResponse:
    return await agent_runs.create(request)


@app.get("/agent/design-runs/{run_id}", response_model=AgentRunResponse)
async def get_agent_design_run(run_id: str) -> AgentRunResponse:
    try:
        return agent_runs.snapshot(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent run not found") from exc


@app.post("/agent/design-runs/{run_id}/stop", response_model=AgentRunResponse)
async def stop_agent_design_run(run_id: str) -> AgentRunResponse:
    try:
        return await agent_runs.stop(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent run not found") from exc


@app.get("/agent/design-runs/{run_id}/flow")
async def export_agent_design_flow(run_id: str) -> JSONResponse:
    try:
        run = agent_runs.snapshot(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent run not found") from exc
    if run.status != "completed" or run.result is None:
        raise HTTPException(status_code=409, detail="완료된 실행만 대시보드로 내보낼 수 있습니다.")
    filename = f"nara-agent-{run_id[:8]}.flow.json"
    return JSONResponse(
        content=design_to_flow(run.result),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get(
    "/agent/design-runs/{run_id}/summary.svg",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}},
)
async def export_agent_design_summary(run_id: str) -> Response:
    """Render the finished plan as a one-page MVP presentation image."""
    try:
        run = agent_runs.snapshot(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent run not found") from exc
    if run.status != "completed" or run.result is None:
        raise HTTPException(status_code=409, detail="완료된 실행만 요약 이미지로 만들 수 있습니다.")
    filename = f"nara-agent-{run_id[:8]}.summary.svg"
    return Response(
        content=design_to_summary_svg(run.result, critic=run.critic),
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.get("/agent/design-runs/{run_id}/events")
async def agent_design_events(run_id: str, request: Request, after: int = 0) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in agent_runs.stream(run_id, after=after):
                if await request.is_disconnected():
                    return
                data = json.dumps(event.model_dump(), ensure_ascii=False)
                yield f"id: {event.sequence}\nevent: progress\ndata: {data}\n\n"
        except KeyError:
            yield "event: error\ndata: {\"message\": \"Agent run not found\"}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8020)

"""FastAPI surface for manually exercising the isolated PoC."""

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
    from app.nara_client import NaraClient, NaraServiceError
    from app.orchestrator import run_design
    from app.schemas import AgentRunRequest, AgentRunResponse, DesignRequest, DesignResponse
else:
    from .agent import AgentRunManager
    from .nara_client import NaraClient, NaraServiceError
    from .orchestrator import run_design
    from .schemas import AgentRunRequest, AgentRunResponse, DesignRequest, DesignResponse

app = FastAPI(
    title="Nara Hermes PoC",
    version="0.1.0",
    description="기존 Nara 서비스를 변경하지 않는 읽기·계획 전용 PoC",
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
    return {"ok": True, "service": "nara-hermes-poc", "upstreams": services}


@app.post("/design", response_model=DesignResponse)
async def design(request: DesignRequest) -> DesignResponse:
    return await run_design(request)


@app.get("/agent/health")
async def agent_health():
    return {
        "ok": True,
        "mode": "bounded-hermes-mcp",
        "profile": agent_runs.settings.hermes_profile,
        "model": agent_runs.settings.hermes_model,
        "probe_enabled": agent_runs.settings.hermes_probe_enabled,
    }


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

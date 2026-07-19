"""FastAPI surface for manually exercising the isolated PoC."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.nara_client import NaraClient, NaraServiceError
    from app.orchestrator import run_design
    from app.schemas import DesignRequest, DesignResponse
else:
    from .nara_client import NaraClient, NaraServiceError
    from .orchestrator import run_design
    from .schemas import DesignRequest, DesignResponse

app = FastAPI(
    title="Nara Hermes PoC",
    version="0.1.0",
    description="기존 Nara 서비스를 변경하지 않는 읽기·계획 전용 PoC",
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8020)

"""브라우저에서 크롤링을 제어하는 읽기·실행 API.

CORS를 열지 않는다. 이 서비스는 크롤을 *시작*시킬 수 있으므로, 아무 출처의
페이지가 로컬호스트로 요청을 보내 크롤을 돌리게 두면 안 된다. UI는 같은
출처에서 제공되므로 CORS가 필요 없다.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import metadata_service, storage_service
from .run_service import DATA_TYPES, CrawlRequest, CrawlRequestError, CrawlRunManager

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Nara Crawler Control",
    version="0.1.0",
    description="data.go.kr 크롤러를 브라우저에서 실행·중단·관찰하는 제어 서비스",
)
runs = CrawlRunManager()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        yield
    finally:
        await runs.shutdown()


app.router.lifespan_context = lifespan

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class CrawlRunRequest(BaseModel):
    type: Optional[str] = Field(default=None, description="크롤 대상 타입")
    start: Optional[int] = Field(default=None, ge=0)
    end: Optional[int] = Field(default=None, ge=0)
    workers: Optional[int] = Field(default=None, ge=1, le=64)
    full: bool = False
    deep: bool = False
    full_download: bool = False
    harvest: bool = False
    harvest_max_hosts: int = Field(default=4, ge=1, le=50)
    skip_update: bool = False
    force_update: bool = False

    def to_domain(self) -> CrawlRequest:
        return CrawlRequest(
            data_type=self.type,
            start=self.start,
            end=self.end,
            workers=self.workers,
            full=self.full,
            deep=self.deep,
            full_download=self.full_download,
            harvest=self.harvest,
            harvest_max_hosts=self.harvest_max_hosts,
            skip_update=self.skip_update,
            force_update=self.force_update,
        )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "nara-crawler-control",
        "data_types": list(DATA_TYPES),
        "active_run_id": runs.active_run_id(),
        "storage": storage_service.storage_overview(),
    }


@app.get("/metadata")
async def metadata_overview():
    """목록 CSV의 존재·크기·수정시각. 범위 파싱은 하지 않는다."""
    return metadata_service.overview()


@app.get("/metadata/{data_type}/range")
async def metadata_range(data_type: str):
    """CSV 전체를 파싱해 문서번호 범위를 구한다. 큰 CSV는 수십 초 걸린다."""
    return await metadata_service.document_range(data_type)


@app.get("/storage")
async def storage_state():
    return {
        **storage_service.storage_overview(),
        "recent_crawls": storage_service.recent_manifests(),
    }


@app.post("/runs/preview")
async def preview_run(request: CrawlRunRequest):
    """실행하지 않고 검증만 한다. UI가 명령을 자체 조립하면 서버와 어긋나므로
    실제로 실행될 argv를 여기서 받아 그대로 보여준다."""
    try:
        return {"ok": True, "command": request.to_domain().command_preview()}
    except CrawlRequestError as exc:
        return {"ok": False, "message": str(exc)}


@app.post("/runs", status_code=202)
async def create_run(request: CrawlRunRequest):
    try:
        return await runs.create_crawl(request.to_domain())
    except CrawlRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/runs")
async def list_runs():
    return {"active_run_id": runs.active_run_id(), "runs": runs.recent()}


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    try:
        return runs.snapshot(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="크롤 실행을 찾을 수 없습니다.") from exc


@app.post("/runs/{run_id}/stop")
async def stop_run(run_id: str):
    try:
        return await runs.stop(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="크롤 실행을 찾을 수 없습니다.") from exc


@app.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, after: int = 0) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in runs.stream(run_id, after=after):
                if await request.is_disconnected():
                    return
                data = json.dumps(event, ensure_ascii=False)
                yield f"id: {event['sequence']}\nevent: progress\ndata: {data}\n\n"
        except KeyError:
            yield 'event: error\ndata: {"message": "크롤 실행을 찾을 수 없습니다."}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.exception_handler(CrawlRequestError)
async def crawl_request_error_handler(_, exc: CrawlRequestError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"ok": False, "message": str(exc)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8004)

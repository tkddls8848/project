"""브라우저에서 활용신청 연장을 표시·제어하는 API.

CORS를 열지 않는다. 이 서비스는 정부 포털에 실제 제출을 일으킬 수 있으므로,
다른 출처의 페이지가 로컬호스트로 요청을 보내 연장을 제출하게 두면 안 된다.
UI는 같은 출처에서 제공되므로 CORS가 필요 없다.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import session_service
from .run_service import COMMANDS, RefreshRequest, RefreshRequestError, RefreshRunManager

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Nara Refresher Control",
    version="0.1.0",
    description="data.go.kr 활용신청 연장을 브라우저에서 보고 실행하는 제어 서비스",
)
runs = RefreshRunManager()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        yield
    finally:
        await runs.shutdown()


app.router.lifespan_context = lifespan

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class RefreshRunRequest(BaseModel):
    command: str = Field(..., description="login | list | extend")
    manual: bool = False
    timeout: float = Field(default=600.0, gt=0, le=3600)
    commit: bool = False
    limit: Optional[int] = Field(default=None, ge=1)
    only: str = ""
    confirm_commit: bool = False

    def to_domain(self) -> RefreshRequest:
        return RefreshRequest(
            command=self.command,
            manual=self.manual,
            timeout=self.timeout,
            commit=self.commit,
            limit=self.limit,
            only=self.only.strip(),
            confirm_commit=self.confirm_commit,
        )


class StdinRequest(BaseModel):
    text: str = "\n"


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
        "service": "nara-refresher-control",
        "commands": list(COMMANDS),
        "active_run_id": runs.active_run_id(),
        "session": session_service.session_state(),
    }


@app.get("/accounts")
async def accounts():
    """저장된 세션으로 보유 API 목록을 읽는다. 포털을 변경하지 않는다."""
    return await session_service.list_accounts()


@app.post("/runs/preview")
async def preview_run(request: RefreshRunRequest):
    """실행하지 않고 검증만 한다. UI가 명령을 자체 조립하면 서버와 어긋난다."""
    domain = request.to_domain()
    try:
        command = domain.command_preview()
    except RefreshRequestError as exc:
        return {"ok": False, "message": str(exc)}
    return {
        "ok": True,
        "command": command,
        "writes_to_portal": domain.writes_to_portal,
        "accepts_stdin": domain.accepts_stdin,
    }


@app.post("/runs", status_code=202)
async def create_run(request: RefreshRunRequest):
    try:
        return await runs.create_command(request.to_domain())
    except RefreshRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
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
        raise HTTPException(status_code=404, detail="실행을 찾을 수 없습니다.") from exc


@app.post("/runs/{run_id}/stop")
async def stop_run(run_id: str):
    try:
        return await runs.stop(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="실행을 찾을 수 없습니다.") from exc


@app.post("/runs/{run_id}/stdin")
async def send_stdin(run_id: str, payload: StdinRequest):
    """`login --manual`이 기다리는 Enter를 브라우저 버튼으로 대신 보낸다."""
    try:
        return await runs.send_stdin(run_id, payload.text)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="실행을 찾을 수 없습니다.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
            yield 'event: error\ndata: {"message": "실행을 찾을 수 없습니다."}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8005)

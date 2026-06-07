"""FastAPI entrypoint for the API document combiner."""
import json
import logging
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import NARA_DATA_DIR, OLLAMA_MODEL
from .loader import get_services, load_all
from .llm import generate, generate_stream
from .prompts import build_prompt, detect_warning
from .schemas import ComposeRequest, ComposeResponse

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Nara Combiner", version="0.1.0")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
_static = BASE_DIR / "static"
if _static.exists():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")


@app.on_event("startup")
async def startup() -> None:
    docs = load_all()
    logger.info("Nara Combiner loaded %d services from %s", len(docs), NARA_DATA_DIR)


@app.get("/health")
async def health():
    docs = load_all()
    return {"ok": True, "service": "nara-combiner", "docs_loaded": len(docs), "model": OLLAMA_MODEL}


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/compose-stream")
async def compose_stream(ids: str, q: str = "이 API들을 조합하면 어떤 행정 서비스 계획을 만들 수 있나?"):
    service_ids = [x.strip() for x in ids.split(",") if x.strip()]
    services, missing = get_services(service_ids)

    domains = sorted({s.domain for s in services})
    warning = detect_warning(services)

    async def event_gen():
        meta = {"domains": domains, "warning": warning, "missing": missing}
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"
        if not services:
            yield f"data: {json.dumps({'error': '서비스 ID를 찾을 수 없습니다.'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        prompt = build_prompt(services, q)
        try:
            async for token in generate_stream(prompt):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except RuntimeError as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/compose")
async def compose(req: ComposeRequest, request: Request):
    t0 = time.time()
    services, missing = get_services(req.service_ids)

    if not services:
        return JSONResponse(
            {"error": "서비스 ID를 하나도 찾을 수 없습니다.", "missing": missing},
            status_code=404,
        )

    domains = sorted({s.domain for s in services})
    warning = detect_warning(services)
    prompt = build_prompt(services, req.question)

    if "text/event-stream" in request.headers.get("accept", ""):
        async def event_gen():
            meta = {"domains": domains, "warning": warning, "missing": missing}
            yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"
            try:
                async for token in generate_stream(prompt):
                    yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            except RuntimeError as e:
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    try:
        suggestion = await generate(prompt)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=503)

    elapsed = int((time.time() - t0) * 1000)
    return ComposeResponse(
        service_ids=req.service_ids,
        domains=domains,
        warning=warning,
        suggestion=suggestion,
        elapsed_ms=elapsed,
        model=OLLAMA_MODEL,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8003, reload=True)

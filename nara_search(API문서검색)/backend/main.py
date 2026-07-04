import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .catalog.detail_service import DetailUnavailableError, ServiceDetailProvider
from .core import config
from .core.service_id import ServiceIdError, normalize_service_id, to_canonical
from .indexing.index_builder import build_status, run_build
from .search.faiss_retriever import FAISSRetriever

STATIC_DIR = config.BASE_DIR / "frontend"

retriever = FAISSRetriever()
detail_provider = ServiceDetailProvider()

app = FastAPI(title="Nara API Document Search", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=config.MAX_QUERY_LENGTH)
    top_k: int = Field(default=config.DEFAULT_TOP_K, ge=1, le=20)
    use_vector: bool = True


def _relative_source_path(path: str) -> str:
    if not path:
        return ""
    try:
        return str(Path(path).resolve().relative_to(config.BASE_DIR))
    except (ValueError, OSError):
        return Path(path).name


def _to_result(meta: dict) -> dict:
    return {
        "service_id":          to_canonical(str(meta.get("api_id", ""))),
        "api_type":            "openapi_new",
        "name":                meta.get("title", ""),
        "provider_agency_name": meta.get("provider", ""),
        "category":            meta.get("category", ""),
        "description":         meta.get("description", ""),
        "display_text":        meta.get("description", ""),
        "score":               meta.get("score", 0.0),
        "match_reasons":       ["vector similarity (ko-sroberta-multitask)"],
        "domain_ids":          [],
        "concept_ids":         [],
        "endpoints":           [],
        "request_fields":      [],
        "response_fields":     [],
        "counts":              {"request_fields": 0, "response_fields": 0},
        "source": {
            "refined_path": _relative_source_path(meta.get("source_path", "")),
            "raw_path":     "",
            "url":          meta.get("url", ""),
        },
    }


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"ok": False, "error_code": error_code, "message": message},
    )


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    count = retriever.collection_count()
    return {
        "ok":                    count is not None,
        "services_total":        count or 0,
        "chunks_total":          count or 0,
        "index_collection_total": count,
        "data_path":             retriever._openapi_dir,
        "index_error":           retriever.last_error() if count is None else "",
        "build_state":           build_status.state,
        "diagnostics":           retriever.diagnostics(),
    }


@app.post("/search")
def search(request: SearchRequest):
    query = request.query.strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="query must be at least 2 characters")
    raw = retriever.search(query, top_k=request.top_k)
    results = [_to_result(m) for m in raw]
    return {
        "query": query,
        "results": results,
        "diagnostics": {
            "vector_enabled":    True,
            "vector_candidates": len(results),
            "vector_error":      retriever.last_error() if not results else "",
        },
    }


@app.post("/build")
def trigger_build():
    if build_status.state == "running":
        return {"ok": False, "message": "이미 빌드 중입니다."}

    def _on_complete():
        retriever.reload()
        detail_provider.reload()

    thread = threading.Thread(target=run_build, kwargs={"on_complete": _on_complete}, daemon=True)
    thread.start()
    return {"ok": True, "message": "빌드를 시작했습니다."}


@app.get("/build/status")
def get_build_status():
    return build_status.to_dict()


@app.get("/services/{service_id:path}")
def service_detail(service_id: str):
    try:
        canonical_id = normalize_service_id(service_id)
    except ServiceIdError as exc:
        return _error_response(400, exc.error_code, exc.message)

    try:
        detail = detail_provider.get_detail(canonical_id)
    except DetailUnavailableError as exc:
        return _error_response(503, "SERVICE_UNAVAILABLE", exc.message)

    if detail is None:
        return _error_response(404, "NOT_FOUND", "service_id not found")
    return detail

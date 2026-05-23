import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .faiss_retriever import FAISSRetriever
from .index_builder import build_status, run_build

STATIC_DIR = config.BASE_DIR / "stage99_service" / "static"

retriever = FAISSRetriever()

app = FastAPI(title="Nara API Document Search", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=config.MAX_QUERY_LENGTH)
    top_k: int = Field(default=config.DEFAULT_TOP_K, ge=1, le=20)
    use_vector: bool = True


def _to_result(meta: dict) -> dict:
    return {
        "service_id":          f"openapi_new:{meta.get('api_id', '')}",
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
            "refined_path": meta.get("source_path", ""),
            "raw_path":     "",
            "url":          meta.get("url", ""),
        },
    }


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
    thread = threading.Thread(target=run_build, kwargs={"on_complete": retriever.reload}, daemon=True)
    thread.start()
    return {"ok": True, "message": "빌드를 시작했습니다."}


@app.get("/build/status")
def get_build_status():
    return build_status.to_dict()


@app.get("/services/{service_id:path}")
def service_detail(service_id: str):
    raise HTTPException(status_code=404, detail="service not found")

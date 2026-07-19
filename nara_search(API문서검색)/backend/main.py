import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .catalog.detail_service import DetailUnavailableError, ServiceDetailProvider
from .catalog.listing import CatalogListing
from .core import config
from .core.service_id import ServiceIdError, normalize_service_id, to_canonical
from .indexing.index_builder import build_status, resolve_device, run_build
from .relations.extractor import derive_relations, signature_from_detail
from .search.faiss_retriever import FAISSRetriever
from .search.fusion import reciprocal_rank_fusion
from .search.lexical_retriever import LexicalRetriever

STATIC_DIR = config.BASE_DIR / "frontend"

retriever = FAISSRetriever()
lexical_retriever = LexicalRetriever()
detail_provider = ServiceDetailProvider()
catalog_listing = CatalogListing()

CHANNEL_REASONS = {
    "vector": "vector similarity (ko-sroberta-multitask)",
    "lexical": "lexical BM25 (cjk bigram)",
}

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


class BuildRequest(BaseModel):
    device: str = Field(default="cpu", pattern="^(cpu|gpu|cuda)$")


def _relative_source_path(path: str) -> str:
    if not path:
        return ""
    try:
        return str(Path(path).resolve().relative_to(config.BASE_DIR))
    except (ValueError, OSError):
        return Path(path).name


def _to_result(meta: dict) -> dict:
    channels = meta.get("match_channels") or ["vector"]
    return {
        "service_id":          to_canonical(str(meta.get("api_id", ""))),
        "api_type":            "openapi_new",
        "name":                meta.get("title", ""),
        "provider_agency_name": meta.get("provider", ""),
        "category":            meta.get("category", ""),
        "description":         meta.get("description", ""),
        "display_text":        meta.get("description", ""),
        "score":               meta.get("score", 0.0),
        "match_reasons":       [CHANNEL_REASONS.get(c, c) for c in channels],
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
    chunk_count = retriever.collection_count()
    service_count = retriever.service_count()
    return {
        "ok":                    chunk_count is not None,
        "services_total":        service_count or 0,
        "chunks_total":          chunk_count or 0,
        "index_collection_total": chunk_count,
        "data_path":             retriever._openapi_dir,
        "index_error":           retriever.last_error() if chunk_count is None else "",
        "build_state":           build_status.state,
        "diagnostics":           retriever.diagnostics(),
        "lexical_corpus_total":  lexical_retriever.corpus_size(),
        "lexical_source":        lexical_retriever.corpus_source(),
    }


@app.post("/search")
def search(request: SearchRequest):
    """하이브리드 검색: 벡터(FAISS) + 렉시컬(BM25/cjk bigram)을 RRF로 융합.

    - 두 채널 모두 결과가 있으면 RRF(k=60)로 순위 융합 (score는 RRF 점수)
    - 한 채널만 가용하면 그 채널의 원 점수를 그대로 사용
    - 인덱스·모델이 없어도 렉시컬 채널로 검색이 동작한다
    """
    query = request.query.strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="query must be at least 2 characters")

    vector_raw = retriever.search(query, top_k=request.top_k) if request.use_vector else []
    lexical_raw = lexical_retriever.search(query, top_k=request.top_k)

    if vector_raw and lexical_raw:
        fused = reciprocal_rank_fusion(
            {"vector": vector_raw, "lexical": lexical_raw},
            top_k=request.top_k,
            weights={
                "vector": config.VECTOR_RRF_WEIGHT,
                "lexical": config.LEXICAL_RRF_WEIGHT,
            },
        )
        fusion = "rrf"
    elif vector_raw or lexical_raw:
        channel = "vector" if vector_raw else "lexical"
        fused = [dict(m, match_channels=[channel]) for m in (vector_raw or lexical_raw)][: request.top_k]
        fusion = channel
    else:
        fused = []
        fusion = "none"

    results = [_to_result(m) for m in fused]
    return {
        "query": query,
        "results": results,
        "diagnostics": {
            "vector_enabled":     request.use_vector,
            "vector_candidates":  len(vector_raw),
            "vector_error":       retriever.last_error() if not vector_raw else "",
            "vector_search":      retriever.search_diagnostics() if request.use_vector else {},
            "vector_rrf_weight":  config.VECTOR_RRF_WEIGHT,
            "lexical_rrf_weight": config.LEXICAL_RRF_WEIGHT,
            "lexical_candidates": len(lexical_raw),
            "lexical_source":     lexical_retriever.corpus_source(),
            "fusion":             fusion,
        },
    }


@app.post("/build")
def trigger_build(request: BuildRequest | None = None):
    if build_status.state == "running":
        return {"ok": False, "message": "이미 빌드 중입니다."}

    device = (request.device if request else "cpu")
    # 빌드 스레드를 띄우기 전에 디바이스 가용성을 확인해 즉시 오류를 반환한다.
    try:
        resolved = resolve_device(device)
    except (RuntimeError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}

    def _on_complete():
        retriever.reload()
        lexical_retriever.reload()
        detail_provider.reload()
        catalog_listing.reload()

    thread = threading.Thread(
        target=run_build,
        kwargs={"on_complete": _on_complete, "device": device},
        daemon=True,
    )
    thread.start()
    label = "GPU" if resolved == "cuda" else "CPU"
    return {"ok": True, "message": f"{label} 빌드를 시작했습니다.", "device": resolved}


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


@app.get("/relations")
def relations(ids: str = ""):
    """요청된 service_id들 사이의 derived 관계를 즉석 계산해 반환한다.

    같은 추출기를 relations.jsonl 프리컴퓨트(backend.relations.builder)와 공유하므로
    엣지 스키마는 항상 동일하다.
    """
    raw_ids = [part.strip() for part in ids.split(",") if part.strip()]
    if not 2 <= len(raw_ids) <= 20:
        return _error_response(400, "INVALID_IDS", "ids는 쉼표로 구분한 2~20개의 service_id여야 합니다")

    canonical_ids: list[str] = []
    for raw in raw_ids:
        try:
            cid = normalize_service_id(raw)
        except ServiceIdError as exc:
            return _error_response(400, exc.error_code, exc.message)
        if cid not in canonical_ids:
            canonical_ids.append(cid)

    signatures, missing = [], []
    for cid in canonical_ids:
        try:
            detail = detail_provider.get_detail(cid)
        except DetailUnavailableError as exc:
            return _error_response(503, "SERVICE_UNAVAILABLE", exc.message)
        if detail is None:
            missing.append(cid)
        else:
            signatures.append(signature_from_detail(detail))

    return {"ids": canonical_ids, "missing": missing, "relations": derive_relations(signatures)}


@app.get("/catalog")
def catalog():
    docs = catalog_listing.list_docs()
    return {"total": len(docs), "docs": docs}

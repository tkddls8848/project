from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .cache_builder import ensure_cache
from .data_loader import DataRepository, clean_text
from .document_builder import DocumentBuilder
from .ollama_retriever import OllamaFAISSRetriever
from .ranker import HybridSearchEngine
from .retriever import ChromaRetriever
from .schemas import SearchRequest, SearchResponse

STATIC_DIR = config.BASE_DIR / "stage99_service" / "static"

# 서버 시작 전 캐시 빌드 (documents.jsonl + faiss.index 없을 때만 실행)
print("[startup] 캐시 확인 중...")
ensure_cache()
print("[startup] 캐시 준비 완료")

repo = DataRepository()
retriever = OllamaFAISSRetriever() if config.FAISS_INDEX_PATH.exists() else ChromaRetriever()
search_engine = HybridSearchEngine(repo, retriever)
document_builder = DocumentBuilder(repo)

app = FastAPI(title="Nara API Document Search", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    index_count = retriever.collection_count()
    return {
        "ok": True,
        **repo.health(),
        "index_collection_total": index_count,
        "index_error": retriever.last_error() if index_count is None else "",
    }


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest):
    query = clean_text(request.query)
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="query must be at least 2 characters")
    return search_engine.search(query, top_k=request.top_k, use_vector=request.use_vector)


@app.get("/services/{service_id:path}")
def service_detail(service_id: str):
    if not repo.service_exists(service_id):
        raise HTTPException(status_code=404, detail="service not found")
    document = document_builder.build(service_id, compact=False)
    return document


@app.post("/reload")
def reload_data():
    repo.reload()
    return {"ok": True, **repo.health()}

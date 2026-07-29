import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def find_project_root(start: Path) -> Path:
    """`.nara-root` 마커를 위로 훑어 저장소 루트를 찾는다.

    디렉터리 깊이에 의존하지 않으므로 모듈을 services/ 아래로 옮겨도 같은 지점을 가리킨다.
    마커를 못 찾으면 예전 규약(모듈이 루트의 직계 자식)으로 폴백한다 — 임시 디렉터리를
    기준으로 도는 테스트가 마커 없이도 예전과 동일하게 동작하게 하기 위함이다.

    모듈 간 import 금지 제약 때문에 이 함수는 각 모듈에 복제되어 있다.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".nara-root").is_file():
            return candidate
    return start.parent


PROJECT_ROOT = find_project_root(BASE_DIR)


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name, "").strip()
    return Path(value) if value else default


DEFAULT_TOP_K = 5
MAX_QUERY_LENGTH = 300
MODEL_MAX_SEQ_LENGTH = int(os.environ.get("NARA_SEARCH_MODEL_MAX_SEQ_LENGTH", "256"))
VECTOR_MIN_SCORE = float(os.environ.get("NARA_SEARCH_VECTOR_MIN_SCORE", "0.42"))
VECTOR_OVERSAMPLE = int(os.environ.get("NARA_SEARCH_VECTOR_OVERSAMPLE", "12"))
VECTOR_CHUNK_MAX_CHARS = int(os.environ.get("NARA_SEARCH_VECTOR_CHUNK_MAX_CHARS", "650"))
VECTOR_MAX_CHUNKS_PER_DOCUMENT = int(
    os.environ.get("NARA_SEARCH_VECTOR_MAX_CHUNKS_PER_DOCUMENT", "12")
)
VECTOR_RRF_WEIGHT = float(os.environ.get("NARA_SEARCH_VECTOR_RRF_WEIGHT", "0.9"))
LEXICAL_RRF_WEIGHT = float(os.environ.get("NARA_SEARCH_LEXICAL_RRF_WEIGHT", "1.1"))

# ── 활성 런타임 경로 ─────────────────────────────────────────────────────────
# 검색 파이프라인(index_builder + faiss_retriever)이 실제로 사용하는 경로.

# OpenAPI JSON 데이터 — 저장소 공통 루트 nara_storage의 openapi_new 폴더
# ({api_id}.json 평면, nara_crawler가 생산). env로 오버라이드 가능.
APIDATA_DIR = _env_path("NARA_SEARCH_APIDATA_DIR", PROJECT_ROOT / "nara_storage" / "openapi_new")

# FAISS 인덱스 (POST /build 출력)
STORAGE_DIR = _env_path("NARA_SEARCH_STORAGE_DIR", BASE_DIR / "storage")
FAISS_INDEX_PATH = STORAGE_DIR / "faiss.index"
STORAGE_META_PATH = STORAGE_DIR / "metadata.jsonl"
VECTOR_META_PATH = STORAGE_DIR / "vector_metadata.jsonl"

# 로컬 임베딩 모델
LOCAL_MODEL_PATH = str(_env_path("NARA_SEARCH_MODEL_DIR", BASE_DIR / "models" / "ko-sroberta-multitask"))
HF_MODEL_ID = "jhgan/ko-sroberta-multitask"

# ── 카탈로그 산출물 경로 (선택) ──────────────────────────────────────────────
# nara_crawler 계획의 Stage 레이아웃(01_raw → 02_catalog → 03_semantic → 04_output)을
# 따르는 JSONL 자산 경로. 파일이 없으면 catalog.DataRepository는 빈 상태로 기동하고,
# 상세조회는 평면 apidata fallback을 사용한다.
DATA_DIR = _env_path("NARA_SEARCH_DATA_DIR", BASE_DIR / "data")
CATALOG_DIR = DATA_DIR / "02_catalog"      # services/documents/endpoints/fields.jsonl
SEMANTIC_DIR = DATA_DIR / "03_semantic"    # service_tags/field_mappings/concepts.jsonl
SERVING_DIR = DATA_DIR / "04_output"       # retrieval_chunks/api_tool_specs/recommender_catalog.jsonl
MINIMAL_DIR = DATA_DIR / "minimal"
MINIMAL_DOCS_PATH = MINIMAL_DIR / "documents.jsonl"


def ensure_local_model() -> str:
    """모델이 로컬에 없으면 HuggingFace Hub에서 다운로드. 로컬 경로 반환."""
    p = Path(LOCAL_MODEL_PATH)
    if p.exists() and any(p.iterdir()):
        return LOCAL_MODEL_PATH
    print(f"[config] 모델 다운로드 시작: {HF_MODEL_ID} → {LOCAL_MODEL_PATH}")
    p.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=HF_MODEL_ID, local_dir=LOCAL_MODEL_PATH)
    print(f"[config] 모델 다운로드 완료")
    return LOCAL_MODEL_PATH

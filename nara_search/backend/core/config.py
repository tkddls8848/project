from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

DEFAULT_TOP_K = 5
MAX_QUERY_LENGTH = 300

# FAISS 인덱스 (build_index.py 출력)
STORAGE_DIR = BASE_DIR / "storage"
FAISS_INDEX_PATH = STORAGE_DIR / "faiss.index"
STORAGE_META_PATH = STORAGE_DIR / "metadata.jsonl"

# 로컬 임베딩 모델
LOCAL_MODEL_PATH = str(BASE_DIR / "models" / "ko-sroberta-multitask")
HF_MODEL_ID = "jhgan/ko-sroberta-multitask"

# OpenAPI JSON 데이터 (평면, {api_id}_{date}.json)
APIDATA_DIR = BASE_DIR / "apidata"


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

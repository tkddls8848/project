from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_TOP_K = 5
MAX_QUERY_LENGTH = 300

# FAISS 인덱스 (build_index.py 출력)
STORAGE_DIR = BASE_DIR / "storage"
FAISS_INDEX_PATH = STORAGE_DIR / "faiss.index"
STORAGE_META_PATH = STORAGE_DIR / "metadata.jsonl"

# 로컬 임베딩 모델
LOCAL_MODEL_PATH = str(BASE_DIR / "models" / "ko-sroberta-multitask")

# 원본 데이터 루트
DATA_DIR = BASE_DIR / "data"

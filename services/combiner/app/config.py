import os
from pathlib import Path

from dotenv import load_dotenv
from nara_common.paths import find_project_root

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

PROJECT_ROOT = find_project_root(BASE_DIR)

# 공유 데이터 루트 nara_storage의 openapi_new 폴더 (env로 오버라이드 가능)
NARA_DATA_DIR: Path = Path(os.getenv("NARA_DATA_DIR", str(PROJECT_ROOT / "nara_storage" / "openapi_new")))
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
OLLAMA_TIMEOUT_SECONDS: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "210"))
OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "16384"))
OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))
OLLAMA_KEEP_ALIVE: str = os.getenv("OLLAMA_KEEP_ALIVE", "10m")
OLLAMA_THINK: bool = os.getenv("OLLAMA_THINK", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# 비스트리밍 suggestion 길이 예산 (초과분은 잘라내고 truncated=true로 표시)
MAX_SUGGESTION_CHARS: int = int(os.getenv("COMBINER_MAX_SUGGESTION_CHARS", "4000"))

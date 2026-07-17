import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# 공유 데이터 루트 nara_storage의 openapi_new 폴더 (env로 오버라이드 가능)
NARA_DATA_DIR: Path = Path(os.getenv("NARA_DATA_DIR", str(BASE_DIR.parent / "nara_storage" / "openapi_new")))
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma4:e4b")

# 비스트리밍 suggestion 길이 예산 (초과분은 잘라내고 truncated=true로 표시)
MAX_SUGGESTION_CHARS: int = int(os.getenv("COMBINER_MAX_SUGGESTION_CHARS", "4000"))

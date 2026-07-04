import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

NARA_DATA_DIR: Path = Path(os.getenv("NARA_DATA_DIR", str(BASE_DIR / "apidata")))
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma4:e4b")

# 비스트리밍 suggestion 길이 예산 (초과분은 잘라내고 truncated=true로 표시)
MAX_SUGGESTION_CHARS: int = int(os.getenv("COMBINER_MAX_SUGGESTION_CHARS", "4000"))

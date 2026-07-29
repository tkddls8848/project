import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def find_project_root(start: Path) -> Path:
    """`.nara-root` 마커를 위로 훑어 저장소 루트를 찾는다.

    디렉터리 깊이에 의존하지 않으므로 모듈을 services/ 아래로 옮겨도 같은 지점을 가리킨다.
    마커를 못 찾으면 예전 규약(모듈이 루트의 직계 자식)으로 폴백한다.

    모듈 간 import 금지 제약 때문에 이 함수는 각 모듈에 복제되어 있다.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".nara-root").is_file():
            return candidate
    return start.parent


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

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
# think가 켜져 있어 예산 대부분을 추론이 쓴다. 서비스 1건 프롬프트도 자연 종료까지
# 약 5,100 토큰이 필요했고 4096에서는 답변 전에 잘려 503이 났다. 더 올리지 않는 이유는
# OLLAMA_TIMEOUT_SECONDS다. 측정 생성 속도가 약 62 tok/s라 예산을 다 쓰면 8192는 130초대,
# 12288은 200초대가 되어 210초 제한에 걸린다.
OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "8192"))
OLLAMA_KEEP_ALIVE: str = os.getenv("OLLAMA_KEEP_ALIVE", "10m")
OLLAMA_THINK: bool = os.getenv("OLLAMA_THINK", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# 비스트리밍 suggestion 길이 예산 (초과분은 잘라내고 truncated=true로 표시)
MAX_SUGGESTION_CHARS: int = int(os.getenv("COMBINER_MAX_SUGGESTION_CHARS", "4000"))

"""nara_mcp 설정 — 환경 변수로만 제어한다."""
import os


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name, "").strip()
    try:
        return float(value) if value else default
    except ValueError:
        return default


NARA_SEARCH_BASE_URL = os.environ.get("NARA_SEARCH_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = _env_float("NARA_MCP_REQUEST_TIMEOUT", 10.0)

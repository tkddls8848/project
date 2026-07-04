"""
서비스 ID 계약.

정식 형식은 "{source}:{api_id}" (예: "openapi_new:15000827")이며,
순수 api_id 입력의 정규화는 Search만 담당한다. 다른 프로젝트는 받은
정식 ID를 재해석하지 않고 그대로 전달한다.
"""
import re

# 현재 수집·색인 대상 source. 확장 시 여기에만 추가한다.
SUPPORTED_SOURCES = frozenset({"openapi_new"})
DEFAULT_SOURCE = "openapi_new"

_CANONICAL_RE = re.compile(r"^(?P<source>[a-z][a-z0-9_]*):(?P<api_id>[A-Za-z0-9][A-Za-z0-9_-]*)$")
_PURE_API_ID_RE = re.compile(r"^\d+$")


class ServiceIdError(ValueError):
    """400으로 매핑되는 서비스 ID 입력 오류."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def normalize_service_id(raw: str) -> str:
    """입력을 정식 service_id로 정규화한다.

    - 정식 형식("{source}:{api_id}")은 source 검증 후 그대로 반환
    - 순수 숫자 api_id는 기본 source를 붙여 반환
    - 지원하지 않는 source prefix → ServiceIdError(UNSUPPORTED_SOURCE)
    - 그 외 형식 → ServiceIdError(INVALID_SERVICE_ID)
    """
    value = (raw or "").strip()
    if not value:
        raise ServiceIdError("INVALID_SERVICE_ID", "service_id is empty")

    if _PURE_API_ID_RE.match(value):
        return f"{DEFAULT_SOURCE}:{value}"

    match = _CANONICAL_RE.match(value)
    if not match:
        raise ServiceIdError(
            "INVALID_SERVICE_ID",
            "service_id must be '{source}:{api_id}' or a numeric api_id",
        )

    source = match.group("source")
    if source not in SUPPORTED_SOURCES:
        raise ServiceIdError("UNSUPPORTED_SOURCE", f"unsupported source prefix: {source}")
    return value


def to_canonical(api_id: str, source: str = DEFAULT_SOURCE) -> str:
    """api_id를 정식 service_id 문자열로 만든다."""
    return f"{source}:{api_id}"


def split_service_id(canonical: str) -> tuple[str, str]:
    """정식 service_id를 (source, api_id)로 분해한다. 정규화 이후에만 호출한다."""
    source, _, api_id = canonical.partition(":")
    return source, api_id

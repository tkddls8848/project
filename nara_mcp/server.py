"""nara_mcp — nara_search read-only MCP 어댑터 (로컬 stdio 전용).

노출 도구는 검색·상세조회·health 3개뿐이다. index build, 파일 쓰기,
조합·실행 기능은 노출하지 않는다. Search 서비스는 이 어댑터 없이도
독립 실행 가능하며, 어댑터는 HTTP로만 통신한다.

실행:
    python server.py            # stdio transport

MCP host 등록 예시는 README.md 참고.
"""
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP

import config
from clients.search_client import SearchClient

mcp = FastMCP(
    "nara-search",
    instructions=(
        "data.go.kr 공공 OpenAPI 문서 검색 서비스(nara_search)의 read-only 어댑터. "
        "search_public_services로 찾은 결과의 service_id(정식 형식 'openapi_new:{api_id}')를 "
        "get_service_detail에 그대로 전달하면 상세 문서를 얻는다. "
        "인덱스 빌드·데이터 수정 기능은 제공하지 않는다."
    ),
)

_client: SearchClient | None = None


def get_client() -> SearchClient:
    global _client
    if _client is None:
        _client = SearchClient(config.NARA_SEARCH_BASE_URL, timeout=config.REQUEST_TIMEOUT)
    return _client


@mcp.tool()
def search_public_services(query: str, top_k: int = 5, use_vector: bool = True) -> dict[str, Any]:
    """자연어로 공공 OpenAPI 문서를 검색한다.

    Args:
        query: 자연어 질의 (2~300자, 예: "미세먼지 실시간 조회")
        top_k: 반환할 최대 결과 수 (1~20)
        use_vector: 벡터 검색 사용 여부 (현재 검색기는 항상 벡터 기반)

    Returns:
        {ok, query, results[], diagnostics}. 각 result의 service_id는
        정식 형식("openapi_new:{api_id}")이며 get_service_detail에 그대로
        전달할 수 있다. 실패 시 {ok:false, error_code, message, retryable}.
    """
    return get_client().search(query, top_k=top_k, use_vector=use_vector)


@mcp.tool()
def get_service_detail(service_id: str) -> dict[str, Any]:
    """service_id로 공공 API 문서의 상세 정보를 조회한다.

    Args:
        service_id: 정식 형식 "openapi_new:{api_id}" (검색 결과의 service_id 그대로)
            또는 순수 숫자 api_id ("15000827")

    Returns:
        {ok, service_id, name, description, provider_agency_name, category,
        endpoints[], request_fields[], response_fields[], source}. 실패 시
        {ok:false, error_code(NOT_FOUND/INVALID_SERVICE_ID/UNSUPPORTED_SOURCE/
        SERVICE_UNAVAILABLE...), message, retryable}.
    """
    return get_client().get_service_detail(service_id)


@mcp.tool()
def get_index_health() -> dict[str, Any]:
    """검색 인덱스 준비 상태를 확인한다.

    Returns:
        {ok, services_total, build_state, diagnostics(apidata/index/metadata/
        model 존재 여부), index_error}. 검색이 빈 결과를 반환할 때 원인
        진단에 사용한다.
    """
    return get_client().health()


if __name__ == "__main__":
    # 로컬 stdio 전용. 원격 transport는 인증·감사 설계 전에는 열지 않는다.
    mcp.run(transport="stdio")

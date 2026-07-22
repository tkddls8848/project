"""Expose existing Nara capabilities as a minimal Hermes MCP server."""

from typing import Any

from app.config import get_settings
from app.freshness import check_document_freshness
from app.nara_client import NaraClient


def create_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MCP SDK가 없습니다. `python -m pip install -r requirements.txt`를 실행하세요."
        ) from exc

    mcp = FastMCP("nara-hermes-poc")

    @mcp.tool()
    async def search_api_docs(
        query: str, top_k: int = 5, use_vector: bool = True
    ) -> dict[str, Any]:
        """자연어로 공공 API 문서를 검색한다. 결과는 최대 20개다."""
        async with NaraClient() as client:
            return await client.search(query, top_k=top_k, use_vector=use_vector)

    @mcp.tool()
    async def get_api_detail(service_id: str) -> dict[str, Any]:
        """검색 결과의 service_id로 API 문서 상세를 조회한다."""
        async with NaraClient() as client:
            return await client.detail(service_id)

    @mcp.tool()
    async def derive_relations(service_ids: list[str]) -> dict[str, Any]:
        """2~20개 API 문서 사이의 파생 관계와 근거를 조회한다."""
        async with NaraClient() as client:
            return await client.relations(service_ids)

    @mcp.tool()
    async def compose_service_plan(
        service_ids: list[str], question: str
    ) -> dict[str, Any]:
        """1~3개 API 문서로 실행이 아닌 행정 서비스 계획 초안을 만든다."""
        async with NaraClient() as client:
            return await client.compose(service_ids, question)


    @mcp.tool()
    async def check_doc_freshness(service_ids: list[str]) -> list[dict[str, Any]]:
        """선택 API 문서의 크롤러 매니페스트 최신성을 한 번에 읽기 전용으로 확인한다."""
        if not 1 <= len(service_ids) <= 3:
            raise ValueError("문서 최신성 확인에는 1~3개의 service_id가 필요합니다.")
        settings = get_settings()
        return [item.model_dump() for item in check_document_freshness(
            service_ids, settings.storage_dir, settings.index_built_at
        )]
    return mcp


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()

"""Expose the two Nara selection capabilities as a minimal Hermes MCP server.

Tool results feed a chat-completions agent loop, which re-sends every earlier
result on each turn, so raw Search payloads make context growth quadratic: one
catalog document can carry hundreds of response fields.  Each tool therefore
returns only what a selector needs to rank and pick service_ids.  The full
documents are re-fetched from Search by the orchestrator after the loop ends.
"""

from typing import Any

from app.nara_client import NaraClient

SEARCH_DESCRIPTION_LIMIT = 200
DETAIL_DESCRIPTION_LIMIT = 400
ENDPOINT_SUMMARY_LIMIT = 80
MAX_ENDPOINTS = 12
MAX_FIELDS = 30


def _clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [row for row in (value or []) if isinstance(row, dict)]


def project_search(payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce a Search response to the ranking signals a selector reads."""
    results = _dicts(payload.get("results"))
    return {
        "query": str(payload.get("query") or ""),
        "total": len(results),
        "results": [
            {
                "service_id": str(row.get("service_id") or ""),
                "name": str(row.get("name") or ""),
                "provider_agency_name": str(row.get("provider_agency_name") or ""),
                "category": str(row.get("category") or ""),
                "description": _clip(row.get("description"), SEARCH_DESCRIPTION_LIMIT),
                "score": row.get("score", 0.0),
            }
            for row in results
        ],
    }


def _field(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(row.get("name") or ""),
        "type": str(row.get("type") or ""),
    }


def project_detail(payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce a detail document to its shape: endpoints and field names only."""
    endpoints = _dicts(payload.get("endpoints"))
    request_fields = _dicts(payload.get("request_fields"))
    response_fields = _dicts(payload.get("response_fields"))
    return {
        "service_id": str(payload.get("service_id") or ""),
        "name": str(payload.get("name") or ""),
        "provider_agency_name": str(payload.get("provider_agency_name") or ""),
        "category": str(payload.get("category") or ""),
        "description": _clip(payload.get("description"), DETAIL_DESCRIPTION_LIMIT),
        "updated_at": str(payload.get("updated_at") or ""),
        "endpoints": [
            {
                "endpoint_id": str(row.get("endpoint_id") or ""),
                "summary": _clip(row.get("summary"), ENDPOINT_SUMMARY_LIMIT),
            }
            for row in endpoints[:MAX_ENDPOINTS]
        ],
        "request_fields": [_field(row) for row in request_fields[:MAX_FIELDS]],
        "response_fields": [_field(row) for row in response_fields[:MAX_FIELDS]],
        # Real sizes stay visible so a clipped list is never read as the whole document.
        "counts": {
            "endpoints": len(endpoints),
            "request_fields": len(request_fields),
            "response_fields": len(response_fields),
        },
        "truncated": {
            "endpoints": len(endpoints) > MAX_ENDPOINTS,
            "request_fields": len(request_fields) > MAX_FIELDS,
            "response_fields": len(response_fields) > MAX_FIELDS,
        },
    }


def create_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MCP SDK가 없습니다. `python -m pip install -r requirements.txt`를 실행하세요."
        ) from exc

    mcp = FastMCP("nara-hermes-orchestrator")

    @mcp.tool()
    async def search_api_docs(
        query: str, top_k: int = 5, use_vector: bool = True
    ) -> dict[str, Any]:
        """자연어로 공공 API 문서를 검색해 service_id 후보 목록을 반환한다."""
        async with NaraClient() as client:
            return project_search(
                await client.search(query, top_k=top_k, use_vector=use_vector)
            )

    @mcp.tool()
    async def get_api_detail(service_id: str) -> dict[str, Any]:
        """service_id로 문서 요약(엔드포인트·필드명)을 조회한다. 전문은 반환하지 않는다."""
        async with NaraClient() as client:
            return project_detail(await client.detail(service_id))

    return mcp


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()

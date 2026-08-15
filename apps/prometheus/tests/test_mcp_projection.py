from __future__ import annotations

import json

from mcp_server.server import (
    MAX_ENDPOINTS,
    MAX_FIELDS,
    SEARCH_DESCRIPTION_LIMIT,
    project_detail,
    project_search,
)


def search_payload():
    return {
        "query": "미세먼지",
        "results": [
            {
                "service_id": "openapi_new:1",
                "api_type": "openapi_new",
                "name": "대기오염정보",
                "provider_agency_name": "한국환경공단",
                "category": "환경",
                "description": "설" * 500,
                "display_text": "설" * 500,
                "score": 0.87,
                "match_reasons": ["벡터 유사도"],
                "domain_ids": [],
                "concept_ids": [],
                "endpoints": [],
                "request_fields": [],
                "response_fields": [],
                "counts": {"request_fields": 0, "response_fields": 0},
                "source": {"refined_path": "nara_storage/openapi_new/1.json", "url": "https://example"},
            }
        ],
        "diagnostics": {"fusion": "rrf"},
    }


def detail_payload(field_count=200):
    return {
        "service_id": "openapi_new:1",
        "name": "대기오염정보",
        "provider_agency_name": "한국환경공단",
        "category": "환경",
        "description": "설명",
        "updated_at": "2026-01-02",
        "endpoints": [
            {"endpoint_id": f"GET /path{index}", "method": "GET", "path": f"/path{index}",
             "summary": "요약" * 200, "operation_id": f"op{index}", "tool_spec": None}
            for index in range(30)
        ],
        "request_fields": [
            {"field_id": f"f{index}", "endpoint_id": "GET /path0", "name": f"req{index}",
             "path": f"req{index}", "role": "request", "type": "string",
             "required": True, "description": "요청 필드 설명" * 20}
            for index in range(field_count)
        ],
        "response_fields": [
            {"field_id": f"r{index}", "endpoint_id": "", "name": f"resp{index}",
             "path": f"D.resp{index}", "role": "response", "type": "string",
             "required": False, "description": "응답 필드 설명" * 20}
            for index in range(field_count)
        ],
        "counts": {"endpoints": 30, "request_fields": field_count, "response_fields": field_count},
        "detail_source": "apidata_flat",
    }


def test_search_projection_keeps_only_ranking_signals():
    projected = project_search(search_payload())
    row = projected["results"][0]
    assert set(row) == {
        "service_id", "name", "provider_agency_name", "category", "description", "score",
    }
    assert row["service_id"] == "openapi_new:1"
    assert len(row["description"]) == SEARCH_DESCRIPTION_LIMIT + 1  # 말줄임표 포함
    assert projected["total"] == 1
    assert "diagnostics" not in projected


def test_detail_projection_caps_fields_and_reports_real_sizes():
    projected = project_detail(detail_payload())
    assert len(projected["endpoints"]) == MAX_ENDPOINTS
    assert len(projected["request_fields"]) == MAX_FIELDS
    assert len(projected["response_fields"]) == MAX_FIELDS
    # 잘린 목록을 문서 전체로 오해하지 않도록 원래 크기를 남긴다.
    assert projected["counts"] == {"endpoints": 30, "request_fields": 200, "response_fields": 200}
    assert projected["truncated"] == {"endpoints": True, "request_fields": True, "response_fields": True}
    assert set(projected["request_fields"][0]) == {"name", "type"}
    assert projected["request_fields"][0]["name"] == "req0"


def test_short_detail_is_not_marked_truncated():
    projected = project_detail(detail_payload(field_count=3))
    assert projected["truncated"]["request_fields"] is False
    assert projected["truncated"]["response_fields"] is False
    assert len(projected["response_fields"]) == 3


def test_projection_bounds_the_bytes_sent_back_into_the_loop():
    """검색 1회 + 상세 3회가 루프에 넣는 총량을 상한으로 고정한다."""
    projected = project_detail(detail_payload())
    detail_bytes = len(json.dumps(projected, ensure_ascii=False).encode("utf-8"))
    raw_bytes = len(json.dumps(detail_payload(), ensure_ascii=False).encode("utf-8"))
    assert detail_bytes < 8_000
    assert detail_bytes * 15 < raw_bytes


def test_projection_tolerates_missing_and_malformed_rows():
    assert project_search({})["results"] == []
    assert project_search({"results": ["nope", None]})["results"] == []
    empty = project_detail({})
    assert empty["service_id"] == ""
    assert empty["counts"] == {"endpoints": 0, "request_fields": 0, "response_fields": 0}
    assert empty["truncated"] == {"endpoints": False, "request_fields": False, "response_fields": False}

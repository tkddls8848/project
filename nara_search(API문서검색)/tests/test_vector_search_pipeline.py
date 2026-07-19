from backend.core import config
from backend.indexing.index_builder import _build_search_chunks
from backend.search.faiss_retriever import split_query_intents


def test_split_query_intents_keeps_full_query_and_korean_sub_intents():
    query = "재난 대피소와 실시간 기상 정보"
    assert split_query_intents(query) == [
        query,
        "재난 대피소",
        "실시간 기상 정보",
    ]


def test_single_intent_query_is_not_split():
    assert split_query_intents("미세먼지 측정소") == ["미세먼지 측정소"]


def test_search_chunks_repeat_identity_and_preserve_interface_fields(monkeypatch):
    monkeypatch.setattr(config, "VECTOR_MAX_CHUNKS_PER_DOCUMENT", 12)
    monkeypatch.setattr(config, "VECTOR_CHUNK_MAX_CHARS", 80)
    document = {
        "api_id": "15000001",
        "info": {
            "목록명": "미세먼지 조회",
            "제공기관": "환경기관",
            "분류체계": "환경",
            "키워드": "미세먼지,측정소",
            "설명": "측정소별 실시간 대기질을 제공합니다.",
        },
        "endpoints": [
            {"method": "GET", "path": "/air", "description": "측정소별 실시간 조회"},
        ],
        "swagger_json": {
            "definitions": {
                "Air": {
                    "properties": {
                        "pm10": {"description": "미세먼지 농도"},
                        "station": {"description": "측정소 이름"},
                    }
                }
            }
        },
    }

    chunks = _build_search_chunks(document)
    chunk_types = [chunk_type for chunk_type, _ in chunks]
    assert chunk_types == ["overview", "endpoints", "response_fields"]
    assert all("[제목] 미세먼지 조회" in text for _, text in chunks)
    assert "GET /air" in chunks[1][1]
    assert "미세먼지 농도" in chunks[2][1]

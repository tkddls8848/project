def _fake_search_results():
    return [
        {
            "api_id": "15000001",
            "title": "한국환경공단_에어코리아_대기오염정보",
            "provider": "한국환경공단",
            "category": "환경기상",
            "description": "시도별 실시간 대기오염 측정정보",
            "url": "https://www.data.go.kr/data/15000001/openapi.do",
            "source_path": "/somewhere/apidata/15000001_20260101120000.json",
            "score": 0.87,
        }
    ]


def test_search_returns_canonical_service_id(app_client, monkeypatch):
    from backend import main

    monkeypatch.setattr(main.retriever, "search", lambda query, top_k: _fake_search_results())
    response = app_client.post("/search", json={"query": "미세먼지 조회"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "미세먼지 조회"
    result = body["results"][0]
    assert result["service_id"] == "openapi_new:15000001"
    assert result["api_type"] == "openapi_new"
    assert result["name"]
    assert "score" in result


def test_search_result_id_works_for_detail(app_client, monkeypatch):
    """계약 핵심: /search가 준 service_id를 /services/{id}에 그대로 넣으면 성공."""
    from backend import main

    monkeypatch.setattr(main.retriever, "search", lambda query, top_k: _fake_search_results())
    search_body = app_client.post("/search", json={"query": "미세먼지 조회"}).json()
    service_id = search_body["results"][0]["service_id"]

    detail = app_client.get(f"/services/{service_id}")
    assert detail.status_code == 200
    assert detail.json()["service_id"] == service_id


def test_search_source_path_is_not_absolute(app_client, monkeypatch):
    from backend import main

    monkeypatch.setattr(main.retriever, "search", lambda query, top_k: _fake_search_results())
    body = app_client.post("/search", json={"query": "미세먼지 조회"}).json()
    refined_path = body["results"][0]["source"]["refined_path"]
    assert refined_path
    assert not refined_path.startswith("/")


def test_search_query_too_short_is_rejected(app_client):
    assert app_client.post("/search", json={"query": "a"}).status_code == 422
    assert app_client.post("/search", json={"query": " a "}).status_code == 400


def test_search_top_k_bounds(app_client):
    assert app_client.post("/search", json={"query": "버스", "top_k": 0}).status_code == 422
    assert app_client.post("/search", json={"query": "버스", "top_k": 21}).status_code == 422


def test_search_without_index_falls_back_to_lexical(app_client):
    """벡터 인덱스·모델이 없어도 렉시컬 BM25 채널로 검색이 동작한다."""
    response = app_client.post("/search", json={"query": "미세먼지"})
    assert response.status_code == 200
    body = response.json()
    diag = body["diagnostics"]
    assert diag["vector_candidates"] == 0
    assert diag["vector_error"]
    assert diag["fusion"] == "lexical"
    assert diag["lexical_source"] == "apidata_scan"
    assert body["results"], "lexical fallback이 결과를 반환해야 한다"
    top = body["results"][0]
    assert top["service_id"] == "openapi_new:15000001"
    assert "lexical BM25 (cjk bigram)" in top["match_reasons"]


def test_search_lexical_ranks_relevant_doc_first(app_client):
    body = app_client.post("/search", json={"query": "버스 도착"}).json()
    assert body["results"][0]["service_id"] == "openapi_new:15000002"


def test_search_no_match_returns_empty(app_client):
    body = app_client.post("/search", json={"query": "zzqqxx"}).json()
    assert body["results"] == []
    assert body["diagnostics"]["fusion"] == "none"


def test_search_rrf_fuses_vector_and_lexical(app_client, monkeypatch):
    """두 채널 모두 결과가 있으면 RRF로 융합하고 채널 근거를 표시한다."""
    from backend import main

    monkeypatch.setattr(main.retriever, "search", lambda query, top_k: _fake_search_results())
    body = app_client.post("/search", json={"query": "미세먼지 조회"}).json()
    diag = body["diagnostics"]
    assert diag["fusion"] == "rrf"
    assert diag["vector_candidates"] == 1
    assert diag["lexical_candidates"] >= 1
    top = body["results"][0]
    # 15000001은 두 채널 모두 1위 → 융합 1위, 두 근거 표시
    assert top["service_id"] == "openapi_new:15000001"
    assert set(top["match_reasons"]) == {
        "vector similarity (ko-sroberta-multitask)",
        "lexical BM25 (cjk bigram)",
    }


def test_search_use_vector_false_is_lexical_only(app_client, monkeypatch):
    from backend import main

    def _must_not_call(query, top_k):
        raise AssertionError("use_vector=false면 벡터 채널을 호출하지 않는다")

    monkeypatch.setattr(main.retriever, "search", _must_not_call)
    body = app_client.post("/search", json={"query": "미세먼지", "use_vector": False}).json()
    assert body["diagnostics"]["vector_enabled"] is False
    assert body["diagnostics"]["fusion"] == "lexical"
    assert body["results"]


def test_health_reports_diagnostics_without_index(app_client):
    response = app_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["index_error"]
    diag = body["diagnostics"]
    assert diag["apidata_exists"] is True
    assert diag["index_exists"] is False
    assert diag["metadata_exists"] is False
    assert body["lexical_corpus_total"] == 2
    assert body["lexical_source"] == "apidata_scan"

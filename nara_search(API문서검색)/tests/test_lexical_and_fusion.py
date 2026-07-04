"""BM25 렉시컬 검색기(cjk bigram)와 RRF 융합 단위 테스트."""
from backend.search.fusion import RRF_K, reciprocal_rank_fusion
from backend.search.lexical_retriever import LexicalRetriever, tokenize


# ── 토크나이저 (Elasticsearch cjk analyzer 방식) ─────────────────────────────

def test_tokenize_korean_bigrams():
    assert tokenize("미세먼지") == ["미세", "세먼", "먼지"]


def test_tokenize_mixed_ascii_and_korean():
    tokens = tokenize("PM10 미세먼지 API")
    assert "pm10" in tokens
    assert "api" in tokens
    assert "미세" in tokens


def test_tokenize_single_cjk_char_and_empty():
    assert tokenize("물") == ["물"]
    assert tokenize("") == []
    assert tokenize(None) == []


# ── BM25 검색 (fixture apidata 코퍼스) ───────────────────────────────────────

def _retriever(monkeypatch, fixture_apidata_dir, tmp_path):
    from backend.core import config

    monkeypatch.setattr(config, "APIDATA_DIR", fixture_apidata_dir)
    monkeypatch.setattr(config, "STORAGE_META_PATH", tmp_path / "none" / "metadata.jsonl")
    return LexicalRetriever()


def test_lexical_search_ranks_by_relevance(monkeypatch, fixture_apidata_dir, tmp_path):
    retriever = _retriever(monkeypatch, fixture_apidata_dir, tmp_path)
    assert retriever.corpus_source() == "apidata_scan"
    assert retriever.corpus_size() == 2

    results = retriever.search("미세먼지 대기오염", top_k=5)
    assert results
    assert results[0]["api_id"] == "15000001"
    assert results[0]["score"] > 0

    results = retriever.search("버스 정류소", top_k=5)
    assert results[0]["api_id"] == "15000002"


def test_lexical_search_no_match(monkeypatch, fixture_apidata_dir, tmp_path):
    retriever = _retriever(monkeypatch, fixture_apidata_dir, tmp_path)
    assert retriever.search("zzz9999", top_k=5) == []


def test_lexical_prefers_storage_metadata_when_present(monkeypatch, fixture_apidata_dir, tmp_path):
    import json

    from backend.core import config

    meta_path = tmp_path / "storage" / "metadata.jsonl"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text(
        json.dumps({"api_id": "77777777", "title": "메타데이터 우선 문서", "provider": "", "category": "", "description": "테스트", "keywords": ""}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "APIDATA_DIR", fixture_apidata_dir)
    monkeypatch.setattr(config, "STORAGE_META_PATH", meta_path)

    retriever = LexicalRetriever()
    assert retriever.corpus_source() == "storage_metadata"
    assert retriever.search("메타데이터")[0]["api_id"] == "77777777"


# ── RRF ──────────────────────────────────────────────────────────────────────

def _rec(api_id):
    return {"api_id": api_id, "title": f"doc {api_id}"}


def test_rrf_doc_in_both_lists_wins():
    fused = reciprocal_rank_fusion(
        {
            "vector": [_rec("A"), _rec("B")],
            "lexical": [_rec("C"), _rec("A")],
        },
        top_k=3,
    )
    assert [r["api_id"] for r in fused][0] == "A"
    top = fused[0]
    assert top["match_channels"] == ["vector", "lexical"]
    expected = round(1 / (RRF_K + 1) + 1 / (RRF_K + 2), 6)
    assert top["score"] == expected


def test_rrf_single_list_preserves_order():
    fused = reciprocal_rank_fusion({"lexical": [_rec("X"), _rec("Y"), _rec("Z")]}, top_k=2)
    assert [r["api_id"] for r in fused] == ["X", "Y"]
    assert fused[0]["match_channels"] == ["lexical"]


def test_rrf_respects_top_k_and_skips_missing_ids():
    fused = reciprocal_rank_fusion(
        {"vector": [{"title": "no id"}, _rec("A"), _rec("B"), _rec("C")]},
        top_k=2,
    )
    assert [r["api_id"] for r in fused] == ["A", "B"]

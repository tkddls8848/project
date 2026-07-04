import json


def _write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _patch_catalog_paths(monkeypatch, tmp_path):
    from backend.core import config

    monkeypatch.setattr(config, "CATALOG_DIR", tmp_path / "02_catalog")
    monkeypatch.setattr(config, "SEMANTIC_DIR", tmp_path / "03_semantic")
    monkeypatch.setattr(config, "SERVING_DIR", tmp_path / "04_output")
    monkeypatch.setattr(config, "MINIMAL_DOCS_PATH", tmp_path / "minimal" / "documents.jsonl")
    return config


def test_repository_starts_empty_when_catalog_missing(monkeypatch, tmp_path):
    """catalog 경로가 없어도 import·기동이 예외 없이 되고 빈 상태로 보고한다."""
    _patch_catalog_paths(monkeypatch, tmp_path)
    from backend.catalog.data_loader import DataRepository

    repo = DataRepository()
    health = repo.health()
    assert health["services_total"] == 0
    assert repo.service_exists("openapi_new:15000001") is False


def test_repository_loads_catalog_services(monkeypatch, tmp_path):
    config = _patch_catalog_paths(monkeypatch, tmp_path)
    _write_jsonl(
        config.CATALOG_DIR / "services.jsonl",
        [
            {
                "service_id": "openapi_new:15000001",
                "name": "카탈로그 대기오염정보",
                "description": "카탈로그 기반 설명",
                "provider_agency_name": "한국환경공단",
                "category": "환경기상",
                "source_portal": "data.go.kr",
                "source_object_id": "15000001",
            }
        ],
    )
    from backend.catalog.data_loader import DataRepository

    repo = DataRepository()
    assert repo.health()["services_total"] == 1
    assert repo.service_exists("openapi_new:15000001") is True


def test_repository_merges_minimal_documents(monkeypatch, tmp_path):
    config = _patch_catalog_paths(monkeypatch, tmp_path)
    _write_jsonl(
        config.MINIMAL_DOCS_PATH,
        [
            {
                "id": "15000009",
                "title": "미니멀 문서 서비스",
                "provider": "테스트기관",
                "category": "공공행정",
                "description": "미니멀 설명",
                "keywords": "테스트,문서",
                "text": "미니멀 검색 본문",
            }
        ],
    )
    from backend.catalog.data_loader import DataRepository

    repo = DataRepository()
    assert repo.service_exists("openapi_new:15000009") is True
    blob = repo.search_blobs["openapi_new:15000009"]
    assert "미니멀 검색 본문" in blob["all"]


def test_document_builder_uses_catalog(monkeypatch, tmp_path):
    config = _patch_catalog_paths(monkeypatch, tmp_path)
    _write_jsonl(
        config.CATALOG_DIR / "services.jsonl",
        [
            {
                "service_id": "openapi_new:15000001",
                "name": "카탈로그 대기오염정보",
                "description": "카탈로그 기반 설명",
                "provider_agency_name": "한국환경공단",
                "category": "환경기상",
            }
        ],
    )
    _write_jsonl(
        config.CATALOG_DIR / "endpoints.jsonl",
        [
            {
                "endpoint_id": "ep-1",
                "service_id": "openapi_new:15000001",
                "method": "GET",
                "path": "/getData",
                "summary": "데이터 조회",
            }
        ],
    )
    from backend.catalog.data_loader import DataRepository
    from backend.catalog.document_builder import DocumentBuilder

    builder = DocumentBuilder(DataRepository())
    payload = builder.build("openapi_new:15000001")
    assert payload is not None
    assert payload["name"] == "카탈로그 대기오염정보"
    assert payload["counts"]["endpoints"] == 1
    assert builder.build("openapi_new:00000000") is None

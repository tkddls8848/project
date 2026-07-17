import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# "nara_search(API문서검색)" 디렉터리명은 import 불가능하므로
# 프로젝트 루트를 sys.path에 넣고 backend 패키지로 import한다.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def fixture_apidata_dir() -> Path:
    return FIXTURES_DIR / "apidata"


@pytest.fixture
def app_client(monkeypatch, tmp_path, fixture_apidata_dir):
    """fixture apidata를 바라보고 인덱스·카탈로그는 없는 TestClient."""
    from backend.core import config

    monkeypatch.setattr(config, "APIDATA_DIR", fixture_apidata_dir)
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path / "storage")
    monkeypatch.setattr(config, "FAISS_INDEX_PATH", tmp_path / "storage" / "faiss.index")
    monkeypatch.setattr(config, "STORAGE_META_PATH", tmp_path / "storage" / "metadata.jsonl")
    monkeypatch.setattr(config, "CATALOG_DIR", tmp_path / "no_catalog")
    monkeypatch.setattr(config, "SEMANTIC_DIR", tmp_path / "no_semantic")
    monkeypatch.setattr(config, "SERVING_DIR", tmp_path / "no_serving")
    monkeypatch.setattr(config, "MINIMAL_DOCS_PATH", tmp_path / "no_minimal" / "documents.jsonl")

    from fastapi.testclient import TestClient

    from backend import main

    main.detail_provider.reload()
    main.lexical_retriever.reload()
    main.catalog_listing.reload()
    client = TestClient(main.app)
    yield client
    main.detail_provider.reload()
    main.lexical_retriever.reload()
    main.catalog_listing.reload()

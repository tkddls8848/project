"""POST /compose 응답 계약 테스트 (정상·일부 누락·전체 누락·LLM 장애·길이 예산)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def primed_catalog():
    """fixture 카탈로그를 캐시에 적재하고 테스트 후 초기화."""
    from app.loader import load_all, reset_cache

    reset_cache()
    load_all(data_dir=FIXTURES)
    yield
    reset_cache()


@pytest.fixture
def fake_llm(monkeypatch):
    """Ollama 호출을 고정 응답으로 대체."""
    async def _fake_generate(prompt: str, model: str = "test-model") -> str:
        return "두 API를 결합해 여행 안전 안내 서비스를 만들 수 있습니다."

    from app import main

    monkeypatch.setattr(main, "generate", _fake_generate)
    return _fake_generate


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


REQUIRED_RESPONSE_FIELDS = [
    "service_ids",
    "domains",
    "warning",
    "missing",
    "suggestion",
    "truncated",
    "elapsed_ms",
    "model",
]


def test_compose_success_contract(fake_llm):
    response = _client().post(
        "/compose", json={"service_ids": ["15000827", "15000863"], "question": "조합 방법?"}
    )
    assert response.status_code == 200
    body = response.json()
    for field in REQUIRED_RESPONSE_FIELDS:
        assert field in body, f"missing field: {field}"
    assert body["missing"] == []
    assert body["truncated"] is False
    assert body["suggestion"]


def test_compose_accepts_canonical_service_ids(fake_llm):
    """Search가 반환하는 정식 ID(openapi_new:...)를 그대로 받을 수 있다."""
    response = _client().post(
        "/compose", json={"service_ids": ["openapi_new:15000827"]}
    )
    assert response.status_code == 200
    assert response.json()["missing"] == []


def test_compose_partial_missing_is_200_with_report(fake_llm):
    response = _client().post(
        "/compose", json={"service_ids": ["15000827", "99999999"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["missing"] == ["99999999"]
    assert body["suggestion"]


def test_compose_all_missing_is_404(fake_llm):
    response = _client().post("/compose", json={"service_ids": ["00000001", "00000002"]})
    assert response.status_code == 404
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "NO_SERVICES_FOUND"
    assert set(body["missing"]) == {"00000001", "00000002"}
    assert body["error"]  # 기존 UI 호환 키


def test_compose_empty_ids_is_422():
    assert _client().post("/compose", json={"service_ids": []}).status_code == 422


def test_compose_too_many_ids_is_422():
    ids = [f"1500{i:04d}" for i in range(11)]
    assert _client().post("/compose", json={"service_ids": ids}).status_code == 422


def test_compose_llm_failure_is_503(monkeypatch):
    async def _broken_generate(prompt: str, model: str = "m") -> str:
        raise RuntimeError("Ollama 연결 실패 (http://localhost:11434). Ollama가 실행 중인지 확인하세요.")

    from app import main

    monkeypatch.setattr(main, "generate", _broken_generate)
    response = _client().post("/compose", json={"service_ids": ["15000827"]})
    assert response.status_code == 503
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "UPSTREAM_UNAVAILABLE"
    assert "Ollama" in body["message"]


def test_compose_truncates_long_suggestion(monkeypatch):
    from app import config, main

    async def _long_generate(prompt: str, model: str = "m") -> str:
        return "가" * (config.MAX_SUGGESTION_CHARS + 500)

    monkeypatch.setattr(main, "generate", _long_generate)
    response = _client().post("/compose", json={"service_ids": ["15000827"]})
    assert response.status_code == 200
    body = response.json()
    assert body["truncated"] is True
    assert len(body["suggestion"]) <= config.MAX_SUGGESTION_CHARS + len(main.TRUNCATION_MARKER)
    assert body["suggestion"].endswith("생략)")


def test_health_reports_docs_loaded():
    response = _client().get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["docs_loaded"] == 3

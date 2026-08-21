"""조합 API 계약 테스트.

POST /compose는 응답 계약(정상·일부 누락·전체 누락·LLM 장애·길이 예산)을,
GET /compose-stream은 같은 입력 제한이 걸려 있는지를 본다. 웹 UI가 실제로
쓰는 것은 후자라 둘이 어긋나면 화면에서만 제한이 새어 나간다.
"""
from pathlib import Path

import httpx
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


class _FakeStreamResponse:
    def __init__(self, *, lines=(), error=None):
        self._lines = lines
        self._error = error

    async def __aenter__(self):
        if self._error is not None:
            raise self._error
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeAsyncClient:
    def __init__(self, *, lines=(), error=None):
        self._lines = lines
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def stream(self, *args, **kwargs):
        return _FakeStreamResponse(lines=self._lines, error=self._error)


def _install_ollama_stream(monkeypatch, *, lines=(), error=None):
    from app import llm

    monkeypatch.setattr(
        llm.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(lines=lines, error=error),
    )


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
    ids = [f"1500{i:04d}" for i in range(4)]
    assert _client().post("/compose", json={"service_ids": ids}).status_code == 422


def test_compose_accepts_three_ids(fake_llm):
    response = _client().post(
        "/compose",
        json={"service_ids": ["15000827", "15000863", "15000881"]},
    )
    assert response.status_code == 200
    assert response.json()["missing"] == []


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


# ── GET /compose-stream ─────────────────────────────────────────────────
# 웹 UI가 실제로 쓰는 경로다. POST와 같은 제한이 걸려 있어야 한다.


@pytest.fixture
def fake_stream(monkeypatch):
    async def _fake_generate_stream(prompt: str, model: str = "test-model"):
        yield "조합 결과"

    from app import main

    monkeypatch.setattr(main, "generate_stream", _fake_generate_stream)
    return _fake_generate_stream


def test_compose_stream_rejects_too_many_ids():
    response = _client().get("/compose-stream", params={"ids": "1,2,3,4"})
    assert response.status_code == 200
    assert "error" in response.text
    assert "조합 결과" not in response.text


def test_compose_stream_rejects_empty_ids():
    response = _client().get("/compose-stream", params={"ids": " , "})
    assert "error" in response.text


def test_compose_stream_rejects_overlong_question():
    response = _client().get(
        "/compose-stream", params={"ids": "15000827", "q": "가" * 501}
    )
    assert "error" in response.text


def test_compose_stream_accepts_the_post_limit(fake_stream):
    response = _client().get(
        "/compose-stream", params={"ids": "15000827,15000863", "q": "조합 방법?"}
    )
    assert response.status_code == 200
    assert "조합 결과" in response.text
    assert response.text.endswith("data: [DONE]\n\n")


def test_compose_stream_accepts_ollama_protocol_sample_with_keep_alive_lines(
    monkeypatch,
):
    lines = (FIXTURES / "ollama_generate_stream.ndjson").read_text(
        encoding="utf-8"
    ).splitlines()
    _install_ollama_stream(monkeypatch, lines=lines)

    response = _client().get("/compose-stream", params={"ids": "15000827"})

    assert response.status_code == 200
    assert '"token": "조합"' in response.text
    assert '"token": " 결과"' in response.text
    assert '"error"' not in response.text


def test_compose_stream_reports_connect_error(monkeypatch):
    error = httpx.ConnectError(
        "connection refused",
        request=httpx.Request("POST", "http://localhost:11434/api/generate"),
    )
    _install_ollama_stream(monkeypatch, error=error)

    response = _client().get("/compose-stream", params={"ids": "15000827"})

    assert '"error"' in response.text
    assert "Ollama 연결 실패" in response.text


def test_compose_stream_reports_timeout(monkeypatch):
    error = httpx.ReadTimeout(
        "timed out",
        request=httpx.Request("POST", "http://localhost:11434/api/generate"),
    )
    _install_ollama_stream(monkeypatch, error=error)

    response = _client().get("/compose-stream", params={"ids": "15000827"})

    assert '"error"' in response.text
    assert "Ollama 응답 시간 초과" in response.text


def test_compose_stream_reports_malformed_json_and_stops(monkeypatch):
    _install_ollama_stream(
        monkeypatch,
        lines=[
            '{"response":"앞 토큰","done":false}',
            '{"response":',
            '{"response":"뒤 토큰","done":false}',
        ],
    )

    response = _client().get("/compose-stream", params={"ids": "15000827"})

    assert '"error"' in response.text
    assert "Ollama 스트림 JSON 파싱 실패" in response.text
    assert "뒤 토큰" not in response.text


def test_health_reports_docs_loaded():
    response = _client().get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["docs_loaded"] == 3
    assert body["docs_failed"] == 0


def test_health_reports_loader_failures(tmp_path):
    import shutil

    from app.loader import load_all, reset_cache

    reset_cache()
    shutil.copy(FIXTURES / "15000827.json", tmp_path / "15000827.json")
    (tmp_path / "broken.json").write_text("{broken", encoding="utf-8")
    load_all(data_dir=tmp_path)

    body = _client().get("/health").json()

    assert body["docs_loaded"] == 1
    assert body["docs_failed"] == 1

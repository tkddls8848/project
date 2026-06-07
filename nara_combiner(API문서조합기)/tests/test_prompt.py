"""prompts.py 단위 테스트."""
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def clear_cache():
    from app.loader import reset_cache
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def services():
    from app.loader import load_all, get_services
    load_all(data_dir=FIXTURES)
    found, _ = get_services(["15000827", "15000863", "15000881"])
    return found


def test_build_prompt_contains_api_names(services):
    from app.prompts import build_prompt
    prompt = build_prompt(services, "테스트 질문")
    assert "외교부_여행경보제도" in prompt
    assert "기상청_단기예보" in prompt
    assert "국토교통부_대중교통노선" in prompt


def test_build_prompt_contains_question(services):
    from app.prompts import build_prompt
    q = "고유한 테스트 질문 XYZ"
    prompt = build_prompt(services, q)
    assert q in prompt


def test_build_prompt_block_count(services):
    from app.prompts import build_prompt
    prompt = build_prompt(services, "질문")
    assert prompt.count("[API ") == 3


def test_detect_warning_same_domain():
    from app.loader import load_all, get_services
    from app.prompts import detect_warning
    load_all(data_dir=FIXTURES)
    # 교통 두 개 — 같은 최상위 도메인 없음 (fixture는 다름), 임시로 단일 서비스 테스트
    found, _ = get_services(["15000863"])
    warning = detect_warning(found)
    assert warning is None  # 1개면 경고 없음


def test_detect_warning_different_domains(services):
    from app.prompts import detect_warning
    warning = detect_warning(services)
    assert warning is None  # 통일·외교 / 기상 / 교통 → 다른 도메인


def test_detect_warning_same_top_domain():
    from app.loader import load_all, get_services
    from app.prompts import detect_warning
    # 두 교통 API 픽스처(15000881)를 두 번 — 실제로는 ID가 같아서 get_services가 1개 반환
    # 직접 Service 객체 생성으로 테스트
    from app.schemas import Service
    s1 = Service(api_id="A", name="버스", agency="국토부", domain="교통 - 버스", keywords=[], description="", endpoints=[])
    s2 = Service(api_id="B", name="지하철", agency="국토부", domain="교통 - 지하철", keywords=[], description="", endpoints=[])
    warning = detect_warning([s1, s2])
    assert warning is not None
    assert "교통" in warning

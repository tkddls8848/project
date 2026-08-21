from backend.search.coverage import (
    apply_coverage_prior,
    is_nationwide,
    query_names_region,
)


def test_full_region_names_are_regional():
    assert not is_nationwide("부산광역시")
    assert not is_nationwide("경상북도 영천시")
    assert not is_nationwide("대구광역시 북구")
    assert not is_nationwide("전남광주통합특별시")


def test_local_public_corporations_are_regional():
    """시도 정식 명칭 없이 축약 지역명으로 시작하는 지방공기업."""
    assert not is_nationwide("광주교통공사")
    assert not is_nationwide("부산교통공사")


def test_central_and_national_agencies_are_nationwide():
    assert is_nationwide("행정안전부")
    assert is_nationwide("건강보험심사평가원")
    assert is_nationwide("한국환경공단")
    assert is_nationwide("국립암센터")


def test_blank_provider_is_not_promoted():
    assert not is_nationwide("")
    assert not is_nationwide("   ")


def test_region_named_query_disables_the_prior():
    assert query_names_region("대전 병원 위치")
    assert query_names_region("경상북도 의료기관")
    assert not query_names_region("전국 병원 위치와 진료과목")

    records = [
        {"api_id": "1", "provider": "대전광역시", "score": 0.030},
        {"api_id": "2", "provider": "건강보험심사평가원", "score": 0.029},
    ]
    unchanged = apply_coverage_prior(records, "대전 병원 위치", 0.004)
    assert [r["api_id"] for r in unchanged] == ["1", "2"]
    assert unchanged[1]["score"] == 0.029


def test_prior_lifts_nationwide_above_regional():
    """관측된 실패 그대로: 지방공기업이 전국 기관을 눌렀던 점수 배치."""
    records = [
        {"api_id": "15109258", "provider": "광주교통공사", "score": 0.031250},
        {"api_id": "15001674", "provider": "건강보험심사평가원", "score": 0.029302},
    ]
    ranked = apply_coverage_prior(records, "전국 병원 위치와 진료과목", 0.004)
    assert [r["api_id"] for r in ranked] == ["15001674", "15109258"]
    assert ranked[0]["coverage_prior"] == "nationwide"
    assert "coverage_prior" not in ranked[1]
    assert ranked[1]["score"] == 0.031250


def test_zero_bonus_disables_the_feature():
    records = [
        {"api_id": "1", "provider": "광주교통공사", "score": 0.031250},
        {"api_id": "2", "provider": "행정안전부", "score": 0.029302},
    ]
    assert apply_coverage_prior(records, "전국 병원", 0.0) == records

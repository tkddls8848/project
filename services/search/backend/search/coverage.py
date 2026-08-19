"""커버리지 prior — 전국 단위 기관을 지자체·지방공기업보다 소폭 우대한다.

RRF는 합의를 보상하므로 두 채널이 크게 불일치하면 양쪽에서 어중간한 문서가
1위가 된다. 실제로 "전국 병원 위치와 진료과목" 질의에서 렉시컬 4위·벡터 4위인
지방공기업 데이터가, 렉시컬 3위·벡터 16위인 전국 단위 데이터를 눌렀다.
두 채널 어디에도 "이 데이터가 전국을 포괄한다"는 신호가 없기 때문이다.

이 모듈이 그 신호 하나를 더한다. 판정 근거는 기관명뿐이다. 카탈로그에 커버리지
필드가 없으므로 없는 값을 추론해 만들지 않는다.
"""
from typing import Any

# 광역시도 정식 명칭. "경상북도 영천시", "대구광역시 북구"처럼 하위 행정구역이
# 뒤에 붙는 형태를 함께 잡는다.
_FULL_REGION_NAMES = (
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
    "대전광역시", "울산광역시", "세종특별자치시",
    "경기도", "강원특별자치도", "강원도", "충청북도", "충청남도",
    "전라북도", "전북특별자치도", "전라남도", "전남광주통합특별시",
    "경상북도", "경상남도", "제주특별자치도",
)

# 지방공기업은 시도 정식 명칭을 안 쓴다(예: "광주교통공사", "부산교통공사").
# 축약 지역명으로 시작하면 지역 기관으로 본다. 전국 기관은 "한국"·"국립"·
# 부처명으로 시작하므로 이 접두어와 겹치지 않는다.
_SHORT_REGION_NAMES = (
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
)


def is_nationwide(provider: str) -> bool:
    """기관명이 지역 단위로 보이지 않으면 전국 단위로 본다."""
    name = (provider or "").strip()
    if not name:
        return False
    return not name.startswith(_FULL_REGION_NAMES + _SHORT_REGION_NAMES)


def query_names_region(query: str) -> bool:
    """질의가 특정 지역을 지목하면 전국 우대를 적용하지 않는다."""
    text = (query or "")
    return any(name in text for name in _FULL_REGION_NAMES + _SHORT_REGION_NAMES)


def apply_coverage_prior(
    records: list[dict[str, Any]],
    query: str,
    bonus: float,
    provider_key: str = "provider",
) -> list[dict[str, Any]]:
    """전국 단위 문서의 융합 점수에 ``bonus``를 더하고 다시 정렬한다.

    RRF 점수 위에서만 의미가 있는 값이라 호출 측이 융합 여부를 판단해 부른다.
    단일 채널일 때의 원 점수(BM25 수십 단위, 코사인 0~1)에 같은 상수를 더하면
    아무 의미가 없거나 순위를 뒤엎는다.
    """
    if bonus <= 0 or not records or query_names_region(query):
        return records

    boosted = []
    for record in records:
        item = dict(record)
        if is_nationwide(str(item.get(provider_key, ""))):
            item["score"] = round(float(item.get("score", 0.0)) + bonus, 6)
            item["coverage_prior"] = "nationwide"
        boosted.append(item)
    boosted.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    return boosted

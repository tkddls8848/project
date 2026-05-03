"""
LLM 프롬프트 템플릿 - Did You Know 콘텐츠 생성용
"""

from typing import Dict, List, Any


def get_api_introduction_prompt(api_doc: Dict[str, Any], api_id: str = "", api_type: str = "") -> str:
    """
    특정 API 소개 프롬프트

    Args:
        api_doc: {
            "title": "...",
            "provider": "...",
            "description": "...",
            "keywords": [...],
            "category": "...",
            "total_endpoints": 11,
            "api_id": "15000001"
        }
        api_id: API ID (예: "15000001")
        api_type: API 타입 (예: "openapi", "fileData", "standard")

    Returns:
        LLM 프롬프트 문자열
    """
    title = api_doc.get('title', '제목 없음')
    provider = api_doc.get('provider', '제공기관 미상')
    description = api_doc.get('description', '')[:300]
    keywords = api_doc.get('keywords', [])[:5]
    category = api_doc.get('category', '')

    url_instruction = """
[작성 지침]
1. "그거 아셨나요? [기관]에서는 [API 기능]도 제공해요!" 형식으로 시작
2. API의 독특하거나 의외의 측면 강조
3. 일상 생활과 연결
4. 전문 용어 최소화
5. 80자 이내로 간결하게 작성
6. URL이나 링크는 절대 생성하지 마세요 (시스템에서 자동 추가됨)

예시:
"그거 아셨나요? 국세청에서는 전국 모든 주유소의 실시간 유가 정보도 제공해요!"
"그거 아셨나요? 기상청에서는 1시간 뒤 동네별 미세먼지 예보까지 확인할 수 있어요!"
"""

    return f"""당신은 공공데이터 포털의 흥미로운 API를 소개하는 AI입니다.

아래 API 정보를 바탕으로 "그거 아셨나요?" 형식의 문장을 작성하세요.

[API 정보]
제목: {title}
제공기관: {provider}
카테고리: {category}
설명: {description}
키워드: {', '.join(keywords)}
{url_instruction}

한 문장만 생성하세요:"""


def get_provider_introduction_prompt(provider_data: Dict[str, Any]) -> str:
    """
    제공 기관 소개 프롬프트

    Args:
        provider_data: {
            "name": "국토교통부",
            "api_count": 234,
            "main_categories": ["교통", "건설", "부동산"],
            "doc_types": ["rest_api": 150, "file_data": 84],
            "sample_apis": ["버스 정보", "지하철 정보", ...]
        }

    Returns:
        LLM 프롬프트 문자열
    """
    name = provider_data.get('name', '기관명 미상')
    api_count = provider_data.get('api_count', 0)
    main_categories = provider_data.get('main_categories', [])[:3]
    sample_apis = provider_data.get('sample_apis', [])[:3]

    return f"""당신은 공공데이터 제공 기관을 소개하는 AI입니다.

아래 기관 정보를 바탕으로 "그거 아셨나요?" 형식의 문장을 작성하세요.

[기관 정보]
기관명: {name}
제공 API 수: {api_count}개
주요 분야: {', '.join(main_categories)}
대표 API: {', '.join(sample_apis)}

[작성 지침]
1. "그거 아셨나요? [기관]에서 [분야] 관련 데이터를 [특징]하게 제공해요!" 형식
2. API 개수나 다양성 강조
3. 기관의 의외의 면모 발굴
4. 80자 이내로 간결하게 작성
5. URL이나 링크는 절대 생성하지 마세요 (시스템에서 자동 추가됨)

예시:
"그거 아셨나요? 교육부에서 234개의 교육 데이터를 공개하고 있어요!"
"그거 아셨나요? 문화재청에서는 전국 문화재 위치와 역사를 상세히 제공해요!"
"그거 아셨나요? 국토교통부에서 교통, 건설, 부동산 등 500개 이상의 API를 운영해요!"

한 문장만 생성하세요 (URL 제외):"""


def get_usage_tip_prompt(api_doc: Dict[str, Any], api_id: str = "", api_type: str = "") -> str:
    """
    데이터 활용 팁 프롬프트

    Args:
        api_doc: {
            "title": "...",
            "provider": "...",
            "description": "...",
            "endpoints": [...],
            "total_endpoints": 5,
            "doc_type": "rest_api",
            "api_id": "15000001"
        }
        api_id: API ID (예: "15000001")
        api_type: API 타입 (예: "openapi", "fileData", "standard")

    Returns:
        LLM 프롬프트 문자열
    """
    title = api_doc.get('title', '제목 없음')
    provider = api_doc.get('provider', '제공기관 미상')
    description = api_doc.get('description', '')[:300]
    total_endpoints = api_doc.get('total_endpoints', 0)
    doc_type = api_doc.get('doc_type', 'unknown')

    url_instruction = """
[작성 지침]
1. "그거 아셨나요? [API]를 활용하면 [실용적 활용법]을 할 수 있어요!" 형식으로 시작
2. 구체적인 활용 시나리오 제시
3. 개발자가 아닌 일반인도 이해 가능하게
4. 80자 이내로 간결하게 작성
5. URL이나 링크는 절대 생성하지 마세요 (시스템에서 자동 추가됨)

예시:
"그거 아셨나요? 버스 도착 정보 API로 나만의 출퇴근 알림 앱을 만들 수 있어요!"
"그거 아셨나요? 날씨 예보 API를 활용하면 우산 챙기는 걸 깜빡하지 않을 수 있어요!"
"""

    return f"""당신은 공공데이터 활용 전문가입니다.

아래 API를 활용한 실용적인 팁을 "그거 아셨나요?" 형식으로 작성하세요.

[API 정보]
제목: {title}
제공기관: {provider}
설명: {description}
엔드포인트 수: {total_endpoints}개
타입: {doc_type}
{url_instruction}

한 문장만 생성하세요:"""


def get_reranking_prompt(article_summary: str, candidates: List[Dict[str, Any]]) -> str:
    """
    LLM 재랭킹용 프롬프트 생성

    Args:
        article_summary: 신문기사 요약본
        candidates: API 후보 목록 (Stage 1에서 추출된 30개)

    Returns:
        LLM 프롬프트 문자열
    """
    # API 리스트 포맷팅 (안전한 문자열 처리)
    apis_text = []
    for idx, api in enumerate(candidates, 1):
        keywords = api.get('keywords', [])[:5]
        keywords_str = ', '.join(keywords) if keywords else '키워드 없음'

        description = api.get('description', '')
        desc_preview = description[:150] + '...' if len(description) > 150 else description

        # Unicode 인코딩 문제 방지
        try:
            title = str(api.get('title', '제목 없음'))
            provider = str(api.get('provider', '미상'))
            # ASCII로 변환 가능한지 테스트
            _ = title.encode('utf-8', errors='ignore').decode('utf-8')
            _ = provider.encode('utf-8', errors='ignore').decode('utf-8')
            _ = desc_preview.encode('utf-8', errors='ignore').decode('utf-8')
        except:
            pass

        apis_text.append(f"""[{idx}] {title}
제공기관: {provider}
키워드: {keywords_str}
설명: {desc_preview}""")

    apis_formatted = '\n\n'.join(apis_text)

    return f"""당신은 신문기사 내용과 공공데이터 API의 관련성을 판단하는 전문가입니다.

[신문기사 내용]
{article_summary}

[API 후보 목록] (총 {len(candidates)}개)
{apis_formatted}

[작업]
위 신문기사의 주제, 등장 인물, 기관, 사건과 가장 관련성이 높은 API를 5개 선택하세요.

관련성 판단 기준:
1. 기사에서 다루는 도메인(교통, 환경, 복지 등)과 API 제공 데이터의 일치도
2. 기사 내용의 문제 해결에 API 데이터가 실제로 활용 가능한지
3. 기사에 등장하는 기관과 API 제공 기관의 관련성
4. 키워드의 의미적 유사성 (단순 단어 매칭이 아닌 맥락)

출력 형식 (반드시 이 형식을 따르세요):
1
7
15
23
28

상위 5개의 API ID(번호)만 한 줄에 하나씩 출력하세요."""

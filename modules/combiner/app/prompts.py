"""Prompt construction for API document combination."""
from .schemas import Service

_TEMPLATE = """\
당신은 공공 API 문서 조합 설계자입니다.

다음 API 문서 메타데이터를 보고, 여러 API를 함께 사용할 때 만들 수 있는 행정 서비스 계획 초안을 작성하세요.

{api_context}

질문: {question}

응답 규칙:
- 개별 API를 단독으로 열거하지 말고, 조합해야만 가능한 흐름에 집중하세요.
- 실제 정부 시스템 실행, 신청 제출, 승인 처리, 감사 로그 저장은 하지 않습니다.
- 실행이 필요한 경우 nara_openclaw(행정서비스실행기)로 넘길 수 있는 계획 관점으로 설명하세요.
- 필요한 사용자 입력값, 확인 조건, 후속 실행 후보를 구분하세요.
- 한국어로 간결하게 답하세요.
"""


def _api_block(service: Service, idx: int) -> str:
    keywords = ", ".join(service.keywords[:8]) or "없음"
    ep_paths = ", ".join(ep.get("path", "") for ep in service.endpoints[:3]) or "-"
    desc = service.description[:300] or "-"
    return (
        f"[API {idx}]\n"
        f"이름: {service.name}\n"
        f"기관: {service.agency}\n"
        f"분야: {service.domain}\n"
        f"설명: {desc}\n"
        f"주요 키워드: {keywords}\n"
        f"엔드포인트 예시: {ep_paths}"
    )


def build_prompt(services: list[Service], question: str) -> str:
    blocks = "\n\n".join(_api_block(s, i + 1) for i, s in enumerate(services))
    return _TEMPLATE.format(api_context=blocks, question=question)


def detect_warning(services: list[Service]) -> str | None:
    if len(services) < 2:
        return None
    top_domains = [s.domain.split(" - ")[0].strip() for s in services]
    if len(set(top_domains)) == 1:
        return f"모든 API가 동일한 상위 분야({top_domains[0]})입니다. 조합 가치가 낮을 수 있습니다."
    return None

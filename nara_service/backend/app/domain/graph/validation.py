"""
Graph API 입력 검증 로직 (Pure Functions)

Why: 그래프 탐색 및 AI 추론 요청의 입력값을 검증합니다.
     비즈니스 규칙(최소/최대 개수, 범위 제한 등)을 명확하게 정의합니다.

CODING_RULES 준수:
    - FP First: 순수 함수 (side-effect 없음)
    - Type Safety: 명확한 타입 힌트
    - KISS: 간단하고 명확한 검증 로직
"""
from typing import List, Tuple


# validate_depth removed - replaced by FastAPI Query(ge=0, le=3) in routers


def validate_limit(limit: int, default_limit: int = 100, max_limit: int = 500) -> int:
    """
    조회 개수 제한을 검증합니다.

    Why: 과도한 데이터 조회를 방지하여 성능을 보호합니다.

    Args:
        limit: 요청된 조회 개수
        default_limit: 기본 조회 개수
        max_limit: 최대 조회 개수

    Returns:
        제한된 조회 개수

    Example:
        >>> validate_limit(1000, max_limit=500)
        500
        >>> validate_limit(50)
        50
    """
    if limit <= 0:
        return default_limit
    return min(limit, max_limit)


def validate_suggestion_limit(limit: int) -> int:
    """
    AI 관계 추천 개수를 검증합니다.

    Why: 추천 개수를 1-10개로 제한하여 합리적인 범위 내에서 제공합니다.

    Args:
        limit: 요청된 추천 개수

    Returns:
        제한된 추천 개수 (1-10)

    Example:
        >>> validate_suggestion_limit(20)
        10
        >>> validate_suggestion_limit(0)
        1
        >>> validate_suggestion_limit(5)
        5
    """
    return min(max(limit, 1), 10)


def validate_ai_inference_documents(
    document_ids: List[str]
) -> Tuple[bool, str]:
    """
    AI 관계 추론을 위한 문서 ID 목록을 검증합니다.

    Why: AI 추론은 최소 2개, 최대 10개의 문서가 필요합니다.
         너무 적으면 관계를 추론할 수 없고,
         너무 많으면 처리 시간이 과도하게 길어집니다.

    Args:
        document_ids: 문서 ID 목록

    Returns:
        (검증 성공 여부, 에러 메시지)
        성공 시: (True, "")
        실패 시: (False, "에러 메시지")

    Example:
        >>> validate_ai_inference_documents(["doc1", "doc2"])
        (True, '')
        >>> validate_ai_inference_documents(["doc1"])
        (False, 'At least 2 documents required')
        >>> validate_ai_inference_documents(["doc" + str(i) for i in range(15)])
        (False, 'Maximum 10 documents allowed')
    """
    if len(document_ids) < 2:
        return False, "At least 2 documents required"

    if len(document_ids) > 10:
        return False, "Maximum 10 documents allowed"

    return True, ""

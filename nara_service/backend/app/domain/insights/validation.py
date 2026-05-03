"""
Insights 파라미터 검증 Pure Functions

Why: Insights API의 입력 파라미터 검증 로직을 Pure Functions로 분리하여
     재사용성과 테스트 가능성을 높입니다.
     비즈니스 규칙을 Domain Layer에 캡슐화합니다.

CODING_RULES 준수:
    - Pure Functions: 부수 효과 없는 순수 함수
    - Type Safety: 완전한 타입 힌트
    - FP First: 함수형 프로그래밍 우선
"""
from typing import Tuple


def validate_chain_length(
    min_length: int,
    max_length: int,
    min_allowed: int = 1,
    max_allowed: int = 6
) -> Tuple[int, int]:
    """
    관계 체인 길이를 검증하고 유효한 범위로 조정합니다.

    Why: Neo4j 쿼리 성능을 보호하기 위해 체인 길이를 제한합니다.
         너무 긴 체인은 지수적으로 성능이 저하됩니다.

    Args:
        min_length: 최소 체인 길이
        max_length: 최대 체인 길이
        min_allowed: 허용되는 최소값 (기본값: 1)
        max_allowed: 허용되는 최대값 (기본값: 6)

    Returns:
        (조정된 min_length, 조정된 max_length) 튜플

    Example:
        >>> validate_chain_length(0, 10)
        (1, 6)
        >>> validate_chain_length(3, 2)
        (3, 3)
    """
    # min_length를 허용 범위로 조정
    validated_min = max(min_allowed, min(min_length, max_allowed))

    # max_length를 허용 범위로 조정하되, min_length보다 작지 않도록
    validated_max = max(validated_min, min(max_length, max_allowed))

    return validated_min, validated_max


def validate_insights_limit(
    limit: int,
    max_limit: int = 50,
    min_limit: int = 1
) -> int:
    """
    Insights API의 결과 개수 제한을 검증합니다.

    Why: API 응답 크기를 제한하여 클라이언트와 서버 성능을 보호합니다.
         대량의 결과는 네트워크 대역폭과 메모리를 소비합니다.

    Args:
        limit: 요청된 결과 개수
        max_limit: 허용되는 최대 개수 (기본값: 50)
        min_limit: 허용되는 최소 개수 (기본값: 1)

    Returns:
        조정된 limit 값

    Example:
        >>> validate_insights_limit(100)
        50
        >>> validate_insights_limit(-5)
        1
        >>> validate_insights_limit(30)
        30
    """
    return max(min_limit, min(limit, max_limit))


def validate_community_size(
    min_size: int,
    min_allowed: int = 2,
    max_allowed: int = 20
) -> int:
    """
    커뮤니티 최소 크기를 검증합니다.

    Why: 너무 작은 커뮤니티(1-2개 노드)는 의미가 없고,
         너무 큰 최소 크기는 유용한 커뮤니티를 놓칠 수 있습니다.

    Args:
        min_size: 요청된 최소 커뮤니티 크기
        min_allowed: 허용되는 최소값 (기본값: 2)
        max_allowed: 허용되는 최대값 (기본값: 20)

    Returns:
        조정된 min_size 값

    Example:
        >>> validate_community_size(1)
        2
        >>> validate_community_size(50)
        20
        >>> validate_community_size(5)
        5
    """
    return max(min_allowed, min(min_size, max_allowed))


def validate_centrality_limit(
    limit: int,
    max_limit: int = 100,
    min_limit: int = 1
) -> int:
    """
    중심성 분석 결과 개수 제한을 검증합니다.

    Why: 중심성 계산은 전체 그래프를 분석하므로 비용이 높습니다.
         결과 개수를 제한하여 상위 중요 노드만 반환합니다.

    Args:
        limit: 요청된 결과 개수
        max_limit: 허용되는 최대 개수 (기본값: 100)
        min_limit: 허용되는 최소 개수 (기본값: 1)

    Returns:
        조정된 limit 값

    Example:
        >>> validate_centrality_limit(200)
        100
        >>> validate_centrality_limit(50)
        50
    """
    return max(min_limit, min(limit, max_limit))


def validate_hidden_connections_limit(
    limit: int,
    max_limit: int = 50,
    min_limit: int = 1
) -> int:
    """
    숨겨진 연결 탐색 결과 개수 제한을 검증합니다.

    Why: 간접 연결 탐색은 2-hop 이상의 경로를 찾으므로
         결과가 폭발적으로 증가할 수 있습니다.

    Args:
        limit: 요청된 결과 개수
        max_limit: 허용되는 최대 개수 (기본값: 50)
        min_limit: 허용되는 최소 개수 (기본값: 1)

    Returns:
        조정된 limit 값

    Example:
        >>> validate_hidden_connections_limit(100)
        50
        >>> validate_hidden_connections_limit(10)
        10
    """
    return max(min_limit, min(limit, max_limit))


def validate_complementary_data_limit(
    limit: int,
    max_limit: int = 50,
    min_limit: int = 1
) -> int:
    """
    보완 데이터 추천 결과 개수 제한을 검증합니다.

    Why: 추천 알고리즘은 그래프 구조 분석이 필요하므로
         결과 개수를 제한하여 성능을 보호합니다.

    Args:
        limit: 요청된 결과 개수
        max_limit: 허용되는 최대 개수 (기본값: 50)
        min_limit: 허용되는 최소 개수 (기본값: 1)

    Returns:
        조정된 limit 값

    Example:
        >>> validate_complementary_data_limit(80)
        50
        >>> validate_complementary_data_limit(20)
        20
    """
    return max(min_limit, min(limit, max_limit))

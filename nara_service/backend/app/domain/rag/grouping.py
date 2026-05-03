"""
RAG 청크 그룹핑 로직 (Pure Functions)

Why: 검색된 청크들을 doc_id별로 그룹핑하여 중복을 제거합니다.
     동일 문서의 여러 청크를 하나의 검색 결과로 통합하기 위함입니다.

CODING_RULES 준수:
    - FP First: 모든 함수는 순수 함수 (side-effect 없음)
    - Type Safety: 모든 함수에 타입 힌트 명시
    - DRY: 중복 로직을 재사용 가능한 함수로 추출
"""
from typing import Dict, List, Any, Tuple


def group_chunks_by_doc_id(chunks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    청크들을 doc_id별로 그룹핑합니다.

    Why: 동일 문서의 여러 청크(document chunk, endpoint chunks)를
         하나로 통합하여 사용자에게 문서 단위로 검색 결과를 제공합니다.
         이는 중복된 문서가 검색 결과에 여러 번 나타나는 것을 방지합니다.

    Technical Details:
        - document chunk: 문서 전체 정보를 담은 청크
        - endpoint chunk: 각 API 엔드포인트 정보를 담은 청크
        - max_score: 그룹 내 최고 점수 (정렬 기준)

    Args:
        chunks: 검색된 청크 리스트
            각 청크는 다음 필드를 포함해야 함:
            - metadata.doc_id: 문서 ID
            - chunk_type: 'document' 또는 'endpoint'
            - score: 유사도 점수 (0.0~1.0)

    Returns:
        doc_id를 키로 하는 그룹 딕셔너리
        각 그룹은 다음 구조:
        {
            'doc_chunk': document 타입 청크 (Optional),
            'endpoint_chunks': endpoint 타입 청크 리스트,
            'max_score': 그룹 내 최대 점수,
            'chunks': 모든 청크 리스트
        }

    Example:
        >>> chunks = [
        ...     {'metadata': {'doc_id': 'api_123'}, 'chunk_type': 'document', 'score': 0.9},
        ...     {'metadata': {'doc_id': 'api_123'}, 'chunk_type': 'endpoint', 'score': 0.85},
        ...     {'metadata': {'doc_id': 'api_456'}, 'chunk_type': 'document', 'score': 0.7}
        ... ]
        >>> groups = group_chunks_by_doc_id(chunks)
        >>> len(groups)
        2
        >>> groups['api_123']['max_score']
        0.9
    """
    groups: Dict[str, Dict[str, Any]] = {}

    for chunk in chunks:
        metadata = chunk.get('metadata', {})
        doc_id = metadata.get('doc_id', '')

        # 새로운 doc_id인 경우 그룹 초기화
        if doc_id not in groups:
            groups[doc_id] = {
                'doc_chunk': None,
                'endpoint_chunks': [],
                'max_score': chunk.get('score', 0.0),
                'chunks': []
            }

        # 최대 점수 갱신
        current_score = chunk.get('score', 0.0)
        groups[doc_id]['max_score'] = max(
            groups[doc_id]['max_score'],
            current_score
        )

        # 청크 저장
        groups[doc_id]['chunks'].append(chunk)

        # 청크 타입별로 분류
        chunk_type = chunk.get('chunk_type', 'unknown')
        if chunk_type == 'document':
            groups[doc_id]['doc_chunk'] = chunk
        elif chunk_type == 'endpoint':
            groups[doc_id]['endpoint_chunks'].append(chunk)

    return groups


def sort_groups_by_score(
    groups: Dict[str, Dict[str, Any]],
    limit: int
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    그룹들을 최대 점수 기준으로 정렬하고 상위 N개만 반환합니다.

    Why: 가장 관련도가 높은 문서들을 우선적으로 사용자에게 보여주기 위함입니다.

    Args:
        groups: doc_id를 키로 하는 그룹 딕셔너리
        limit: 반환할 최대 그룹 개수

    Returns:
        (doc_id, group) 튜플의 리스트 (점수 내림차순 정렬)

    Example:
        >>> groups = {
        ...     'api_123': {'max_score': 0.9, ...},
        ...     'api_456': {'max_score': 0.7, ...},
        ...     'api_789': {'max_score': 0.95, ...}
        ... }
        >>> sorted_groups = sort_groups_by_score(groups, limit=2)
        >>> sorted_groups[0][0]  # 가장 높은 점수의 doc_id
        'api_789'
        >>> len(sorted_groups)
        2
    """
    sorted_items = sorted(
        groups.items(),
        key=lambda item: item[1]['max_score'],
        reverse=True
    )
    return sorted_items[:limit]


def sort_endpoints_by_score(
    endpoint_chunks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    엔드포인트 청크들을 점수 기준으로 정렬합니다.

    Why: 가장 관련도 높은 엔드포인트를 먼저 표시하기 위함입니다.

    Args:
        endpoint_chunks: 엔드포인트 청크 리스트

    Returns:
        점수 내림차순으로 정렬된 엔드포인트 청크 리스트

    Example:
        >>> endpoints = [
        ...     {'score': 0.7, 'metadata': {'endpoint_path': '/api/v1/data'}},
        ...     {'score': 0.9, 'metadata': {'endpoint_path': '/api/v2/search'}},
        ... ]
        >>> sorted_eps = sort_endpoints_by_score(endpoints)
        >>> sorted_eps[0]['score']
        0.9
    """
    return sorted(
        endpoint_chunks,
        key=lambda chunk: chunk.get('score', 0.0),
        reverse=True
    )

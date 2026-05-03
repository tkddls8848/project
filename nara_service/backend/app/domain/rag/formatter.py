"""
RAG 검색 결과 포맷팅 로직 (Pure Functions)

Why: 그룹핑된 청크 데이터를 API 응답 형식으로 변환합니다.
     Frontend와의 인터페이스를 명확하게 정의하고 재사용성을 높입니다.

CODING_RULES 준수:
    - FP First: 모든 함수는 순수 함수 (입력 → 출력, side-effect 없음)
    - Type Safety: 명확한 타입 힌트
    - KISS: 간단하고 명확한 로직
"""
from typing import Dict, List, Any, Optional


def format_search_result(
    doc_id: str,
    group: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    그룹핑된 청크를 검색 결과 형식으로 변환합니다.

    Why: Frontend가 기대하는 JSON 형식으로 데이터를 변환합니다.
         일관된 응답 구조를 유지하여 Frontend 코드의 안정성을 보장합니다.

    Technical Details:
        - doc_chunk가 없으면 첫 번째 endpoint_chunk를 대표로 사용
        - 청크가 전혀 없으면 None 반환 (필터링됨)
        - content는 300자로 제한 (preview)

    Args:
        doc_id: 문서 ID
        group: 그룹 딕셔너리
            - doc_chunk: document 타입 청크
            - endpoint_chunks: endpoint 타입 청크 리스트
            - max_score: 최대 점수

    Returns:
        검색 결과 딕셔너리 또는 None (청크가 없는 경우)
        {
            "chunk_id": str,
            "score": float,
            "doc_id": str,
            "api_id": str,
            "title": str,
            "provider": str,
            "doc_type": str,
            "content_preview": str,
            "metadata": dict,
            "endpoints": list
        }

    Example:
        >>> group = {
        ...     'doc_chunk': {'chunk_id': 'doc_123', 'content': 'API documentation...', 'metadata': {...}},
        ...     'endpoint_chunks': [...],
        ...     'max_score': 0.9
        ... }
        >>> result = format_search_result('api_123', group)
        >>> result['score']
        0.9
        >>> result['doc_id']
        'api_123'
    """
    doc_chunk = group['doc_chunk']
    endpoint_chunks = group['endpoint_chunks']

    # 대표 청크 선택
    if not doc_chunk:
        if endpoint_chunks:
            # document chunk가 없으면 첫 엔드포인트를 대표로 사용
            doc_chunk = endpoint_chunks[0]
        else:
            # 청크가 전혀 없으면 건너뜀
            return None

    metadata = doc_chunk.get('metadata', {})
    content = doc_chunk.get('content', '')

    # 콘텐츠 미리보기 (300자 제한)
    content_preview = (
        content[:300] + "..." if len(content) > 300 else content
    )

    # 기본 문서 정보 구성
    result = {
        "chunk_id": doc_chunk.get('chunk_id', ''),
        "score": group['max_score'],
        "doc_id": metadata.get('doc_id', ''),
        "api_id": metadata.get('api_id', ''),
        "title": metadata.get('title', ''),
        "provider": metadata.get('provider', ''),
        "doc_type": metadata.get('doc_type', ''),
        "content_preview": content_preview,
        "metadata": metadata,
        "endpoints": []  # 엔드포인트 정보는 별도로 추가
    }

    return result


def format_endpoint_info(
    endpoint_chunk: Dict[str, Any]
) -> Dict[str, Any]:
    """
    엔드포인트 청크를 엔드포인트 정보 형식으로 변환합니다.

    Why: API 엔드포인트 상세 정보를 구조화하여 제공합니다.
         Frontend에서 엔드포인트별로 표시할 수 있도록 합니다.

    Args:
        endpoint_chunk: 엔드포인트 청크

    Returns:
        엔드포인트 정보 딕셔너리
        {
            "path": str,
            "method": str,
            "operation_id": str,
            "summary": str,
            "url_template": str,
            "required_params": list[str],
            "optional_params": list[str],
            "score": float
        }

    Example:
        >>> chunk = {
        ...     'metadata': {
        ...         'endpoint_path': '/api/v1/search',
        ...         'method': 'GET',
        ...         'summary': 'Search API',
        ...         'required_params': ['q'],
        ...         'optional_params': ['limit']
        ...     },
        ...     'score': 0.85
        ... }
        >>> info = format_endpoint_info(chunk)
        >>> info['path']
        '/api/v1/search'
        >>> info['method']
        'GET'
    """
    metadata = endpoint_chunk.get('metadata', {})

    return {
        "path": metadata.get('endpoint_path', ''),
        "method": metadata.get('method', 'GET'),
        "operation_id": metadata.get('operation_id', ''),
        "summary": metadata.get('summary', ''),
        "url_template": metadata.get('url_template', ''),
        "required_params": metadata.get('required_params', []),
        "optional_params": metadata.get('optional_params', []),
        "score": endpoint_chunk.get('score', 0.0)
    }


def format_batch_results(
    sorted_groups: List[tuple[str, Dict[str, Any]]],
    include_endpoints: bool = True
) -> List[Dict[str, Any]]:
    """
    여러 그룹을 일괄 변환합니다.

    Why: 반복 로직을 줄이고 일관된 변환을 보장합니다.

    Args:
        sorted_groups: (doc_id, group) 튜플의 리스트
        include_endpoints: 엔드포인트 정보 포함 여부

    Returns:
        변환된 검색 결과 리스트

    Example:
        >>> groups = [
        ...     ('api_123', {'doc_chunk': {...}, 'endpoint_chunks': [...], 'max_score': 0.9}),
        ...     ('api_456', {'doc_chunk': {...}, 'endpoint_chunks': [], 'max_score': 0.7})
        ... ]
        >>> results = format_batch_results(groups)
        >>> len(results)
        2
    """
    results = []

    for doc_id, group in sorted_groups:
        # 기본 결과 변환
        result = format_search_result(doc_id, group)

        if result is None:
            # 청크가 없는 경우 건너뜀
            continue

        # 엔드포인트 정보 추가
        if include_endpoints:
            endpoint_chunks = group['endpoint_chunks']

            # 엔드포인트들을 점수순으로 정렬 (이미 grouping.py에서 처리 가능)
            from .grouping import sort_endpoints_by_score
            sorted_endpoints = sort_endpoints_by_score(endpoint_chunks)

            # 각 엔드포인트 정보 변환
            result['endpoints'] = [
                format_endpoint_info(ep_chunk)
                for ep_chunk in sorted_endpoints
            ]

        results.append(result)

    return results

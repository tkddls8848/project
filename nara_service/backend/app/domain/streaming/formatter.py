"""
스트리밍 메시지 포맷팅 로직 (Pure Functions)

Why: general.py와 prometheus.py에서 반복되는 스트리밍 메시지 생성 로직을
     Pure Functions로 추출하여 재사용성과 테스트 가능성을 높입니다.

CODING_RULES 준수:
    - FP First: 모든 함수는 순수 함수 (side-effect 없음)
    - Type Safety: 명확한 타입 힌트
    - DRY: 중복 메시지 생성 로직 제거
"""
import json
from typing import Any, Dict, List


def create_stream_message(message_type: str, data: Any) -> str:
    """
    스트리밍 메시지를 JSON 형식으로 생성합니다.

    Why: NDJSON(Newline Delimited JSON) 형식의 스트리밍 응답을 표준화합니다.
         Frontend가 일관된 형식으로 메시지를 파싱할 수 있도록 합니다.

    Args:
        message_type: 메시지 타입 (documents, related_documents, token, done, error)
        data: 전송할 데이터 (딕셔너리, 리스트, 문자열 등)

    Returns:
        NDJSON 형식 문자열 (줄바꿈 포함)

    Example:
        >>> msg = create_stream_message("token", "Hello")
        >>> msg
        '{"type": "token", "data": "Hello"}\\n'

        >>> msg = create_stream_message("documents", [{"id": "1", "title": "Doc1"}])
        >>> "documents" in msg
        True
    """
    return json.dumps({
        "type": message_type,
        "data": data
    }, ensure_ascii=False) + "\n"


def create_documents_message(
    documents: List[Dict[str, Any]],
    total_count: int
) -> str:
    """
    검색 결과 문서 메시지를 생성합니다.

    Why: 메인 검색 결과를 전송할 때 사용하는 표준 형식입니다.

    Args:
        documents: 검색된 문서 리스트
        total_count: 전체 문서 개수

    Returns:
        NDJSON 형식 문자열

    Example:
        >>> docs = [{"id": "1", "title": "API Guide"}]
        >>> msg = create_documents_message(docs, total_count=100)
        >>> '"type": "documents"' in msg
        True
    """
    return json.dumps({
        "type": "documents",
        "data": documents,
        "total": total_count
    }, ensure_ascii=False) + "\n"


def create_related_documents_message(
    related_docs: List[Dict[str, Any]],
    insights: List[str]
) -> str:
    """
    Neo4j 관련 문서 메시지를 생성합니다.

    Why: 그래프 탐색을 통해 발견된 관련 문서와 컨텍스트 정보를 전송합니다.

    Args:
        related_docs: 관련 문서 리스트
        insights: 관계 기반 인사이트 메시지 리스트

    Returns:
        NDJSON 형식 문자열

    Example:
        >>> related = [{"id": "2", "title": "Related API"}]
        >>> insights = ["이 API는 X와 연관됩니다"]
        >>> msg = create_related_documents_message(related, insights)
        >>> '"type": "related_documents"' in msg
        True
    """
    return json.dumps({
        "type": "related_documents",
        "data": related_docs,
        "insights": insights
    }, ensure_ascii=False) + "\n"


def create_token_message(token: str) -> str:
    """
    LLM 스트리밍 토큰 메시지를 생성합니다.

    Why: LLM이 생성하는 텍스트 토큰을 실시간으로 전송합니다.

    Args:
        token: LLM이 생성한 텍스트 토큰

    Returns:
        NDJSON 형식 문자열

    Example:
        >>> msg = create_token_message("안녕하세요")
        >>> '"type": "token"' in msg
        True
        >>> '"data": "안녕하세요"' in msg
        True
    """
    return json.dumps({
        "type": "token",
        "data": token
    }, ensure_ascii=False) + "\n"


def create_done_message() -> str:
    """
    스트리밍 완료 메시지를 생성합니다.

    Why: Frontend가 스트리밍이 끝났음을 감지하고
         로딩 상태를 종료할 수 있도록 신호를 보냅니다.

    Returns:
        NDJSON 형식 문자열

    Example:
        >>> msg = create_done_message()
        >>> msg
        '{"type": "done"}\\n'
    """
    return json.dumps({"type": "done"}, ensure_ascii=False) + "\n"


def create_error_message(error_detail: str) -> str:
    """
    에러 메시지를 생성합니다.

    Why: 스트리밍 중 발생한 에러를 Frontend에 전달하여
         사용자에게 적절한 에러 메시지를 표시할 수 있도록 합니다.

    Args:
        error_detail: 에러 상세 메시지

    Returns:
        NDJSON 형식 문자열

    Example:
        >>> msg = create_error_message("Database connection failed")
        >>> '"type": "error"' in msg
        True
        >>> '"data": "Database connection failed"' in msg
        True
    """
    return json.dumps({
        "type": "error",
        "data": error_detail
    }, ensure_ascii=False) + "\n"


def should_send_related_documents(
    related_docs: List[Dict[str, Any]],
    insights: List[str]
) -> bool:
    """
    관련 문서 메시지를 전송해야 하는지 판단합니다.

    Why: 관련 문서나 인사이트가 없으면 불필요한 메시지를 보내지 않습니다.

    Args:
        related_docs: 관련 문서 리스트
        insights: 인사이트 리스트

    Returns:
        전송 여부 (True/False)

    Example:
        >>> should_send_related_documents([], [])
        False
        >>> should_send_related_documents([{"id": "1"}], [])
        True
        >>> should_send_related_documents([], ["insight"])
        True
    """
    return bool(related_docs or insights)

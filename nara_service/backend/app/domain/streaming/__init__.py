"""
Streaming Domain Layer

Why: 스트리밍 응답 생성 시 사용되는 공통 포맷팅 로직을 제공합니다.
"""
from .formatter import (
    create_stream_message,
    create_documents_message,
    create_related_documents_message,
    create_token_message,
    create_done_message,
    create_error_message,
    should_send_related_documents,
)

__all__ = [
    "create_stream_message",
    "create_documents_message",
    "create_related_documents_message",
    "create_token_message",
    "create_done_message",
    "create_error_message",
    "should_send_related_documents",
]

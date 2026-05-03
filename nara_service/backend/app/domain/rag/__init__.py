"""
RAG Domain Layer

Why: RAG 관련 순수 비즈니스 로직을 포함합니다.
     청크 그룹핑, 포맷팅 등 재사용 가능한 Pure Functions를 제공합니다.
"""
from .grouping import group_chunks_by_doc_id, sort_groups_by_score
from .formatter import format_search_result, format_endpoint_info, format_batch_results

__all__ = [
    "group_chunks_by_doc_id",
    "sort_groups_by_score",
    "format_search_result",
    "format_endpoint_info",
    "format_batch_results",
]

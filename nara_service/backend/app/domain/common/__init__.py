"""
Common Domain Layer

Why: 프로젝트 전체에서 사용되는 공통 타입과 패턴을 제공합니다.
"""
from .result import Result
from .dependencies import (
    set_rag_service,
    set_search_rag_service,
    set_prometheus_service,
    set_ai_inferrer,
    set_neo4j_service,
    set_insight_engine,
    get_rag_service,
    get_search_rag_service,
    get_prometheus_service,
    get_ai_inferrer,
    get_neo4j_service,
    get_insight_engine,
    get_rag_service_optional,
    get_search_rag_service_optional,
)

__all__ = [
    "Result",
    "set_rag_service",
    "set_search_rag_service",
    "set_prometheus_service",
    "set_ai_inferrer",
    "set_neo4j_service",
    "set_insight_engine",
    "get_rag_service",
    "get_search_rag_service",
    "get_prometheus_service",
    "get_ai_inferrer",
    "get_neo4j_service",
    "get_insight_engine",
    "get_rag_service_optional",
    "get_search_rag_service_optional",
]

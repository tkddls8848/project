"""
의존성 주입 헬퍼 (FastAPI Depends)

Why: 전역 변수 대신 의존성 주입 패턴을 사용하여
     테스트 용이성과 타입 안전성을 보장합니다.
     모든 라우터에서 중복되는 서비스 초기화 체크 로직을 제거합니다.

CODING_RULES 준수:
    - Dependency Injection: 전역 변수 대신 FastAPI Depends 사용
    - Type Safety: 명확한 타입 힌트
    - DRY: ServiceRegistry 패턴으로 중복 제거
"""
from typing import Optional, TYPE_CHECKING

from app.domain.common.service_registry import ServiceRegistry

if TYPE_CHECKING:
    from app.services.rag_service import RAGService
    from app.services.search_rag_service import SearchRAGService
    from app.services.prometheus_service import PrometheusService
    from app.services.ai_relationship_inferrer import AIRelationshipInferrer
    from app.services.relationship_chat_service import RelationshipChatService
    from app.services.didyouknow_service import DidYouKnowService
    from app.services.neo4j_service import Neo4jService
    from app.services.insight_engine import InsightEngine


# ==================== Setter Functions ====================
# main.py에서 서비스 초기화 시 호출
# 내부적으로 ServiceRegistry를 사용하여 중복 제거

def set_rag_service(service: 'RAGService') -> None:
    """RAG 서비스 인스턴스를 주입합니다."""
    from app.services.rag_service import RAGService
    ServiceRegistry.register(RAGService, service)


def set_search_rag_service(service: 'SearchRAGService') -> None:
    """SearchRAG 서비스 인스턴스를 주입합니다."""
    from app.services.search_rag_service import SearchRAGService
    ServiceRegistry.register(SearchRAGService, service)


def set_prometheus_service(service: 'PrometheusService') -> None:
    """Prometheus 서비스 인스턴스를 주입합니다."""
    from app.services.prometheus_service import PrometheusService
    ServiceRegistry.register(PrometheusService, service)


def set_ai_inferrer(inferrer: 'AIRelationshipInferrer') -> None:
    """AI Relationship Inferrer 인스턴스를 주입합니다."""
    from app.services.ai_relationship_inferrer import AIRelationshipInferrer
    ServiceRegistry.register(AIRelationshipInferrer, inferrer)


def set_chat_service(service: 'RelationshipChatService') -> None:
    """Relationship Chat 서비스 인스턴스를 주입합니다."""
    from app.services.relationship_chat_service import RelationshipChatService
    ServiceRegistry.register(RelationshipChatService, service)


def set_didyouknow_service(service: 'DidYouKnowService') -> None:
    """Did You Know 서비스 인스턴스를 주입합니다."""
    from app.services.didyouknow_service import DidYouKnowService
    ServiceRegistry.register(DidYouKnowService, service)


def set_neo4j_service(service: 'Neo4jService') -> None:
    """Neo4j 서비스 인스턴스를 주입합니다."""
    from app.services.neo4j_service import Neo4jService
    ServiceRegistry.register(Neo4jService, service)


def set_insight_engine(engine: 'InsightEngine') -> None:
    """Insight Engine 인스턴스를 주입합니다."""
    from app.services.insight_engine import InsightEngine
    ServiceRegistry.register(InsightEngine, engine)


# ==================== Dependency Functions (FastAPI Depends) ====================
# 라우터에서 Depends()로 사용
# 내부적으로 ServiceRegistry를 사용하여 중복 제거

def get_rag_service() -> 'RAGService':
    """
    RAG 서비스 인스턴스를 반환합니다.

    Returns:
        RAGService 인스턴스

    Raises:
        HTTPException: 서비스가 초기화되지 않은 경우 503 에러
    """
    from app.services.rag_service import RAGService
    return ServiceRegistry.get(RAGService)


def get_search_rag_service() -> 'SearchRAGService':
    """SearchRAG 서비스 인스턴스를 반환합니다."""
    from app.services.search_rag_service import SearchRAGService
    return ServiceRegistry.get(SearchRAGService)


def get_prometheus_service() -> 'PrometheusService':
    """Prometheus 서비스 인스턴스를 반환합니다."""
    from app.services.prometheus_service import PrometheusService
    return ServiceRegistry.get(PrometheusService)


def get_ai_inferrer() -> 'AIRelationshipInferrer':
    """AI Relationship Inferrer 인스턴스를 반환합니다."""
    from app.services.ai_relationship_inferrer import AIRelationshipInferrer
    return ServiceRegistry.get(AIRelationshipInferrer)


def get_chat_service() -> 'RelationshipChatService':
    """Relationship Chat 서비스 인스턴스를 반환합니다."""
    from app.services.relationship_chat_service import RelationshipChatService
    return ServiceRegistry.get(RelationshipChatService)


def get_didyouknow_service() -> 'DidYouKnowService':
    """Did You Know 서비스 인스턴스를 반환합니다."""
    from app.services.didyouknow_service import DidYouKnowService
    return ServiceRegistry.get(DidYouKnowService)


def get_neo4j_service() -> 'Neo4jService':
    """Neo4j 서비스 인스턴스를 반환합니다."""
    from app.services.neo4j_service import Neo4jService
    return ServiceRegistry.get(Neo4jService)


def get_insight_engine() -> 'InsightEngine':
    """Insight Engine 인스턴스를 반환합니다."""
    from app.services.insight_engine import InsightEngine
    return ServiceRegistry.get(InsightEngine)


# ==================== Optional Dependencies ====================
# 서비스가 없어도 에러를 던지지 않는 경우

def get_rag_service_optional() -> Optional['RAGService']:
    """RAG 서비스를 반환하되, 없으면 None을 반환합니다."""
    from app.services.rag_service import RAGService
    return ServiceRegistry.get_optional(RAGService)


def get_search_rag_service_optional() -> Optional['SearchRAGService']:
    """SearchRAG 서비스를 반환하되, 없으면 None을 반환합니다."""
    from app.services.search_rag_service import SearchRAGService
    return ServiceRegistry.get_optional(SearchRAGService)


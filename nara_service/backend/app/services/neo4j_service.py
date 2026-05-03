"""
Neo4j Service - Backward Compatibility Facade

이 파일은 기존 코드와의 호환성을 위한 Facade입니다.
실제 구현은 services/neo4j/ 모듈로 분해되었습니다.

분해된 구조:
- ConnectionManager: 연결 풀 관리
- DocumentRepository: 문서 CRUD
- GraphExplorer: 그래프 탐색
- PathFinder: 경로 찾기
- RelationshipManager: 사용자 정의 관계 CRUD
- RelationshipSuggester: AI 기반 관계 추천
"""

import logging
from typing import Any, Dict, Optional
from neo4j import Driver, Session

from app.domain.common.result import Result
from app.services.neo4j import (
    connection_manager,
    DocumentRepository,
    GraphExplorer,
    PathFinder,
    RelationshipManager,
    RelationshipSuggester,
)

logger = logging.getLogger(__name__)


class Neo4jService:
    """
    Neo4j Service Facade (호환성 레이어)

    기존 코드와의 호환성을 위해 동일한 인터페이스를 제공합니다.
    내부적으로는 분해된 서비스들을 위임(delegation)합니다.
    """

    _instance = None
    _driver: Optional[Driver] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jService, cls).__new__(cls)
            # 분해된 서비스 초기화
            cls._instance._conn = connection_manager
            cls._instance._doc_repo = DocumentRepository(connection_manager)
            cls._instance._graph_explorer = GraphExplorer(connection_manager)
            cls._instance._path_finder = PathFinder(connection_manager)
            cls._instance._rel_manager = RelationshipManager(connection_manager)
            cls._instance._rel_suggester = RelationshipSuggester(connection_manager)
        return cls._instance

    def __init__(self):
        # Singleton - 초기화는 __new__에서 처리
        self._driver = self._conn._driver
        self._cache = self._conn._cache

    # ==========================================
    # Connection Management (위임)
    # ==========================================

    def _verify_connection(self):
        """연결 확인"""
        return self._conn._verify_connection()

    def get_session(self) -> Session:
        """세션 획득"""
        return self._conn.get_session()

    def close(self):
        """드라이버 종료"""
        return self._conn.close()

    def initialize_indexes(self):
        """Neo4j 인덱스 및 제약조건 초기화"""
        return self._conn.initialize_indexes()

    @staticmethod
    def _serialize_neo4j_types(obj: Any) -> Any:
        """Neo4j 타입을 JSON 직렬화 가능한 타입으로 변환"""
        return GraphExplorer._serialize_neo4j_types(obj)

    def _invalidate_graph_cache(self, *doc_ids: str):
        """그래프 관련 캐시 무효화"""
        return self._conn.invalidate_graph_cache(*doc_ids)

    # ==========================================
    # Document Repository (위임)
    # ==========================================

    def upsert_document(self, doc_data: Dict[str, Any]) -> Result[None]:
        """문서 및 관련 메타데이터를 그래프에 저장"""
        return self._doc_repo.upsert_document(doc_data)

    def get_related_context(self, api_ids: list[str]) -> Result[list[str]]:
        """주어진 문서 ID 목록과 연관된 추가 정보(Context)를 검색"""
        return self._doc_repo.get_related_context(api_ids)

    # ==========================================
    # Graph Explorer (위임)
    # ==========================================

    def explore_graph(self, doc_id: str, depth: int = 2) -> Result[Dict[str, Any]]:
        """특정 문서 주변의 그래프 데이터를 depth 단계까지 탐색"""
        return self._graph_explorer.explore_graph(doc_id, depth)

    def get_graph_summary(self) -> Result[Dict[str, Any]]:
        """전체 그래프 통계 및 상위 엔티티 조회"""
        return self._graph_explorer.get_graph_summary()

    # ==========================================
    # Path Finder (위임)
    # ==========================================

    def find_shortest_path(self, source_id: str, target_id: str) -> Result[Dict[str, Any]]:
        """두 문서 간 최단 경로 탐색"""
        return self._path_finder.find_shortest_path(source_id, target_id)

    # ==========================================
    # Relationship Manager (위임)
    # ==========================================

    def create_custom_relationship(
        self,
        source_id: str,
        target_id: str,
        custom_type: str,
        description: str,
        strength: float = None
    ) -> Result[Dict[str, Any]]:
        """사용자 정의 관계 생성"""
        return self._rel_manager.create_custom_relationship(
            source_id, target_id, custom_type, description, strength
        )

    def get_custom_relationship(self, rel_id: str) -> Result[Dict[str, Any]]:
        """사용자 정의 관계 조회"""
        return self._rel_manager.get_custom_relationship(rel_id)

    def update_custom_relationship(
        self,
        rel_id: str,
        custom_type: str = None,
        description: str = None,
        strength: float = None
    ) -> Result[Dict[str, Any]]:
        """사용자 정의 관계 수정"""
        return self._rel_manager.update_custom_relationship(
            rel_id, custom_type, description, strength
        )

    def delete_custom_relationship(self, rel_id: str) -> Result[bool]:
        """사용자 정의 관계 삭제"""
        return self._rel_manager.delete_custom_relationship(rel_id)

    def list_user_relationships(self, limit: int = 100) -> Result[Dict[str, Any]]:
        """사용자 정의 관계 목록 조회"""
        return self._rel_manager.list_user_relationships(limit)

    # ==========================================
    # Relationship Suggester (위임)
    # ==========================================

    def suggest_relationships(self, doc_id: str, limit: int = 5) -> Result[Dict[str, Any]]:
        """특정 문서와 관계를 맺으면 유용할 다른 문서들을 AI가 추천"""
        return self._rel_suggester.suggest_relationships(doc_id, limit)


# Singleton Instance (기존 코드와 호환성 유지)
neo4j_service = Neo4jService()

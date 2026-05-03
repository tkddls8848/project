import logging
from typing import Optional
from neo4j import GraphDatabase, Driver, Session

from app.core.config import settings
from app.services.neo4j_indexes import create_neo4j_indexes
from app.services.cache_service import get_cache_service

logger = logging.getLogger(__name__)


class Neo4jConnectionManager:
    """Neo4j 연결 풀 관리 (Singleton)"""

    _instance = None
    _driver: Optional[Driver] = None
    _cache = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jConnectionManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Singleton 초기화 방지
        if self._driver is not None:
            return

        try:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
            )
            self._verify_connection()
            # Redis 캐시 서비스 초기화
            self._cache = get_cache_service(ttl=600)  # 기본 10분 TTL
            logger.info("Neo4j driver initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j driver: {e}")
            self._driver = None

    def _verify_connection(self):
        """연결 확인"""
        if self._driver:
            self._driver.verify_connectivity()

    def get_session(self) -> Session:
        """세션 획득"""
        if not self._driver:
            raise ConnectionError("Neo4j driver is not initialized.")
        return self._driver.session()

    def get_cache(self):
        """캐시 서비스 반환"""
        return self._cache

    def close(self):
        """드라이버 종료"""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j driver closed.")

    def initialize_indexes(self):
        """
        Neo4j 인덱스 및 제약조건 초기화

        Returns:
            생성된 인덱스 수
        """
        if not self._driver:
            logger.warning("Neo4j driver not initialized, skipping index creation")
            return 0

        try:
            count = create_neo4j_indexes(self._driver)
            logger.info(f"✅ Neo4j indexes initialized: {count} items")
            return count
        except Exception as e:
            logger.error(f"❌ Failed to initialize Neo4j indexes: {e}")
            return 0

    def invalidate_graph_cache(self, *doc_ids: str):
        """
        그래프 관련 캐시 무효화

        관계가 변경되면 관련 문서들의 캐시를 모두 삭제

        Args:
            *doc_ids: 무효화할 문서 ID들
        """
        if not self._cache:
            return

        # 문서별 캐시 삭제
        for doc_id in doc_ids:
            # explore_graph 캐시 (모든 depth)
            for depth in range(4):
                self._cache.delete(f"explore_graph:{doc_id}:{depth}")

            # suggest_relationships 캐시
            self._cache.delete_pattern(f"suggest_relationships:{doc_id}:*")

            # shortest_path 캐시 (source 또는 target으로 포함된 경로들)
            self._cache.delete_pattern(f"shortest_path:{doc_id}:*")
            self._cache.delete_pattern(f"shortest_path:*:{doc_id}")

        # 그래프 요약 캐시도 삭제 (전체 통계가 변경됨)
        self._cache.delete("graph_summary")

        logger.info(f"Invalidated graph cache for documents: {doc_ids}")


# Singleton Instance
connection_manager = Neo4jConnectionManager()

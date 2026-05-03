"""
Advanced Query Service - Backward Compatibility Facade

이 파일은 기존 코드와의 호환성을 위한 Facade입니다.
실제 구현은 services/query/ 모듈로 분해되었습니다.

분해된 구조:
- DocumentSearchService: 고급 문서 검색
- GraphAnalysisService: 그래프 패턴 분석
- StatisticsService: 통계 및 시계열 분석
"""

import logging
from typing import Dict, Any, List, Optional
from enum import Enum

from app.services.query import (
    FilterOperator,
    AggregationFunction,
    DocumentSearchService,
    GraphAnalysisService,
    StatisticsService,
)

logger = logging.getLogger(__name__)


# Re-export Enums for backward compatibility
class FilterOperator(str, Enum):
    """필터 연산자"""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    CONTAINS = "contains"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"


class AggregationFunction(str, Enum):
    """집계 함수"""
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COLLECT = "collect"


class AdvancedQueryService:
    """
    Advanced Query Service Facade (호환성 레이어)

    기존 코드와의 호환성을 위해 동일한 인터페이스를 제공합니다.
    내부적으로는 분해된 서비스들을 위임(delegation)합니다.
    """

    def __init__(self, neo4j_service):
        """
        Args:
            neo4j_service: Neo4jService 인스턴스
        """
        self.neo4j_service = neo4j_service
        # 분해된 서비스 초기화
        self._doc_search = DocumentSearchService(neo4j_service)
        self._graph_analysis = GraphAnalysisService(neo4j_service)
        self._statistics = StatisticsService(neo4j_service)
        logger.info("AdvancedQueryService initialized (Facade)")

    # ==========================================
    # Document Search (위임)
    # ==========================================

    def search_documents_advanced(
        self,
        filters: List[Dict[str, Any]],
        relationship_filters: Optional[List[Dict[str, Any]]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "DESC",
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """고급 다중 조건 문서 검색"""
        return self._doc_search.search_documents_advanced(
            filters, relationship_filters, sort_by, sort_order, limit, offset
        )

    # ==========================================
    # Graph Analysis (위임)
    # ==========================================

    def find_strong_connections(
        self,
        doc_id: str,
        min_strength: float = 0.5,
        relationship_types: Optional[List[str]] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """강한 관계만 필터링하여 연결된 문서 찾기"""
        return self._graph_analysis.find_strong_connections(
            doc_id, min_strength, relationship_types, limit
        )

    def find_triangular_relationships(
        self,
        doc_id: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """삼각 관계 패턴 찾기 (A-B-C-A 형태)"""
        return self._graph_analysis.find_triangular_relationships(doc_id, limit)

    def find_common_neighbors(
        self,
        doc_ids: List[str],
        min_common: int = 2,
        limit: int = 20
    ) -> Dict[str, Any]:
        """여러 문서의 공통 이웃 노드 찾기"""
        return self._graph_analysis.find_common_neighbors(doc_ids, min_common, limit)

    # ==========================================
    # Statistics (위임)
    # ==========================================

    def aggregate_by_relationship_type(
        self,
        group_by: str = "category",
        aggregation: AggregationFunction = AggregationFunction.COUNT
    ) -> Dict[str, Any]:
        """관계 타입별 집계 통계"""
        return self._statistics.aggregate_by_relationship_type(group_by, aggregation)

    def get_relationship_statistics(self) -> Dict[str, Any]:
        """전체 관계 통계 조회"""
        return self._statistics.get_relationship_statistics()

    def analyze_temporal_patterns(
        self,
        time_window_days: int = 30,
        group_by: str = "day"
    ) -> Dict[str, Any]:
        """시계열 패턴 분석 (관계 생성 시간 기반)"""
        return self._statistics.analyze_temporal_patterns(time_window_days, group_by)

    def find_all_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 4,
        limit: int = 10
    ) -> Dict[str, Any]:
        """두 문서 간 모든 경로 찾기"""
        return self._statistics.find_all_paths(source_id, target_id, max_depth, limit)

    def find_paths_through_node(
        self,
        through_id: str,
        through_type: str = "Document",
        max_depth: int = 3,
        limit: int = 20
    ) -> Dict[str, Any]:
        """특정 노드를 경유하는 경로 찾기"""
        return self._statistics.find_paths_through_node(through_id, through_type, max_depth, limit)

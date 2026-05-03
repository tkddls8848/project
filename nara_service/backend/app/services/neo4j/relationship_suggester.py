import logging
from typing import Any, Dict

from app.core.config import settings
from app.domain.common.result import Result, ErrorCode
from app.graph_schema import NodeLabel, RelationType, PropKey
from app.services.neo4j.connection_manager import Neo4jConnectionManager

logger = logging.getLogger(__name__)


class RelationshipSuggester:
    """AI 기반 관계 추천"""

    def __init__(self, connection_manager: Neo4jConnectionManager):
        self.conn = connection_manager
        self.cache = connection_manager.get_cache()

    def suggest_relationships(self, doc_id: str, limit: int = 5) -> Result[Dict[str, Any]]:
        """
        특정 문서와 관계를 맺으면 유용할 다른 문서들을 AI가 추천

        추천 알고리즘:
        1. 공통 키워드 개수
        2. 같은 카테고리 여부
        3. 같은 제공기관 여부
        4. 이미 직접 연결된 문서는 제외

        Args:
            doc_id: 기준 문서 ID
            limit: 최대 추천 개수 (기본값 5)

        Returns:
            {
                "doc_id": 기준 문서 ID,
                "suggestions": [
                    {
                        "target_doc": {"id": "...", "title": "...", "category": "..."},
                        "suggested_type": "보완" | "유사" | "인과",
                        "reason": "추천 이유",
                        "confidence": 0.0-1.0,
                        "common_keywords": ["키워드1", "키워드2"],
                        "common_category": "카테고리명" | None,
                        "common_provider": "제공기관명" | None
                    }
                ],
                "total": 추천 개수
            }
        """
        if not doc_id:
            return Result.fail("Document ID is required", ErrorCode.INVALID_PARAMS)

        # 캐시 조회
        cache_key = f"suggest_relationships:{doc_id}:{limit}"
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return Result.ok(cached_result)

        # 제외할 문서 카테고리 목록
        excluded_categories = settings.EXCLUDED_DOCUMENT_CATEGORIES

        # 1. 기준 문서의 키워드, 카테고리, 제공기관 조회
        base_query = f"""
        MATCH (d:{NodeLabel.DOCUMENT} {{api_id: $doc_id}})
        OPTIONAL MATCH (d)-[:{RelationType.HAS_KEYWORD}]->(k:{NodeLabel.KEYWORD})
        OPTIONAL MATCH (d)-[:{RelationType.BELONGS_TO}]->(c:{NodeLabel.CATEGORY})
        OPTIONAL MATCH (d)-[:{RelationType.PROVIDED_BY}]->(p:{NodeLabel.PROVIDER})
        RETURN
            d.title as doc_title,
            collect(DISTINCT k.name) as keywords,
            c.name as category,
            p.name as provider
        """

        # 2. 유사 문서 찾기 (공통 속성 기반), 제외할 카테고리는 필터링
        suggest_query = f"""
        MATCH (source:{NodeLabel.DOCUMENT} {{api_id: $doc_id}})
        MATCH (target:{NodeLabel.DOCUMENT})
        WHERE source <> target

        // 이미 직접 연결된 문서 제외
        AND NOT (source)-[:{RelationType.CUSTOM_RELATED_TO}]-(target)

        // 제외할 카테고리에 속한 문서 제외
        AND NOT EXISTS {{
          MATCH (target)-[:{RelationType.BELONGS_TO}]->(cat:{NodeLabel.CATEGORY})
          WHERE cat.{PropKey.NAME} IN $excluded_categories
        }}

        // 공통 키워드
        OPTIONAL MATCH (source)-[:{RelationType.HAS_KEYWORD}]->(k:{NodeLabel.KEYWORD})<-[:{RelationType.HAS_KEYWORD}]-(target)
        WITH source, target, collect(DISTINCT k.name) as common_keywords

        // 카테고리
        OPTIONAL MATCH (source)-[:{RelationType.BELONGS_TO}]->(c:{NodeLabel.CATEGORY})<-[:{RelationType.BELONGS_TO}]-(target)

        // 제공기관
        OPTIONAL MATCH (source)-[:{RelationType.PROVIDED_BY}]->(p:{NodeLabel.PROVIDER})<-[:{RelationType.PROVIDED_BY}]-(target)

        // 필터: 최소 1개 이상 공통점 있어야 함
        WHERE size(common_keywords) > 0 OR c IS NOT NULL OR p IS NOT NULL

        RETURN
            target.api_id as target_id,
            target.title as target_title,
            target.description as target_description,
            common_keywords,
            c.name as common_category,
            p.name as common_provider,
            size(common_keywords) as keyword_count,
            CASE WHEN c IS NOT NULL THEN 1 ELSE 0 END as category_match,
            CASE WHEN p IS NOT NULL THEN 1 ELSE 0 END as provider_match
        ORDER BY keyword_count DESC, category_match DESC, provider_match DESC
        LIMIT $limit
        """

        try:
            with self.conn.get_session() as session:
                # 기준 문서 정보 조회
                base_result = session.run(base_query, doc_id=doc_id)
                base_record = base_result.single()

                if not base_record:
                    logger.warning(f"Document {doc_id} not found for suggestions")
                    return Result.fail(f"Document {doc_id} not found", ErrorCode.NOT_FOUND)

                # 추천 문서 조회
                suggest_result = session.run(
                    suggest_query,
                    doc_id=doc_id,
                    limit=limit,
                    excluded_categories=excluded_categories
                )
                suggestions = []

                for record in suggest_result:
                    common_keywords = [k for k in record["common_keywords"] if k]
                    common_category = record["common_category"]
                    common_provider = record["common_provider"]

                    keyword_count = len(common_keywords)
                    category_match = 1 if common_category else 0
                    provider_match = 1 if common_provider else 0

                    # Confidence 계산 (0.0 - 1.0)
                    confidence = self._calculate_confidence(keyword_count, category_match, provider_match)

                    # 추천 타입 및 이유 결정
                    suggested_type, reason = self._determine_suggestion_type(
                        keyword_count,
                        category_match,
                        provider_match,
                        common_category,
                        common_provider,
                        common_keywords
                    )

                    suggestions.append({
                        "target_doc": {
                            "id": record["target_id"],
                            "title": record["target_title"],
                            "description": record["target_description"] or "",
                            "category": common_category or ""
                        },
                        "suggested_type": suggested_type,
                        "reason": reason,
                        "confidence": round(confidence, 2),
                        "common_keywords": common_keywords,
                        "common_category": common_category,
                        "common_provider": common_provider
                    })

                logger.info(f"Generated {len(suggestions)} relationship suggestions for {doc_id}")
                result_data = {
                    "doc_id": doc_id,
                    "suggestions": suggestions,
                    "total": len(suggestions)
                }

                # 캐시 저장 (5분 TTL - 추천은 비교적 자주 갱신)
                self.cache.set(cache_key, result_data, ttl=300)

                return Result.ok(result_data)

        except Exception as e:
            logger.error(f"Error suggesting relationships for {doc_id}: {e}")
            return Result.fail(f"Failed to suggest relationships: {str(e)}", ErrorCode.DB_QUERY_ERROR)

    def _calculate_confidence(
        self,
        keyword_count: int,
        category_match: int,
        provider_match: int
    ) -> float:
        """
        신뢰도 점수 계산

        공통 키워드: 개당 0.2점 (최대 0.6)
        카테고리 일치: 0.3점
        제공기관 일치: 0.1점
        """
        return min(
            (keyword_count * 0.2) + (category_match * 0.3) + (provider_match * 0.1),
            1.0
        )

    def _determine_suggestion_type(
        self,
        keyword_count: int,
        category_match: int,
        provider_match: int,
        common_category: str,
        common_provider: str,
        common_keywords: list
    ) -> tuple[str, str]:
        """
        추천 타입 및 이유 결정

        Returns:
            (suggested_type, reason)
        """
        reason_parts = []

        if category_match and keyword_count >= 2:
            suggested_type = "보완"
            reason_parts.append(f"같은 카테고리({common_category})")
        elif keyword_count >= 3:
            suggested_type = "유사"
            reason_parts.append(f"공통 키워드 {keyword_count}개")
        elif provider_match:
            suggested_type = "연관"
            reason_parts.append(f"같은 제공기관({common_provider})")
        else:
            suggested_type = "참고"

        # 이유 설명 생성
        if common_keywords:
            keywords_str = ", ".join(common_keywords[:3])
            reason_parts.append(f"키워드: {keywords_str}")

        reason = ", ".join(reason_parts) if reason_parts else "관련성 있음"

        return suggested_type, reason

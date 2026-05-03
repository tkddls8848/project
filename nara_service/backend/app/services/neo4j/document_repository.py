import logging
from typing import Any, Dict

from app.domain.common.result import Result, ErrorCode
from app.graph_schema import NodeLabel, RelationType, PropKey
from app.core.relationship_config import (
    generate_full_cypher_query,
    get_relationship_parameters
)
from app.services.neo4j.connection_manager import Neo4jConnectionManager

logger = logging.getLogger(__name__)


class DocumentRepository:
    """문서 CRUD 작업"""

    def __init__(self, connection_manager: Neo4jConnectionManager):
        self.conn = connection_manager

    def upsert_document(self, doc_data: Dict[str, Any]) -> Result[None]:
        """
        문서 및 관련 메타데이터를 그래프에 저장 (Merge)
        자동 관계는 app.core.relationship_config에서 정의됨
        """
        # 설정 기반으로 Cypher 쿼리 자동 생성
        query = generate_full_cypher_query()

        try:
            # 기본 문서 속성
            params = {
                'api_id': doc_data.get('api_id'),
                'title': doc_data.get('metadata', {}).get('title', ''),
                'description': doc_data.get('metadata', {}).get('description', ''),
                'url': doc_data.get('crawled_url', ''),
            }

            # 자동 관계 파라미터 추가
            relationship_params = get_relationship_parameters(doc_data)
            params.update(relationship_params)

            with self.conn.get_session() as session:
                session.run(query, **params)
                logger.debug(f"Upserted document: {doc_data.get('api_id')}")
                return Result.ok(None)
        except Exception as e:
            logger.error(f"Error upserting document {doc_data.get('api_id')}: {e}")
            return Result.fail(f"Failed to upsert document: {str(e)}", ErrorCode.DB_QUERY_ERROR)

    def get_related_context(self, api_ids: list[str]) -> Result[list[str]]:
        """
        주어진 문서 ID 목록과 연관된 추가 정보(Context)를 검색
        """
        if not api_ids:
            return Result.ok([])

        # Cypher: 주어진 문서들과 같은 키워드/카테고리를 공유하는 다른 문서들 찾기
        query = f"""
        MATCH (d:{NodeLabel.DOCUMENT})
        WHERE d.{PropKey.API_ID} IN $api_ids

        // 1. 같은 키워드를 가진 문서들
        OPTIONAL MATCH (d)-[:{RelationType.HAS_KEYWORD}]->(k:{NodeLabel.KEYWORD})<-[:{RelationType.HAS_KEYWORD}]-(related_k:{NodeLabel.DOCUMENT})

        // 2. 같은 카테고리의 문서들
        OPTIONAL MATCH (d)-[:{RelationType.BELONGS_TO}]->(c:{NodeLabel.CATEGORY})<-[:{RelationType.BELONGS_TO}]-(related_c:{NodeLabel.DOCUMENT})

        RETURN
            d.{PropKey.TITLE} as source_title,
            collect(DISTINCT k.{PropKey.NAME}) as shared_keywords,
            collect(DISTINCT related_k.{PropKey.TITLE}) as keyword_related_docs,
            c.{PropKey.NAME} as category,
            collect(DISTINCT related_c.{PropKey.TITLE}) as category_related_docs
        LIMIT 5
        """

        try:
            context_lines = []
            with self.conn.get_session() as session:
                result = session.run(query, api_ids=api_ids)
                for record in result:
                    source = record["source_title"]
                    keywords = record["shared_keywords"]
                    kw_docs = record["keyword_related_docs"][:3]  # 너무 많으면 자름
                    category = record["category"]
                    cat_docs = record["category_related_docs"][:3]

                    if kw_docs:
                        context_lines.append(
                            f"- '{source}' 문서는 '{', '.join(keywords)}' 키워드를 통해 "
                            f"'{', '.join(kw_docs)}' 등과 관련이 있습니다."
                        )
                    if cat_docs:
                        context_lines.append(
                            f"- '{source}' 문서는 '{category}' 분야에 속하며, "
                            f"유사한 문서로 '{', '.join(cat_docs)}' 등이 있습니다."
                        )

            return Result.ok(context_lines)
        except Exception as e:
            logger.error(f"Error fetching related context: {e}")
            return Result.fail(f"Failed to fetch related context: {str(e)}", ErrorCode.DB_QUERY_ERROR)

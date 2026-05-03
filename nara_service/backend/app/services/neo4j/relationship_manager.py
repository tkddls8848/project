import logging
from typing import Any, Dict
from neo4j.time import DateTime

from app.domain.common.result import Result, ErrorCode
from app.graph_schema import NodeLabel, RelationType, PropKey
from app.services.neo4j.connection_manager import Neo4jConnectionManager

logger = logging.getLogger(__name__)


class RelationshipManager:
    """사용자 정의 관계 CRUD"""

    def __init__(self, connection_manager: Neo4jConnectionManager):
        self.conn = connection_manager

    @staticmethod
    def _serialize_neo4j_types(obj: Any) -> Any:
        """Neo4j 타입을 JSON 직렬화 가능한 타입으로 변환"""
        if isinstance(obj, DateTime):
            return obj.iso_format()
        elif isinstance(obj, dict):
            return {key: RelationshipManager._serialize_neo4j_types(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [RelationshipManager._serialize_neo4j_types(item) for item in obj]
        else:
            return obj

    def create_custom_relationship(
        self,
        source_id: str,
        target_id: str,
        custom_type: str,
        description: str,
        strength: float = None
    ) -> Result[Dict[str, Any]]:
        """
        사용자 정의 관계 생성

        Args:
            source_id: 시작 문서 ID
            target_id: 대상 문서 ID
            custom_type: 관계 타입 (예: "비교", "참고", "연관")
            description: 관계 설명
            strength: 관계 강도 (0.0 - 1.0, 선택적)

        Returns:
            {
                "id": 관계 ID,
                "source_id": 시작 문서 ID,
                "source_title": 시작 문서 제목,
                "target_id": 대상 문서 ID,
                "target_title": 대상 문서 제목,
                "custom_type": 관계 타입,
                "description": 설명,
                "strength": 강도,
                "created_by": "user",
                "created_at": ISO 시간
            }
        """
        if not source_id or not target_id:
            return Result.fail("Source ID and target ID are required", ErrorCode.INVALID_PARAMS)

        if source_id == target_id:
            return Result.fail("Cannot create relationship to the same document", ErrorCode.INVALID_PARAMS)

        query = f"""
        MATCH (source:{NodeLabel.DOCUMENT} {{api_id: $source_id}})
        MATCH (target:{NodeLabel.DOCUMENT} {{api_id: $target_id}})
        CREATE (source)-[r:{RelationType.CUSTOM_RELATED_TO} {{
            custom_type: $custom_type,
            description: $description,
            strength: $strength,
            created_by: 'user',
            created_at: datetime()
        }}]->(target)
        RETURN elementId(r) as rel_id, r, source.title as source_title, target.title as target_title
        """

        try:
            with self.conn.get_session() as session:
                result = session.run(
                    query,
                    source_id=source_id,
                    target_id=target_id,
                    custom_type=custom_type,
                    description=description,
                    strength=strength
                )
                record = result.single()

                if not record:
                    return Result.fail("Documents not found", ErrorCode.NOT_FOUND)

                rel = record["r"]
                rel_data = self._serialize_neo4j_types(dict(rel))

                response = {
                    "id": record["rel_id"],
                    "source_id": source_id,
                    "source_title": record["source_title"],
                    "target_id": target_id,
                    "target_title": record["target_title"],
                    "custom_type": rel_data.get(PropKey.CUSTOM_TYPE),
                    "description": rel_data.get(PropKey.REL_DESCRIPTION),
                    "strength": rel_data.get(PropKey.STRENGTH),
                    "created_by": rel_data.get(PropKey.CREATED_BY),
                    "created_at": rel_data.get(PropKey.CREATED_AT)
                }

                logger.info(f"Created custom relationship: {source_id} -> {target_id} ({custom_type})")

                # 캐시 무효화
                self.conn.invalidate_graph_cache(source_id, target_id)

                return Result.ok(response)

        except Exception as e:
            logger.error(f"Error creating custom relationship: {e}")
            return Result.fail(f"Failed to create relationship: {str(e)}", ErrorCode.DB_QUERY_ERROR)

    def get_custom_relationship(self, rel_id: str) -> Result[Dict[str, Any]]:
        """
        사용자 정의 관계 조회

        Args:
            rel_id: 관계 ID (elementId)

        Returns:
            관계 정보
        """
        if not rel_id:
            return Result.fail("Relationship ID is required", ErrorCode.INVALID_PARAMS)

        query = f"""
        MATCH (source:{NodeLabel.DOCUMENT})-[r:{RelationType.CUSTOM_RELATED_TO}]->(target:{NodeLabel.DOCUMENT})
        WHERE elementId(r) = $rel_id
        RETURN elementId(r) as rel_id, r,
               source.api_id as source_id, source.title as source_title,
               target.api_id as target_id, target.title as target_title
        """

        try:
            with self.conn.get_session() as session:
                result = session.run(query, rel_id=rel_id)
                record = result.single()

                if not record:
                    return Result.fail(f"Relationship {rel_id} not found", ErrorCode.NOT_FOUND)

                rel = record["r"]
                rel_data = self._serialize_neo4j_types(dict(rel))

                result_data = {
                    "id": record["rel_id"],
                    "source_id": record["source_id"],
                    "source_title": record["source_title"],
                    "target_id": record["target_id"],
                    "target_title": record["target_title"],
                    "custom_type": rel_data.get(PropKey.CUSTOM_TYPE),
                    "description": rel_data.get(PropKey.REL_DESCRIPTION),
                    "strength": rel_data.get(PropKey.STRENGTH),
                    "created_by": rel_data.get(PropKey.CREATED_BY),
                    "created_at": rel_data.get(PropKey.CREATED_AT)
                }

                return Result.ok(result_data)

        except Exception as e:
            logger.error(f"Error getting custom relationship {rel_id}: {e}")
            return Result.fail(f"Failed to get relationship: {str(e)}", ErrorCode.DB_QUERY_ERROR)

    def update_custom_relationship(
        self,
        rel_id: str,
        custom_type: str = None,
        description: str = None,
        strength: float = None
    ) -> Result[Dict[str, Any]]:
        """
        사용자 정의 관계 수정

        Args:
            rel_id: 관계 ID
            custom_type: 새 관계 타입 (선택적)
            description: 새 설명 (선택적)
            strength: 새 강도 (선택적)

        Returns:
            수정된 관계 정보
        """
        if not rel_id:
            return Result.fail("Relationship ID is required", ErrorCode.INVALID_PARAMS)

        # 업데이트할 속성 구성
        set_clauses = []
        params = {"rel_id": rel_id}

        if custom_type is not None:
            set_clauses.append("r.custom_type = $custom_type")
            params["custom_type"] = custom_type

        if description is not None:
            set_clauses.append("r.description = $description")
            params["description"] = description

        if strength is not None:
            set_clauses.append("r.strength = $strength")
            params["strength"] = strength

        if not set_clauses:
            return Result.fail("No update parameters provided", ErrorCode.INVALID_PARAMS)

        set_clause = ", ".join(set_clauses)

        query = f"""
        MATCH (source:{NodeLabel.DOCUMENT})-[r:{RelationType.CUSTOM_RELATED_TO}]->(target:{NodeLabel.DOCUMENT})
        WHERE elementId(r) = $rel_id
        SET {set_clause}
        RETURN elementId(r) as rel_id, r,
               source.api_id as source_id, source.title as source_title,
               target.api_id as target_id, target.title as target_title
        """

        try:
            with self.conn.get_session() as session:
                result = session.run(query, **params)
                record = result.single()

                if not record:
                    return Result.fail(f"Relationship {rel_id} not found", ErrorCode.NOT_FOUND)

                rel = record["r"]
                rel_data = self._serialize_neo4j_types(dict(rel))

                logger.info(f"Updated custom relationship {rel_id}")

                updated_data = {
                    "id": record["rel_id"],
                    "source_id": record["source_id"],
                    "source_title": record["source_title"],
                    "target_id": record["target_id"],
                    "target_title": record["target_title"],
                    "custom_type": rel_data.get(PropKey.CUSTOM_TYPE),
                    "description": rel_data.get(PropKey.REL_DESCRIPTION),
                    "strength": rel_data.get(PropKey.STRENGTH),
                    "created_by": rel_data.get(PropKey.CREATED_BY),
                    "created_at": rel_data.get(PropKey.CREATED_AT)
                }

                # 캐시 무효화
                self.conn.invalidate_graph_cache(record["source_id"], record["target_id"])

                return Result.ok(updated_data)

        except Exception as e:
            logger.error(f"Error updating custom relationship {rel_id}: {e}")
            return Result.fail(f"Failed to update relationship: {str(e)}", ErrorCode.DB_QUERY_ERROR)

    def delete_custom_relationship(self, rel_id: str) -> Result[bool]:
        """
        사용자 정의 관계 삭제

        Args:
            rel_id: 관계 ID

        Returns:
            삭제 성공 여부
        """
        if not rel_id:
            return Result.fail("Relationship ID is required", ErrorCode.INVALID_PARAMS)

        # 캐시 무효화를 위해 삭제 전에 관계 정보 조회
        get_query = f"""
        MATCH (source:{NodeLabel.DOCUMENT})-[r:{RelationType.CUSTOM_RELATED_TO}]->(target:{NodeLabel.DOCUMENT})
        WHERE elementId(r) = $rel_id
        RETURN source.api_id as source_id, target.api_id as target_id
        """

        query = f"""
        MATCH ()-[r:{RelationType.CUSTOM_RELATED_TO}]->()
        WHERE elementId(r) = $rel_id
        DELETE r
        RETURN count(r) as deleted_count
        """

        try:
            with self.conn.get_session() as session:
                # 관계 정보 조회
                get_result = session.run(get_query, rel_id=rel_id)
                get_record = get_result.single()

                # 삭제
                result = session.run(query, rel_id=rel_id)
                record = result.single()

                deleted = record["deleted_count"] > 0
                if deleted:
                    logger.info(f"Deleted custom relationship {rel_id}")

                    # 캐시 무효화
                    if get_record:
                        self.conn.invalidate_graph_cache(get_record["source_id"], get_record["target_id"])

                    return Result.ok(True)
                else:
                    logger.warning(f"Relationship {rel_id} not found for deletion")
                    return Result.fail(f"Relationship {rel_id} not found", ErrorCode.NOT_FOUND)

        except Exception as e:
            logger.error(f"Error deleting custom relationship {rel_id}: {e}")
            return Result.fail(f"Failed to delete relationship: {str(e)}", ErrorCode.DB_QUERY_ERROR)

    def list_user_relationships(self, limit: int = 100) -> Result[Dict[str, Any]]:
        """
        사용자 정의 관계 목록 조회

        Args:
            limit: 최대 조회 개수

        Returns:
            {
                "relationships": [관계 목록],
                "total": 총 개수
            }
        """
        query = f"""
        MATCH (source:{NodeLabel.DOCUMENT})-[r:{RelationType.CUSTOM_RELATED_TO}]->(target:{NodeLabel.DOCUMENT})
        WHERE r.created_by = 'user'
        RETURN elementId(r) as rel_id, r,
               source.api_id as source_id, source.title as source_title,
               target.api_id as target_id, target.title as target_title
        ORDER BY r.created_at DESC
        LIMIT $limit
        """

        count_query = f"""
        MATCH ()-[r:{RelationType.CUSTOM_RELATED_TO}]->()
        WHERE r.created_by = 'user'
        RETURN count(r) as total
        """

        try:
            with self.conn.get_session() as session:
                # 관계 목록 조회
                result = session.run(query, limit=limit)
                relationships = []

                for record in result:
                    rel = record["r"]
                    rel_data = self._serialize_neo4j_types(dict(rel))

                    relationships.append({
                        "id": record["rel_id"],
                        "source_id": record["source_id"],
                        "source_title": record["source_title"],
                        "target_id": record["target_id"],
                        "target_title": record["target_title"],
                        "custom_type": rel_data.get(PropKey.CUSTOM_TYPE),
                        "description": rel_data.get(PropKey.REL_DESCRIPTION),
                        "strength": rel_data.get(PropKey.STRENGTH),
                        "created_by": rel_data.get(PropKey.CREATED_BY),
                        "created_at": rel_data.get(PropKey.CREATED_AT)
                    })

                # 총 개수 조회
                count_result = session.run(count_query)
                total = count_result.single()["total"]

                logger.info(f"Retrieved {len(relationships)} user relationships (total: {total})")
                result_data = {
                    "relationships": relationships,
                    "total": total
                }

                return Result.ok(result_data)

        except Exception as e:
            logger.error(f"Error listing user relationships: {e}")
            return Result.fail(f"Failed to list relationships: {str(e)}", ErrorCode.DB_QUERY_ERROR)

import logging
from typing import Any, Dict
from neo4j.time import DateTime

from app.domain.common.result import Result, ErrorCode
from app.graph_schema import NodeLabel, RelationType, PropKey
from app.services.neo4j.connection_manager import Neo4jConnectionManager

logger = logging.getLogger(__name__)


class PathFinder:
    """문서 간 경로 탐색"""

    def __init__(self, connection_manager: Neo4jConnectionManager):
        self.conn = connection_manager
        self.cache = connection_manager.get_cache()

    @staticmethod
    def _serialize_neo4j_types(obj: Any) -> Any:
        """Neo4j 타입을 JSON 직렬화 가능한 타입으로 변환"""
        if isinstance(obj, DateTime):
            return obj.iso_format()
        elif isinstance(obj, dict):
            return {key: PathFinder._serialize_neo4j_types(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [PathFinder._serialize_neo4j_types(item) for item in obj]
        else:
            return obj

    def find_shortest_path(self, source_id: str, target_id: str) -> Result[Dict[str, Any]]:
        """
        두 문서 간 최단 경로 탐색

        Args:
            source_id: 시작 문서 ID
            target_id: 목표 문서 ID

        Returns:
            Result[Dict]: 성공 시 경로 데이터, 실패 시 에러 메시지
                {
                    "path": [노드 리스트],
                    "relationships": [엣지 리스트],
                    "insights": "설명 텍스트"
                }
        """
        if not source_id or not target_id:
            return Result.fail("Source ID and target ID are required", ErrorCode.INVALID_PARAMS)

        # 캐시 조회
        cache_key = f"shortest_path:{source_id}:{target_id}"
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return Result.ok(cached_result)

        query = f"""
        MATCH (source:{NodeLabel.DOCUMENT} {{api_id: $source_id}}),
              (target:{NodeLabel.DOCUMENT} {{api_id: $target_id}}),
              path = shortestPath((source)-[*..6]-(target))
        WHERE source <> target
        RETURN path
        """

        try:
            with self.conn.get_session() as session:
                result = session.run(query, source_id=source_id, target_id=target_id)
                record = result.single()

                if not record:
                    result_data = {
                        "path": [],
                        "relationships": [],
                        "insights": "두 문서 간 연결된 경로가 없습니다."
                    }
                    self.cache.set(cache_key, result_data, ttl=600)
                    return Result.ok(result_data)

                path = record["path"]
                nodes_data = []
                edges_data = []
                keywords = []

                # 노드 처리
                for node in path.nodes:
                    labels = list(node.labels)
                    node_type = labels[0] if labels else "Unknown"

                    if node_type == "Document":
                        node_id = node.get(PropKey.API_ID, node.id)
                        label = node.get(PropKey.TITLE, "Untitled")
                    else:
                        node_id = f"{node_type.lower()}_{node.get(PropKey.NAME, node.id)}"
                        label = node.get(PropKey.NAME, "Unknown")

                        # 키워드 수집 (insights 생성용)
                        if node_type == "Keyword":
                            keywords.append(label)

                    nodes_data.append({
                        "id": str(node_id),
                        "label": label,
                        "type": node_type,
                        "properties": self._serialize_neo4j_types(dict(node))
                    })

                # 관계 처리
                label_map = {
                    RelationType.HAS_KEYWORD: "키워드",
                    RelationType.PROVIDED_BY: "제공기관",
                    RelationType.BELONGS_TO: "카테고리"
                }

                for rel in path.relationships:
                    start_node = rel.start_node
                    end_node = rel.end_node
                    rel_type = rel.type

                    start_labels = list(start_node.labels)
                    end_labels = list(end_node.labels)
                    start_type = start_labels[0] if start_labels else "Unknown"
                    end_type = end_labels[0] if end_labels else "Unknown"

                    if start_type == "Document":
                        source_node_id = start_node.get(PropKey.API_ID, start_node.id)
                    else:
                        source_node_id = f"{start_type.lower()}_{start_node.get(PropKey.NAME, start_node.id)}"

                    if end_type == "Document":
                        target_node_id = end_node.get(PropKey.API_ID, end_node.id)
                    else:
                        target_node_id = f"{end_type.lower()}_{end_node.get(PropKey.NAME, end_node.id)}"

                    label = label_map.get(rel_type, rel_type)

                    edges_data.append({
                        "id": f"{source_node_id}_{rel_type}_{target_node_id}",
                        "source": str(source_node_id),
                        "target": str(target_node_id),
                        "type": rel_type,
                        "label": label
                    })

                # Insights 생성
                path_length = len(path.relationships)
                insights = f"두 문서는 {path_length}단계로 연결되어 있습니다."

                if keywords:
                    keywords_str = "', '".join(keywords[:3])  # 최대 3개만
                    insights += f" 주요 연결 키워드: '{keywords_str}'"

                logger.info(f"Found path between {source_id} and {target_id}: {path_length} steps")
                result_data = {
                    "path": nodes_data,
                    "relationships": edges_data,
                    "insights": insights
                }

                # 캐시 저장 (10분 TTL)
                self.cache.set(cache_key, result_data, ttl=600)

                return Result.ok(result_data)

        except Exception as e:
            logger.error(f"Error finding path between {source_id} and {target_id}: {e}")
            return Result.fail(f"Failed to find path: {str(e)}", ErrorCode.DB_QUERY_ERROR)

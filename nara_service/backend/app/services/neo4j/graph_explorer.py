import logging
from typing import Any, Dict
from neo4j.time import DateTime

from app.core.config import settings
from app.domain.common.result import Result, ErrorCode
from app.graph_schema import NodeLabel, RelationType, PropKey
from app.services.neo4j.connection_manager import Neo4jConnectionManager

logger = logging.getLogger(__name__)


class GraphExplorer:
    """그래프 탐색 서비스"""

    def __init__(self, connection_manager: Neo4jConnectionManager):
        self.conn = connection_manager
        self.cache = connection_manager.get_cache()

    @staticmethod
    def _serialize_neo4j_types(obj: Any) -> Any:
        """Neo4j 타입을 JSON 직렬화 가능한 타입으로 변환"""
        if isinstance(obj, DateTime):
            return obj.iso_format()
        elif isinstance(obj, dict):
            return {key: GraphExplorer._serialize_neo4j_types(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [GraphExplorer._serialize_neo4j_types(item) for item in obj]
        else:
            return obj

    def _load_single_document(self, doc_id: str) -> Dict[str, Any]:
        """depth=0 처리: 문서 노드만 반환"""
        try:
            with self.conn.get_session() as session:
                query = f"""
                MATCH (d:{NodeLabel.DOCUMENT} {{api_id: $doc_id}})
                RETURN d
                """
                result = session.run(query, doc_id=doc_id)
                record = result.single()

                if not record:
                    logger.warning(f"Document {doc_id} not found")
                    return {"nodes": [], "edges": [], "center_node": doc_id}

                doc_node = record["d"]
                node = {
                    "id": str(doc_node.get(PropKey.API_ID, doc_node.id)),
                    "label": doc_node.get(PropKey.TITLE, "Untitled"),
                    "type": "Document",
                    "properties": self._serialize_neo4j_types(dict(doc_node))
                }

                logger.info(f"Loaded single document node: {doc_id}")
                return {
                    "nodes": [node],
                    "edges": [],
                    "center_node": doc_id
                }
        except Exception as e:
            logger.error(f"Error loading single document {doc_id}: {e}")
            return {"nodes": [], "edges": [], "center_node": doc_id}

    def _build_node(self, node, node_type: str) -> Dict[str, Any]:
        """노드 객체를 딕셔너리로 변환"""
        if node_type == "Document":
            node_id = node.get(PropKey.API_ID, node.id)
            label = node.get(PropKey.TITLE, "Untitled")
        else:
            node_id = f"{node_type.lower()}_{node.get(PropKey.NAME, node.id)}"
            label = node.get(PropKey.NAME, "Unknown")

        return {
            "id": str(node_id),
            "label": label,
            "type": node_type,
            "properties": self._serialize_neo4j_types(dict(node))
        }

    def _build_edge(self, rel, source_id: str, target_id: str, rel_type: str) -> Dict[str, Any]:
        """관계 객체를 딕셔너리로 변환"""
        label_map = {
            RelationType.HAS_KEYWORD: "키워드",
            RelationType.PROVIDED_BY: "제공기관",
            RelationType.BELONGS_TO: "카테고리",
            RelationType.CUSTOM_RELATED_TO: "사용자 정의"
        }

        # CUSTOM_RELATED_TO는 custom_type 속성 사용
        if rel_type == RelationType.CUSTOM_RELATED_TO:
            label = rel.get(PropKey.CUSTOM_TYPE, "사용자 정의")
        else:
            label = label_map.get(rel_type, rel_type)

        return {
            "id": f"{source_id}_{rel_type}_{target_id}",
            "source": str(source_id),
            "target": str(target_id),
            "type": rel_type,
            "label": label
        }

    def _extract_node_id(self, node, node_type: str) -> str:
        """노드에서 ID 추출"""
        if node_type == "Document":
            return node.get(PropKey.API_ID, node.id)
        else:
            return f"{node_type.lower()}_{node.get(PropKey.NAME, node.id)}"

    def explore_graph(self, doc_id: str, depth: int = 2) -> Result[Dict[str, Any]]:
        """
        특정 문서 주변의 그래프 데이터를 depth 단계까지 탐색

        Args:
            doc_id: 탐색 시작 문서 ID
            depth: 탐색 깊이 (0-3, 기본값 2)
                   - 0: 문서 노드만 반환 (주변 노드 없음)
                   - 1-3: depth 단계까지 주변 노드 탐색

        Returns:
            Result[Dict]: 성공 시 그래프 데이터, 실패 시 에러 메시지
                {
                    "nodes": [{"id": "...", "label": "...", "type": "...", "properties": {...}}],
                    "edges": [{"id": "...", "source": "...", "target": "...", "type": "...", "label": "..."}],
                    "center_node": "doc_id"
                }
        """
        if not doc_id:
            return Result.fail("Document ID is required", ErrorCode.INVALID_PARAMS)

        # 캐시 조회
        cache_key = f"explore_graph:{doc_id}:{depth}"
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return Result.ok(cached_result)

        # depth=0: 문서 노드만 반환
        if depth == 0:
            result = self._load_single_document(doc_id)
            if not result["nodes"]:
                return Result.fail(f"Document {doc_id} not found", ErrorCode.NOT_FOUND)
            self.cache.set(cache_key, result, ttl=600)
            return Result.ok(result)

        # 깊이 제한 (성능 보호) - depth 1-3
        depth = min(max(depth, 1), 3)

        # 제외할 문서 카테고리 목록
        excluded_categories = settings.EXCLUDED_DOCUMENT_CATEGORIES

        # Cypher 쿼리: 모든 관계 타입 포함, 제외할 카테고리의 Document는 필터링
        query = f"""
        MATCH path = (d:{NodeLabel.DOCUMENT} {{api_id: $doc_id}})-[*1..{depth}]-(related)
        WHERE d <> related
          AND (
            NOT related:{NodeLabel.DOCUMENT}
            OR NOT EXISTS {{
              MATCH (related)-[:{RelationType.BELONGS_TO}]->(cat:{NodeLabel.CATEGORY})
              WHERE cat.{PropKey.NAME} IN $excluded_categories
            }}
          )
        WITH collect(DISTINCT related) as nodes, collect(path) as paths
        UNWIND paths as p
        UNWIND relationships(p) as rel
        RETURN nodes, collect(DISTINCT rel) as rels
        LIMIT 500
        """

        try:
            nodes = []
            edges = []
            seen_nodes = set()
            seen_edges = set()

            with self.conn.get_session() as session:
                result = session.run(query, doc_id=doc_id, excluded_categories=excluded_categories)
                record = result.single()

                if not record:
                    logger.warning(f"No graph data found for document: {doc_id}")
                    return Result.fail(f"Document {doc_id} not found", ErrorCode.NOT_FOUND)

                # 중심 문서 노드 추가
                center_node = self._load_center_node(session, doc_id, seen_nodes, nodes)

                # 관련 노드 처리
                for node in record["nodes"]:
                    labels = list(node.labels)
                    node_type = labels[0] if labels else "Unknown"
                    node_id = self._extract_node_id(node, node_type)

                    if node_id not in seen_nodes:
                        nodes.append(self._build_node(node, node_type))
                        seen_nodes.add(node_id)

                # 관계 처리
                self._process_relationships(record["rels"], seen_edges, edges)

                # Document 간 직접 연결(CUSTOM_RELATED_TO) 추가
                self._add_doc_to_doc_relationships(session, doc_id, seen_nodes, seen_edges, nodes, edges)

            logger.info(f"Explored graph for {doc_id}: {len(nodes)} nodes, {len(edges)} edges")
            result_data = {
                "nodes": nodes,
                "edges": edges,
                "center_node": doc_id
            }
            serialized_result = self._serialize_neo4j_types(result_data)

            # 캐시 저장 (10분 TTL)
            self.cache.set(cache_key, serialized_result, ttl=600)

            return Result.ok(serialized_result)

        except Exception as e:
            logger.error(f"Error exploring graph for {doc_id}: {e}")
            return Result.fail(f"Failed to explore graph: {str(e)}", ErrorCode.DB_QUERY_ERROR)

    def _load_center_node(self, session, doc_id: str, seen_nodes: set, nodes: list):
        """중심 문서 노드 로드"""
        center_doc_query = f"""
        MATCH (d:{NodeLabel.DOCUMENT} {{api_id: $doc_id}})
        RETURN d
        """
        center_result = session.run(center_doc_query, doc_id=doc_id)
        center_record = center_result.single()
        if center_record:
            center_node = center_record["d"]
            node_id = center_node.get(PropKey.API_ID, center_node.id)
            if node_id not in seen_nodes:
                nodes.append({
                    "id": str(node_id),
                    "label": center_node.get(PropKey.TITLE, "Untitled"),
                    "type": "Document",
                    "properties": self._serialize_neo4j_types(dict(center_node))
                })
                seen_nodes.add(node_id)

    def _process_relationships(self, rels, seen_edges: set, edges: list):
        """관계 목록 처리"""
        for rel in rels:
            start_node = rel.start_node
            end_node = rel.end_node
            rel_type = rel.type

            # 노드 ID 추출
            start_labels = list(start_node.labels)
            end_labels = list(end_node.labels)
            start_type = start_labels[0] if start_labels else "Unknown"
            end_type = end_labels[0] if end_labels else "Unknown"

            source_id = self._extract_node_id(start_node, start_type)
            target_id = self._extract_node_id(end_node, end_type)
            edge_id = f"{source_id}_{rel_type}_{target_id}"

            if edge_id not in seen_edges:
                edges.append(self._build_edge(rel, source_id, target_id, rel_type))
                seen_edges.add(edge_id)

    def _add_doc_to_doc_relationships(self, session, doc_id: str, seen_nodes: set, seen_edges: set, nodes: list, edges: list):
        """Document 간 직접 연결 추가"""
        doc_to_doc_query = f"""
        MATCH (d:{NodeLabel.DOCUMENT} {{api_id: $doc_id}})-[r:{RelationType.CUSTOM_RELATED_TO}]-(other:{NodeLabel.DOCUMENT})
        RETURN other, r
        """
        logger.info(f"Running Document-to-Document query for {doc_id}")
        doc_result = session.run(doc_to_doc_query, doc_id=doc_id)
        doc_records = list(doc_result)
        logger.info(f"Found {len(doc_records)} Document-to-Document relationships for {doc_id}")

        for doc_record in doc_records:
            other_doc = doc_record["other"]
            custom_rel = doc_record["r"]

            # 다른 문서 노드 추가
            other_id = other_doc.get(PropKey.API_ID, other_doc.id)
            if other_id not in seen_nodes:
                nodes.append({
                    "id": str(other_id),
                    "label": other_doc.get(PropKey.TITLE, "Untitled"),
                    "type": "Document",
                    "properties": self._serialize_neo4j_types(dict(other_doc))
                })
                seen_nodes.add(other_id)

            # Custom 관계 추가
            start_node = custom_rel.start_node
            end_node = custom_rel.end_node
            source_id = start_node.get(PropKey.API_ID, start_node.id)
            target_id = end_node.get(PropKey.API_ID, end_node.id)
            edge_id = f"{source_id}_{RelationType.CUSTOM_RELATED_TO}_{target_id}"

            if edge_id not in seen_edges:
                custom_type = custom_rel.get(PropKey.CUSTOM_TYPE, "사용자 정의")
                edges.append({
                    "id": edge_id,
                    "source": str(source_id),
                    "target": str(target_id),
                    "type": RelationType.CUSTOM_RELATED_TO,
                    "label": custom_type
                })
                seen_edges.add(edge_id)

    def get_graph_summary(self) -> Result[Dict[str, Any]]:
        """
        전체 그래프 통계 및 상위 엔티티 조회

        Returns:
            Result[Dict]: 성공 시 그래프 통계, 실패 시 에러 메시지
                {
                    "stats": {"total_documents": int, "total_keywords": int, ...},
                    "top_keywords": [{"name": str, "doc_count": int}, ...],
                    "top_providers": [{"name": str, "doc_count": int}, ...],
                    "top_categories": [{"name": str, "doc_count": int}, ...]
                }
        """
        # 캐시 조회 (그래프 요약은 자주 변경되지 않으므로 긴 TTL)
        cache_key = "graph_summary"
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return Result.ok(cached_result)

        try:
            with self.conn.get_session() as session:
                # 1. 노드 카운트
                doc_count = session.run(f"MATCH (d:{NodeLabel.DOCUMENT}) RETURN count(d) as cnt").single()
                keyword_count = session.run(f"MATCH (k:{NodeLabel.KEYWORD}) RETURN count(k) as cnt").single()
                category_count = session.run(f"MATCH (c:{NodeLabel.CATEGORY}) RETURN count(c) as cnt").single()
                provider_count = session.run(f"MATCH (p:{NodeLabel.PROVIDER}) RETURN count(p) as cnt").single()

                stats = {
                    "total_documents": doc_count["cnt"] if doc_count else 0,
                    "total_keywords": keyword_count["cnt"] if keyword_count else 0,
                    "total_categories": category_count["cnt"] if category_count else 0,
                    "total_providers": provider_count["cnt"] if provider_count else 0
                }

                # 2. 상위 키워드
                keyword_query = f"""
                MATCH (k:{NodeLabel.KEYWORD})<-[r:{RelationType.HAS_KEYWORD}]-(d:{NodeLabel.DOCUMENT})
                RETURN k.{PropKey.NAME} as name, count(r) as doc_count
                ORDER BY doc_count DESC
                LIMIT 10
                """
                keyword_result = session.run(keyword_query)
                top_keywords = [{"name": record["name"], "doc_count": record["doc_count"]}
                               for record in keyword_result]

                # 3. 상위 제공기관
                provider_query = f"""
                MATCH (p:{NodeLabel.PROVIDER})<-[r:{RelationType.PROVIDED_BY}]-(d:{NodeLabel.DOCUMENT})
                RETURN p.{PropKey.NAME} as name, count(r) as doc_count
                ORDER BY doc_count DESC
                LIMIT 10
                """
                provider_result = session.run(provider_query)
                top_providers = [{"name": record["name"], "doc_count": record["doc_count"]}
                                for record in provider_result]

                # 4. 상위 카테고리
                category_query = f"""
                MATCH (c:{NodeLabel.CATEGORY})<-[r:{RelationType.BELONGS_TO}]-(d:{NodeLabel.DOCUMENT})
                RETURN c.{PropKey.NAME} as name, count(r) as doc_count
                ORDER BY doc_count DESC
                LIMIT 10
                """
                category_result = session.run(category_query)
                top_categories = [{"name": record["name"], "doc_count": record["doc_count"]}
                                 for record in category_result]

            logger.info(f"Graph summary retrieved: {stats}")
            result_data = {
                "stats": stats,
                "top_keywords": top_keywords,
                "top_providers": top_providers,
                "top_categories": top_categories
            }

            # 캐시 저장 (30분 TTL - 그래프 요약은 자주 변경되지 않음)
            self.cache.set(cache_key, result_data, ttl=1800)

            return Result.ok(result_data)

        except Exception as e:
            logger.error(f"Error getting graph summary: {e}")
            return Result.fail(f"Failed to get graph summary: {str(e)}", ErrorCode.DB_QUERY_ERROR)

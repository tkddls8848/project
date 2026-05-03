"""Advanced Graph Insights Engine Service

이 서비스는 Neo4j 그래프 데이터를 분석하여 고급 인사이트를 제공합니다:
- 관계 체인 발견 (Relationship Chains)
- 숨겨진 연결 발견 (Hidden Connections)
- 커뮤니티 탐지 (Community Detection)
- 중심성 분석 (Centrality Analysis)
- 보완 데이터 추천 (Complementary Data Recommendations)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import networkx as nx
from community import community_louvain
from collections import Counter

from app.graph_schema import NodeLabel, RelationType

logger = logging.getLogger(__name__)


class InsightEngine:
    """고급 그래프 분석 및 인사이트 엔진"""

    def __init__(self, neo4j_service):
        """
        Args:
            neo4j_service: Neo4jService 인스턴스
        """
        self.neo4j_service = neo4j_service
        logger.info("InsightEngine initialized")

    # ==========================================
    # 1. Relationship Chain Discovery
    # ==========================================

    def discover_chains(self, doc_id: str, min_length: int = 2, max_length: int = 4, limit: int = 10) -> Dict[str, Any]:
        """
        특정 문서에서 시작하는 관계 체인을 발견합니다.

        Args:
            doc_id: 기준 문서 ID
            min_length: 최소 체인 길이 (관계 개수)
            max_length: 최대 체인 길이
            limit: 최대 반환 체인 개수

        Returns:
            발견된 관계 체인 목록
        """
        logger.info(f"Discovering relationship chains for document: {doc_id}")

        # Cypher 쿼리: 사용자 정의 관계로 연결된 체인 발견
        query = f"""
        MATCH path = (start:{NodeLabel.DOCUMENT} {{api_id: $doc_id}})-[r:{RelationType.CUSTOM_RELATED_TO}*{min_length}..{max_length}]->(end:{NodeLabel.DOCUMENT})
        WHERE start <> end
        WITH path, relationships(path) as rels, nodes(path) as nodeList
        RETURN
            [n in nodeList | {{
                id: n.api_id,
                title: n.title,
                category: n.category,
                description: n.description
            }}] as chain_nodes,
            [rel in rels | {{
                type: rel.custom_type,
                description: rel.description,
                strength: rel.strength
            }}] as chain_relationships,
            length(path) as chain_length
        ORDER BY chain_length DESC
        LIMIT $limit
        """

        try:
            with self.neo4j_service.get_session() as session:
                result = session.run(query, doc_id=doc_id, limit=limit)
                records = list(result)

            chains = []
            for idx, record in enumerate(records):
                try:
                    chain_nodes = record["chain_nodes"]
                    chain_relationships = record["chain_relationships"]
                    chain_length = record["chain_length"]

                    # 빈 체인 건너뛰기
                    if not chain_nodes or not chain_relationships:
                        continue

                    # 체인 타입 분석
                    chain_types = [rel.get("type", "알 수 없음") for rel in chain_relationships]
                    type_counter = Counter(chain_types)
                    dominant_type = type_counter.most_common(1)[0][0] if type_counter else "혼합"

                    # 인사이트 생성
                    insight = self._generate_chain_insight(chain_nodes, chain_relationships, dominant_type)

                    chains.append({
                        "chain_id": f"chain_{idx}",
                        "nodes": chain_nodes,
                        "relationships": chain_relationships,
                        "length": chain_length,
                        "chain_types": chain_types,
                        "insight": insight
                    })
                except Exception as e:
                    logger.warning(f"Skipping invalid chain record: {e}")
                    continue

            return {
                "doc_id": doc_id,
                "chains": chains,
                "total": len(chains)
            }

        except Exception as e:
            logger.error(f"Error discovering chains for {doc_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def _generate_chain_insight(self, nodes: List[dict], relationships: List[dict], dominant_type: str) -> str:
        """관계 체인에 대한 인사이트 생성"""
        # 안전성 검사
        if not nodes or len(nodes) < 2:
            return "관계 체인 정보가 부족합니다."

        start_title = nodes[0].get("title", "알 수 없는 문서")
        end_title = nodes[-1].get("title", "알 수 없는 문서")
        chain_length = len(relationships)

        # 카테고리 분석
        categories = [n["category"] for n in nodes if n.get("category")]
        category_counter = Counter(categories)

        if category_counter:
            most_common_category = category_counter.most_common(1)[0][0]
            insight = f"'{start_title}'에서 '{end_title}'까지 {chain_length}단계의 '{dominant_type}' 관계 체인이 발견되었습니다. "
            insight += f"주로 '{most_common_category}' 카테고리 내에서 연결됩니다."
        else:
            insight = f"'{start_title}'에서 '{end_title}'까지 {chain_length}단계의 관계 체인이 발견되었습니다."

        return insight

    # ==========================================
    # 2. Hidden Connections Discovery
    # ==========================================

    def find_hidden_connections(self, doc_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        간접적으로 연결되어 있지만 직접 관계가 없는 문서들을 발견합니다.
        공통 키워드, 카테고리, 제공기관을 기반으로 숨겨진 연결을 찾습니다.

        Args:
            doc_id: 기준 문서 ID
            limit: 최대 반환 개수

        Returns:
            숨겨진 연결 목록
        """
        logger.info(f"Finding hidden connections for document: {doc_id}")

        # Cypher 쿼리: 간접 연결 발견 (공통 키워드/카테고리/제공기관)
        query = f"""
        MATCH (source:{NodeLabel.DOCUMENT} {{api_id: $doc_id}})

        // 이미 직접 연결된 문서는 제외
        OPTIONAL MATCH (source)-[:{RelationType.CUSTOM_RELATED_TO}]-(directly_connected:{NodeLabel.DOCUMENT})
        WITH source, collect(directly_connected.api_id) as excluded_ids

        // 공통 키워드를 가진 문서
        MATCH (source)-[:{RelationType.HAS_KEYWORD}]->(kw:{NodeLabel.KEYWORD})<-[:{RelationType.HAS_KEYWORD}]-(target:{NodeLabel.DOCUMENT})
        WHERE target.api_id <> source.api_id AND NOT target.api_id IN excluded_ids
        WITH source, target, collect(DISTINCT kw.name) as common_keywords, excluded_ids

        // 카테고리 및 제공기관 정보
        OPTIONAL MATCH (source)-[:{RelationType.BELONGS_TO}]->(cat:{NodeLabel.CATEGORY})<-[:{RelationType.BELONGS_TO}]-(target)
        OPTIONAL MATCH (source)-[:{RelationType.PROVIDED_BY}]->(prov:{NodeLabel.PROVIDER})<-[:{RelationType.PROVIDED_BY}]-(target)

        WITH source, target, common_keywords,
             cat.name as common_category,
             prov.name as common_provider,
             size(common_keywords) as keyword_count
        WHERE keyword_count >= 2  // 최소 2개 이상의 공통 키워드

        // 중간 매개 노드 찾기 (키워드, 카테고리, 제공기관)
        WITH source, target, common_keywords, common_category, common_provider, keyword_count
        OPTIONAL MATCH (source)-[:{RelationType.HAS_KEYWORD}]->(intermediate_kw:{NodeLabel.KEYWORD})<-[:{RelationType.HAS_KEYWORD}]-(target)
        WITH source, target, common_keywords, common_category, common_provider, keyword_count,
             collect(DISTINCT {{type: 'Keyword', name: intermediate_kw.name}}) as intermediate_keywords

        OPTIONAL MATCH (source)-[:{RelationType.BELONGS_TO}]->(intermediate_cat:{NodeLabel.CATEGORY})<-[:{RelationType.BELONGS_TO}]-(target)
        WITH source, target, common_keywords, common_category, common_provider, keyword_count, intermediate_keywords,
             CASE WHEN intermediate_cat IS NOT NULL THEN [{{type: 'Category', name: intermediate_cat.name}}] ELSE [] END as intermediate_cat_list

        RETURN
            {{
                id: source.api_id,
                title: source.title,
                category: source.category,
                description: source.description
            }} as source_doc,
            {{
                id: target.api_id,
                title: target.title,
                category: target.category,
                description: target.description
            }} as target_doc,
            common_keywords,
            common_category,
            common_provider,
            keyword_count,
            intermediate_keywords + intermediate_cat_list as intermediate_nodes
        ORDER BY keyword_count DESC
        LIMIT $limit
        """

        try:
            with self.neo4j_service.get_session() as session:
                result = session.run(query, doc_id=doc_id, limit=limit)
                records = list(result)

            connections = []
            for record in records:
                source_doc = record["source_doc"]
                target_doc = record["target_doc"]
                common_keywords = record["common_keywords"]
                common_category = record["common_category"]
                common_provider = record["common_provider"]
                keyword_count = record["keyword_count"]
                intermediate_nodes = record["intermediate_nodes"]

                # 연결 강도 계산 (공통 키워드 개수 기반, 0.0-1.0)
                connection_strength = min(keyword_count / 5.0, 1.0)  # 5개 키워드면 최대

                # 공통 속성 정리
                common_attributes = {
                    "keywords": common_keywords,
                    "category": common_category,
                    "provider": common_provider
                }

                # 제안 관계 타입 결정
                suggested_relationship = self._determine_suggested_relationship(common_keywords, common_category)

                # 연결 이유 생성
                reason = self._generate_connection_reason(common_keywords, common_category, common_provider, keyword_count)

                connections.append({
                    "source_doc": source_doc,
                    "target_doc": target_doc,
                    "intermediate_nodes": intermediate_nodes,
                    "connection_strength": round(connection_strength, 2),
                    "common_attributes": common_attributes,
                    "suggested_relationship": suggested_relationship,
                    "reason": reason
                })

            return {
                "doc_id": doc_id,
                "connections": connections,
                "total": len(connections)
            }

        except Exception as e:
            logger.error(f"Error finding hidden connections for {doc_id}: {e}")
            raise

    def _determine_suggested_relationship(self, common_keywords: List[str], common_category: Optional[str]) -> str:
        """공통 속성 기반 제안 관계 타입 결정"""
        if common_category:
            return "유사"
        elif len(common_keywords) >= 4:
            return "연관"
        else:
            return "참고"

    def _generate_connection_reason(self, keywords: List[str], category: Optional[str], provider: Optional[str], keyword_count: int) -> str:
        """숨겨진 연결 이유 생성"""
        reasons = []

        if keyword_count >= 3:
            reasons.append(f"{keyword_count}개의 공통 키워드 ({', '.join(keywords[:3])})")

        if category:
            reasons.append(f"동일 카테고리 ({category})")

        if provider:
            reasons.append(f"동일 제공기관 ({provider})")

        return "로 연결됩니다.".join(reasons) if reasons else "공통 속성으로 연결됩니다."

    # ==========================================
    # 3. Community Detection
    # ==========================================

    def detect_communities(self, min_size: int = 3) -> Dict[str, Any]:
        """
        Louvain 알고리즘을 사용하여 그래프 내 커뮤니티를 탐지합니다.

        Args:
            min_size: 최소 커뮤니티 크기 (노드 개수)

        Returns:
            발견된 커뮤니티 목록
        """
        logger.info("Detecting communities using Louvain algorithm")

        # Neo4j에서 전체 그래프 데이터 가져오기 (사용자 정의 관계만)
        query = f"""
        MATCH (d1:{NodeLabel.DOCUMENT})-[r:{RelationType.CUSTOM_RELATED_TO}]-(d2:{NodeLabel.DOCUMENT})
        RETURN
            d1.api_id as source_id,
            d1.title as source_title,
            d1.category as source_category,
            d1.provider as source_provider,
            d2.api_id as target_id,
            d2.title as target_title,
            d2.category as target_category,
            d2.provider as target_provider,
            r.strength as weight
        """

        try:
            with self.neo4j_service.get_session() as session:
                result = session.run(query)
                records = list(result)

            if not records:
                logger.warning("No custom relationships found for community detection")
                return {
                    "communities": [],
                    "total_communities": 0,
                    "modularity": 0.0
                }

            # NetworkX 그래프 구축
            G = nx.Graph()
            node_info = {}  # 노드 정보 저장

            for record in records:
                source_id = record["source_id"]
                target_id = record["target_id"]
                weight = record["weight"] or 1.0

                # 노드 정보 저장
                if source_id not in node_info:
                    node_info[source_id] = {
                        "id": source_id,
                        "title": record["source_title"],
                        "category": record["source_category"],
                        "provider": record["source_provider"]
                    }

                if target_id not in node_info:
                    node_info[target_id] = {
                        "id": target_id,
                        "title": record["target_title"],
                        "category": record["target_category"],
                        "provider": record["target_provider"]
                    }

                # 엣지 추가
                G.add_edge(source_id, target_id, weight=weight)

            # Louvain 커뮤니티 탐지
            partition = community_louvain.best_partition(G)
            modularity = community_louvain.modularity(partition, G)

            # 커뮤니티별 노드 그룹화
            communities_dict = {}
            for node_id, comm_id in partition.items():
                if comm_id not in communities_dict:
                    communities_dict[comm_id] = []
                communities_dict[comm_id].append(node_id)

            # 커뮤니티 분석 및 포맷팅
            communities = []
            for comm_id, node_ids in communities_dict.items():
                if len(node_ids) < min_size:
                    continue

                # 커뮤니티 노드 정보
                nodes = [node_info[nid] for nid in node_ids if nid in node_info]

                # 주요 카테고리 및 제공기관 분석
                categories = [n["category"] for n in nodes if n.get("category")]
                providers = [n["provider"] for n in nodes if n.get("provider")]

                category_counter = Counter(categories)
                provider_counter = Counter(providers)

                dominant_category = category_counter.most_common(1)[0][0] if category_counter else None
                dominant_provider = provider_counter.most_common(1)[0][0] if provider_counter else None

                # 공통 키워드 찾기 (이 커뮤니티 문서들의 공통 키워드)
                common_keywords = self._find_community_keywords(node_ids)

                # 커뮤니티 설명 생성
                description = self._generate_community_description(
                    len(nodes), dominant_category, dominant_provider, common_keywords
                )

                communities.append({
                    "community_id": comm_id,
                    "nodes": nodes,
                    "size": len(nodes),
                    "dominant_category": dominant_category,
                    "dominant_provider": dominant_provider,
                    "common_keywords": common_keywords[:5],  # 상위 5개
                    "description": description
                })

            # 크기 순으로 정렬
            communities.sort(key=lambda c: c["size"], reverse=True)

            return {
                "communities": communities,
                "total_communities": len(communities),
                "modularity": round(modularity, 3)
            }

        except Exception as e:
            logger.error(f"Error detecting communities: {e}")
            raise

    def _find_community_keywords(self, node_ids: List[str]) -> List[str]:
        """커뮤니티 문서들의 공통 키워드 찾기"""
        if not node_ids:
            return []

        query = f"""
        MATCH (d:{NodeLabel.DOCUMENT})-[:{RelationType.HAS_KEYWORD}]->(kw:{NodeLabel.KEYWORD})
        WHERE d.api_id IN $node_ids
        WITH kw.name as keyword, count(DISTINCT d) as doc_count
        WHERE doc_count >= 2  // 최소 2개 문서에서 공통
        RETURN keyword
        ORDER BY doc_count DESC
        LIMIT 10
        """

        try:
            with self.neo4j_service.get_session() as session:
                result = session.run(query, node_ids=node_ids)
                keywords = [record["keyword"] for record in result]
            return keywords
        except Exception as e:
            logger.error(f"Error finding community keywords: {e}")
            return []

    def _generate_community_description(self, size: int, category: Optional[str], provider: Optional[str], keywords: List[str]) -> str:
        """커뮤니티 설명 생성"""
        desc = f"{size}개의 문서로 구성된 커뮤니티입니다. "

        if category:
            desc += f"주로 '{category}' 카테고리에 속하며, "

        if provider:
            desc += f"'{provider}' 제공기관의 데이터가 많습니다. "

        if keywords:
            desc += f"공통 키워드: {', '.join(keywords[:3])}"

        return desc

    # ==========================================
    # 4. Centrality Analysis
    # ==========================================

    def calculate_centrality(self, limit: int = 20) -> Dict[str, Any]:
        """
        그래프 내 중요 노드를 중심성 지표로 분석합니다.
        - Degree Centrality (연결 중심성)
        - Betweenness Centrality (매개 중심성)
        - PageRank (페이지랭크)

        Args:
            limit: 최대 반환 노드 개수

        Returns:
            상위 중요 노드 목록
        """
        logger.info("Calculating centrality metrics")

        # Neo4j에서 전체 그래프 데이터 가져오기
        query = f"""
        MATCH (d1:{NodeLabel.DOCUMENT})-[r:{RelationType.CUSTOM_RELATED_TO}]-(d2:{NodeLabel.DOCUMENT})
        RETURN
            d1.api_id as source_id,
            d1.title as source_title,
            d1.category as source_category,
            d2.api_id as target_id,
            d2.title as target_title,
            d2.category as target_category,
            r.strength as weight
        """

        try:
            with self.neo4j_service.get_session() as session:
                result = session.run(query)
                records = list(result)

            if not records:
                logger.warning("No custom relationships found for centrality analysis")
                return {
                    "top_nodes": [],
                    "total_analyzed": 0,
                    "insights": "분석할 사용자 정의 관계가 없습니다."
                }

            # NetworkX 그래프 구축
            G = nx.Graph()
            node_info = {}

            for record in records:
                source_id = record["source_id"]
                target_id = record["target_id"]
                weight = record["weight"] or 1.0

                # 노드 정보 저장
                if source_id not in node_info:
                    node_info[source_id] = {
                        "id": source_id,
                        "title": record["source_title"],
                        "type": "Document",
                        "category": record["source_category"]
                    }

                if target_id not in node_info:
                    node_info[target_id] = {
                        "id": target_id,
                        "title": record["target_title"],
                        "type": "Document",
                        "category": record["target_category"]
                    }

                # 엣지 추가
                G.add_edge(source_id, target_id, weight=weight)

            # 중심성 지표 계산
            degree_centrality = nx.degree_centrality(G)
            betweenness_centrality = nx.betweenness_centrality(G, weight='weight')
            pagerank = nx.pagerank(G, weight='weight')

            # 각 노드의 중심성 점수 종합
            node_scores = []
            for node_id in G.nodes():
                if node_id not in node_info:
                    continue

                degree = degree_centrality[node_id]
                betweenness = betweenness_centrality[node_id]
                pr = pagerank[node_id]

                # 종합 중요도 점수 (가중 평균)
                importance_score = (degree * 0.3) + (betweenness * 0.3) + (pr * 0.4)

                node_scores.append({
                    "node_id": node_id,
                    "node_title": node_info[node_id]["title"],
                    "node_type": node_info[node_id]["type"],
                    "degree_centrality": round(degree, 4),
                    "betweenness_centrality": round(betweenness, 4),
                    "pagerank": round(pr, 4),
                    "importance_score": round(importance_score, 4)
                })

            # 중요도 순으로 정렬
            node_scores.sort(key=lambda x: x["importance_score"], reverse=True)
            top_nodes = node_scores[:limit]

            # 인사이트 생성
            insights = self._generate_centrality_insights(top_nodes, len(G.nodes()))

            return {
                "top_nodes": top_nodes,
                "total_analyzed": len(G.nodes()),
                "insights": insights
            }

        except Exception as e:
            logger.error(f"Error calculating centrality: {e}")
            raise

    def _generate_centrality_insights(self, top_nodes: List[dict], total_nodes: int) -> str:
        """중심성 분석 인사이트 생성"""
        if not top_nodes:
            return "분석할 노드가 없습니다."

        top_node = top_nodes[0]
        insights = f"총 {total_nodes}개 문서 중 '{top_node['node_title']}'가 가장 중요한 허브 문서입니다. "
        insights += f"(중요도 점수: {top_node['importance_score']:.3f}) "

        # 상위 3개 문서의 카테고리 분석
        if len(top_nodes) >= 3:
            top_3_titles = [n["node_title"] for n in top_nodes[:3]]
            insights += f"상위 핵심 문서: {', '.join(top_3_titles[:2])}"

        return insights

    # ==========================================
    # 5. Complementary Data Recommendations
    # ==========================================

    def suggest_complementary_data(self, doc_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        현재 문서 및 연결된 문서들을 분석하여 부족한 영역을 채울 수 있는
        보완 데이터를 추천합니다.

        Args:
            doc_id: 기준 문서 ID
            limit: 최대 추천 개수

        Returns:
            보완 데이터 추천 목록
        """
        logger.info(f"Suggesting complementary data for document: {doc_id}")

        # 1. 현재 문서 및 연결된 문서들의 커버리지 분석
        coverage_query = f"""
        MATCH (source:{NodeLabel.DOCUMENT} {{api_id: $doc_id}})
        OPTIONAL MATCH (source)-[:{RelationType.CUSTOM_RELATED_TO}*1..2]-(connected:{NodeLabel.DOCUMENT})

        WITH source, collect(DISTINCT connected) as connected_docs

        // 키워드 커버리지
        OPTIONAL MATCH (source)-[:{RelationType.HAS_KEYWORD}]->(kw:{NodeLabel.KEYWORD})
        WITH source, connected_docs, collect(DISTINCT kw.name) as current_keywords

        // 카테고리 커버리지
        OPTIONAL MATCH (source)-[:{RelationType.BELONGS_TO}]->(cat:{NodeLabel.CATEGORY})
        WITH source, connected_docs, current_keywords, collect(DISTINCT cat.name) as current_categories

        // 제공기관 커버리지
        OPTIONAL MATCH (source)-[:{RelationType.PROVIDED_BY}]->(prov:{NodeLabel.PROVIDER})
        WITH source, connected_docs, current_keywords, current_categories, collect(DISTINCT prov.name) as current_providers

        RETURN
            source.api_id as doc_id,
            source.title as doc_title,
            source.category as doc_category,
            current_keywords,
            current_categories,
            current_providers,
            size(connected_docs) as connected_count
        """

        # 2. 커버리지 갭을 채울 수 있는 문서 찾기
        recommendations_query = f"""
        MATCH (source:{NodeLabel.DOCUMENT} {{api_id: $doc_id}})

        // 현재 문서의 키워드 및 카테고리
        OPTIONAL MATCH (source)-[:{RelationType.HAS_KEYWORD}]->(source_kw:{NodeLabel.KEYWORD})
        OPTIONAL MATCH (source)-[:{RelationType.BELONGS_TO}]->(source_cat:{NodeLabel.CATEGORY})
        WITH source, collect(DISTINCT source_kw.name) as source_keywords, source_cat.name as source_category

        // 이미 연결된 문서 제외
        OPTIONAL MATCH (source)-[:{RelationType.CUSTOM_RELATED_TO}*1..2]-(connected:{NodeLabel.DOCUMENT})
        WITH source, source_keywords, source_category, collect(DISTINCT connected.api_id) as excluded_ids

        // 다른 카테고리지만 관련 키워드를 가진 문서 찾기
        MATCH (target:{NodeLabel.DOCUMENT})
        WHERE target.api_id <> source.api_id
          AND NOT target.api_id IN excluded_ids
          AND target.category <> source_category  // 다른 카테고리

        // 공통 키워드 확인
        OPTIONAL MATCH (target)-[:{RelationType.HAS_KEYWORD}]->(target_kw:{NodeLabel.KEYWORD})
        WHERE target_kw.name IN source_keywords

        WITH source, target, source_category, target.category as target_category,
             collect(DISTINCT target_kw.name) as common_keywords,
             size(collect(DISTINCT target_kw.name)) as common_count

        WHERE common_count >= 1  // 최소 1개 공통 키워드

        // 관련성 점수 계산
        WITH source, target, source_category, target_category, common_keywords,
             (toFloat(common_count) / 5.0) as relevance_score  // 5개면 최대 점수

        RETURN
            target.api_id as doc_id,
            target.title as title,
            target_category as category,
            CASE
                WHEN relevance_score > 1.0 THEN 1.0
                ELSE relevance_score
            END as relevance_score,
            common_keywords,
            target_category + ' 영역의 보완' as gap_filled
        ORDER BY relevance_score DESC
        LIMIT $limit
        """

        try:
            with self.neo4j_service.get_session() as session:
                # 커버리지 분석
                coverage_result = session.run(coverage_query, doc_id=doc_id)
                coverage_record = coverage_result.single()

                if not coverage_record:
                    raise ValueError(f"Document {doc_id} not found")

                coverage_analysis = {
                    "current_keywords": coverage_record["current_keywords"],
                    "current_categories": coverage_record["current_categories"],
                    "current_providers": coverage_record["current_providers"],
                    "connected_count": coverage_record["connected_count"]
                }

                # 보완 데이터 추천
                rec_result = session.run(recommendations_query, doc_id=doc_id, limit=limit)
                rec_records = list(rec_result)

            recommendations = []
            for record in rec_records:
                common_kw = record["common_keywords"]

                # 추천 이유 생성
                reason = self._generate_complementary_reason(
                    coverage_record["doc_category"],
                    record["category"],
                    common_kw
                )

                recommendations.append({
                    "doc_id": record["doc_id"],
                    "title": record["title"],
                    "category": record["category"],
                    "relevance_score": round(record["relevance_score"], 2),
                    "gap_filled": record["gap_filled"],
                    "reason": reason
                })

            return {
                "doc_id": doc_id,
                "recommendations": recommendations,
                "total": len(recommendations),
                "coverage_analysis": coverage_analysis
            }

        except Exception as e:
            logger.error(f"Error suggesting complementary data for {doc_id}: {e}")
            raise

    def _generate_complementary_reason(self, source_category: str, target_category: str, common_keywords: List[str]) -> str:
        """보완 데이터 추천 이유 생성"""
        reason = f"'{source_category}'에서 '{target_category}' 영역으로 확장할 수 있습니다. "

        if common_keywords:
            reason += f"공통 키워드: {', '.join(common_keywords[:3])}"

        return reason

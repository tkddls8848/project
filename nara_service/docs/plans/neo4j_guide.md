 현재 시스템 구조

  프로젝트는 이미 잘 구조화된 Neo4j 관계 시스템을 가지고 있습니다:

  1. 그래프 스키마 (graph_schema.py:10-36)

  노드 타입:
  - Document: API 문서 (예: "한국문화관광연구원 관광실태조사서비스")
  - Keyword: 키워드 (예: "조사통계", "국민여행조사")
  - Provider: 제공기관 (예: "한국문화관광연구원")
  - Category: 카테고리 (예: "일반공공행정 - 정부자원관리")

  관계 타입:
  - HAS_KEYWORD: Document → Keyword
  - PROVIDED_BY: Document → Provider
  - BELONGS_TO: Document → Category
  - CUSTOM_RELATED_TO: Document → Document (사용자 정의)

  2. Neo4j 관계 쿼리 작성 방법

  현재 시스템에서 사용 가능한 주요 쿼리 패턴들을 설명하겠습니다:

  패턴 1: 특정 키워드를 가진 문서 찾기

  MATCH (d:Document)-[:HAS_KEYWORD]->(k:Keyword {name: "조사통계"})
  RETURN d.title, d.description
  LIMIT 10

  패턴 2: 같은 제공기관의 문서들 찾기

  MATCH (p:Provider {name: "한국문화관광연구원"})<-[:PROVIDED_BY]-(d:Document)
  RETURN d.api_id, d.title

  패턴 3: 특정 카테고리의 문서들 찾기

  MATCH (c:Category {name: "일반공공행정 - 정부자원관리"})<-[:BELONGS_TO]-(d:Document)
  RETURN d.api_id, d.title

  패턴 4: 공통 키워드를 가진 관련 문서 찾기

  MATCH (d1:Document {api_id: "15000017"})-[:HAS_KEYWORD]->(k:Keyword)<-[:HAS_KEYWORD]-(d2:Document)
  WHERE d1 <> d2
  RETURN d2.title, collect(k.name) as common_keywords
  ORDER BY size(collect(k.name)) DESC
  LIMIT 5

  패턴 5: 문서의 모든 관계 정보 조회

  MATCH (d:Document {api_id: "15000017"})
  OPTIONAL MATCH (d)-[:HAS_KEYWORD]->(k:Keyword)
  OPTIONAL MATCH (d)-[:PROVIDED_BY]->(p:Provider)
  OPTIONAL MATCH (d)-[:BELONGS_TO]->(c:Category)
  RETURN
    d.title as document,
    collect(DISTINCT k.name) as keywords,
    p.name as provider,
    c.name as category

  패턴 6: 키워드 네트워크 분석

  MATCH (k1:Keyword)<-[:HAS_KEYWORD]-(d:Document)-[:HAS_KEYWORD]->(k2:Keyword)
  WHERE k1 <> k2
  RETURN k1.name, k2.name, count(d) as co_occurrence
  ORDER BY co_occurrence DESC
  LIMIT 20

  3. 실제 사용 예시

  코드에서 이미 구현된 쿼리들을 확인할 수 있습니다:

  - get_related_context (neo4j_service.py:162-208): 문서의 관련 컨텍스트 검색
  - explore_graph (neo4j_service.py:214-464): 그래프 탐색
  - suggest_relationships (neo4j_service.py:1069-1253): 관계 추천

  4. 새로운 관계 추가 방법

  relationship_config.py에 새로운 자동 관계를 추가하려면:

  AUTO_RELATIONSHIPS.append(
      AutoRelationship(
          name="region",
          description="문서 지역 관계",
          relationship_type="LOCATED_IN",
          target_node_label="Region",
          target_property="name",
          source_data_path="metadata.region",  # RAG 데이터의 경로
          is_list=False
      )
  )

  어떤 특정 쿼리를 작성하고 싶으신가요? 구체적인 사용 사례를 알려주시면 맞춤형 쿼리를 작성해드리겠습니다.

> graph_schema.py위치가 어디냐 

● graph_schema.py 파일의 위치입니다:

  절대 경로:
  C:\python_app\python_app\nara_service\backend\app\graph_schema.py

  현재 작업 디렉토리 기준 상대 경로:
  backend\app\graph_schema.py

  참고로 관련 파일들의 위치는 다음과 같습니다:

  - graph_schema.py: backend\app\graph_schema.py (노드/관계 정의)
  - relationship_config.py: backend\app\core\relationship_config.py (자동 관계 설정)
  - neo4j_service.py: backend\app\services\neo4j_service.py (Neo4j 서비스 로직)
  - neo4j_loader.py: backend\app\services\neo4j_loader.py (데이터 로더)

  이 파일들을 수정하여 그래프 스키마나 관계를 변경할 수 있습니다.
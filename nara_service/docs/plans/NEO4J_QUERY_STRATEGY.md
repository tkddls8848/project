# Neo4j 심도있는 데이터 관계성 쿼리 전략

## 📋 목차
1. [개요](#개요)
2. [데이터 모델 구조](#데이터-모델-구조)
3. [고급 쿼리 전략](#고급-쿼리-전략)
4. [쿼리 최적화 기법](#쿼리-최적화-기법)
5. [인덱싱 전략](#인덱싱-전략)
6. [사용 예시](#사용-예시)
7. [성능 모니터링](#성능-모니터링)

---

## 개요

이 문서는 NARA 서비스의 Neo4j 그래프 데이터베이스에서 심도있는 데이터 관계성을 탐색하기 위한 고급 쿼리 전략을 설명합니다.

### 주요 기능

- **복잡한 다중 조건 쿼리**: 여러 필터를 조합한 정교한 검색
- **관계 강도 기반 필터링**: 의미있는 연결만 추출
- **패턴 매칭**: 삼각 관계, 공통 이웃 등 특정 패턴 발견
- **시계열 분석**: 관계 생성 시간 기반 트렌드 분석
- **경로 기반 탐색**: 다양한 경로 찾기 및 분석
- **집계 통계**: 그룹별 통계 및 인사이트

---

## 데이터 모델 구조

### 노드 타입 (Nodes)

```cypher
// 주요 노드
(:Document)   - 공공데이터 API 문서
(:Keyword)    - 메타데이터 키워드
(:Category)   - 데이터 분류
(:Provider)   - 데이터 제공 기관
```

### 관계 타입 (Relationships)

```cypher
// 자동 생성 관계
(:Document)-[:HAS_KEYWORD]->(:Keyword)
(:Document)-[:BELONGS_TO]->(:Category)
(:Document)-[:PROVIDED_BY]->(:Provider)

// 사용자 정의 관계
(:Document)-[:CUSTOM_RELATED_TO {
    custom_type: "보완|유사|인과|참고|시계열",
    description: "관계 설명",
    strength: 0.0-1.0,
    created_at: datetime,
    created_by: "user|ai|system"
}]->(:Document)
```

### 주요 속성

```cypher
// Document 속성
{
    api_id: "고유 ID",
    title: "문서 제목",
    description: "문서 설명",
    url: "크롤링 URL",
    created_at: datetime
}

// Relationship 속성 (CUSTOM_RELATED_TO)
{
    custom_type: "관계 타입",
    description: "설명",
    strength: 0.0-1.0,  // 관계 강도
    created_at: datetime,
    created_by: "생성자"
}
```

---

## 고급 쿼리 전략

### 1. 복잡한 다중 조건 쿼리

#### 1.1 노드 속성 + 관계 조건 조합

```python
from app.services.advanced_query_service import AdvancedQueryService

advanced_service = AdvancedQueryService(neo4j_service)

# 복잡한 필터링 예시
result = advanced_service.search_documents_advanced(
    filters=[
        {"field": "title", "operator": "contains", "value": "교육"},
        {"field": "description", "operator": "contains", "value": "복지"}
    ],
    relationship_filters=[
        {
            "rel_type": "HAS_KEYWORD",
            "target_label": "Keyword",
            "target_field": "name",
            "operator": "in",
            "value": ["보육", "어린이집"]
        },
        {
            "rel_type": "BELONGS_TO",
            "target_label": "Category",
            "target_field": "name",
            "operator": "eq",
            "value": "사회복지"
        }
    ],
    sort_by="created_at",
    sort_order="DESC",
    limit=50
)
```

**Cypher 쿼리 예시:**
```cypher
MATCH (d:Document)
MATCH (d)-[:HAS_KEYWORD]->(target_0:Keyword)
MATCH (d)-[:BELONGS_TO]->(target_1:Category)
WHERE d.title CONTAINS "교육"
  AND d.description CONTAINS "복지"
  AND target_0.name IN ["보육", "어린이집"]
  AND target_1.name = "사회복지"
WITH DISTINCT d
ORDER BY d.created_at DESC
SKIP 0
LIMIT 50
RETURN d
```

#### 1.2 동적 필터 빌더

지원하는 필터 연산자:
- `eq`: 같음 (=)
- `ne`: 같지 않음 (<>)
- `contains`: 포함 (CONTAINS)
- `in`: 목록에 포함 (IN)
- `not_in`: 목록에 미포함 (NOT IN)
- `gt`: 초과 (>)
- `lt`: 미만 (<)
- `gte`: 이상 (>=)
- `lte`: 이하 (<=)

### 2. 관계 강도 기반 쿼리

#### 2.1 강한 관계만 필터링

```python
# 0.7 이상의 강한 관계만 조회
result = advanced_service.find_strong_connections(
    doc_id="15002724",
    min_strength=0.7,
    relationship_types=["CUSTOM_RELATED_TO"],
    limit=20
)
```

**Cypher 쿼리:**
```cypher
MATCH (source:Document {api_id: "15002724"})-[r:CUSTOM_RELATED_TO]-(target:Document)
WHERE r.strength IS NOT NULL AND r.strength >= 0.7
RETURN target, r
ORDER BY r.strength DESC
LIMIT 20
```

#### 2.2 관계 강도별 그룹화

```cypher
MATCH (d:Document)-[r:CUSTOM_RELATED_TO]-(other:Document)
WHERE r.strength IS NOT NULL
WITH
    CASE
        WHEN r.strength >= 0.8 THEN "매우 강함"
        WHEN r.strength >= 0.6 THEN "강함"
        WHEN r.strength >= 0.4 THEN "보통"
        ELSE "약함"
    END as strength_category,
    count(r) as relationship_count
RETURN strength_category, relationship_count
ORDER BY relationship_count DESC
```

### 3. 패턴 매칭 쿼리

#### 3.1 삼각 관계 패턴 (Triangles)

밀접하게 연결된 문서 그룹 발견:

```python
result = advanced_service.find_triangular_relationships(
    doc_id="15002724",
    limit=10
)
```

**Cypher 쿼리:**
```cypher
MATCH (a:Document {api_id: "15002724"})-[r1:CUSTOM_RELATED_TO]-(b:Document)
      -[r2:CUSTOM_RELATED_TO]-(c:Document)
      -[r3:CUSTOM_RELATED_TO]-(a)
WHERE a <> b AND b <> c AND c <> a
RETURN DISTINCT b, c, r1, r2, r3
LIMIT 10
```

**활용 사례:**
- 서로 밀접하게 연관된 문서 클러스터 발견
- 순환 참조 패턴 분석
- 핵심 문서 그룹 식별

#### 3.2 공통 이웃 노드 찾기

여러 문서가 공통으로 연결된 노드 발견:

```python
result = advanced_service.find_common_neighbors(
    doc_ids=["15002724", "15002725", "15002731"],
    min_common=2,
    limit=20
)
```

**Cypher 쿼리:**
```cypher
MATCH (d:Document)
WHERE d.api_id IN ["15002724", "15002725", "15002731"]

MATCH (d)-[r]-(neighbor)
WHERE neighbor:Keyword OR neighbor:Category OR neighbor:Provider OR neighbor:Document

WITH neighbor, type(r) as rel_type, count(DISTINCT d) as connection_count
WHERE connection_count >= 2

RETURN neighbor, rel_type, connection_count
ORDER BY connection_count DESC
LIMIT 20
```

**활용 사례:**
- 여러 문서의 공통 주제 발견
- 문서 간 연관성 분석
- 클러스터링 기초 데이터 추출

#### 3.3 스타 패턴 (Hub Detection)

많은 연결을 가진 허브 노드 찾기:

```cypher
MATCH (hub)-[r:CUSTOM_RELATED_TO]-(doc:Document)
WITH hub, count(r) as connection_count
WHERE connection_count >= 5
RETURN hub, connection_count
ORDER BY connection_count DESC
LIMIT 10
```

### 4. 경로 기반 고급 탐색

#### 4.1 모든 경로 찾기

최단 경로뿐만 아니라 가능한 모든 경로 탐색:

```python
result = advanced_service.find_all_paths(
    source_id="15002724",
    target_id="15002731",
    max_depth=4,
    limit=10
)
```

**Cypher 쿼리:**
```cypher
MATCH (source:Document {api_id: "15002724"}),
      (target:Document {api_id: "15002731"}),
      path = (source)-[*1..4]-(target)
WHERE source <> target
RETURN path, length(path) as path_length
ORDER BY path_length ASC
LIMIT 10
```

#### 4.2 특정 노드를 경유하는 경로

```python
result = advanced_service.find_paths_through_node(
    through_id="교육",
    through_type="Keyword",
    max_depth=3,
    limit=20
)
```

**Cypher 쿼리:**
```cypher
MATCH (through:Keyword {name: "교육"})
MATCH path = (start)-[*1..3]-(through)-[*1..3]-(end)
WHERE start:Document AND end:Document AND start <> end
RETURN start, end, length(path) as path_length
ORDER BY path_length ASC
LIMIT 20
```

**활용 사례:**
- 특정 키워드/카테고리를 중심으로 한 문서 연결망 분석
- 매개 역할을 하는 중요 노드 식별
- 주제별 문서 그룹화

#### 4.3 조건부 경로 탐색

특정 조건을 만족하는 경로만 찾기:

```cypher
MATCH path = (source:Document {api_id: "15002724"})-[*1..4]-(target:Document)
WHERE source <> target
  AND all(r in relationships(path) WHERE r.strength >= 0.5)  // 모든 관계가 강해야 함
  AND length(path) <= 3  // 최대 3단계
RETURN path, length(path) as path_length
ORDER BY path_length ASC
LIMIT 10
```

### 5. 시계열 분석

#### 5.1 관계 생성 트렌드 분석

```python
result = advanced_service.analyze_temporal_patterns(
    time_window_days=30,
    group_by="day"  # "day", "week", "month"
)
```

**Cypher 쿼리 (일별):**
```cypher
MATCH ()-[r:CUSTOM_RELATED_TO]->()
WHERE r.created_at >= datetime("2025-11-23T00:00:00")
WITH date(r.created_at) as time_bucket, r
RETURN
    toString(time_bucket) as period,
    count(r) as relationship_count,
    collect(DISTINCT r.custom_type) as relationship_types,
    avg(r.strength) as avg_strength
ORDER BY period
```

**주별 그룹화:**
```cypher
// 주의 시작일(월요일) 기준으로 그룹화
WITH date(r.created_at) - duration({days: date(r.created_at).dayOfWeek - 1}) as week_start
```

**월별 그룹화:**
```cypher
WITH date(datetime({year: r.created_at.year, month: r.created_at.month, day: 1})) as month_start
```

#### 5.2 시간대별 관계 타입 분석

```cypher
MATCH ()-[r:CUSTOM_RELATED_TO]->()
WHERE r.created_at >= datetime() - duration({days: 90})
WITH date(r.created_at) as period, r.custom_type as rel_type
RETURN period, rel_type, count(*) as count
ORDER BY period, count DESC
```

### 6. 집계 및 통계 쿼리

#### 6.1 그룹별 집계

```python
# 카테고리별 문서 개수
result = advanced_service.aggregate_by_relationship_type(
    group_by="category",
    aggregation="count"
)

# 키워드별 문서 목록
result = advanced_service.aggregate_by_relationship_type(
    group_by="keyword",
    aggregation="collect"
)
```

**Cypher 쿼리:**
```cypher
MATCH (d:Document)-[:BELONGS_TO]->(group:Category)
WITH group, count(d) as agg_value
RETURN group.name as group_name, agg_value
ORDER BY agg_value DESC
LIMIT 50
```

#### 6.2 전체 관계 통계

```python
result = advanced_service.get_relationship_statistics()
```

반환 결과:
```json
{
    "total_relationships": 1500,
    "by_type": {
        "HAS_KEYWORD": 800,
        "BELONGS_TO": 300,
        "PROVIDED_BY": 300,
        "CUSTOM_RELATED_TO": 100
    },
    "avg_relationships_per_doc": 5.2,
    "custom_relationships": {
        "total": 100,
        "by_custom_type": {
            "보완": 40,
            "유사": 35,
            "참고": 25
        },
        "avg_strength": 0.65
    }
}
```

#### 6.3 복잡한 집계 쿼리

```cypher
// 카테고리별로 가장 많은 키워드를 가진 문서 찾기
MATCH (d:Document)-[:BELONGS_TO]->(c:Category)
OPTIONAL MATCH (d)-[:HAS_KEYWORD]->(k:Keyword)
WITH c, d, count(k) as keyword_count
WITH c, max(keyword_count) as max_keywords
MATCH (d:Document)-[:BELONGS_TO]->(c)
OPTIONAL MATCH (d)-[:HAS_KEYWORD]->(k:Keyword)
WITH c, d, count(k) as keyword_count, max_keywords
WHERE keyword_count = max_keywords
RETURN c.name as category, d.title as document, keyword_count
ORDER BY keyword_count DESC
```

---

## 쿼리 최적화 기법

### 1. 인덱스 활용

#### 1.1 제약조건 (Constraints)

Unique 제약조건은 자동으로 인덱스를 생성합니다:

```cypher
CREATE CONSTRAINT document_api_id IF NOT EXISTS
FOR (d:Document) REQUIRE d.api_id IS UNIQUE;

CREATE CONSTRAINT keyword_name IF NOT EXISTS
FOR (k:Keyword) REQUIRE k.name IS UNIQUE;

CREATE CONSTRAINT category_name IF NOT EXISTS
FOR (c:Category) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT provider_name IF NOT EXISTS
FOR (p:Provider) REQUIRE p.name IS UNIQUE;
```

#### 1.2 일반 인덱스

검색 성능 향상을 위한 인덱스:

```cypher
CREATE INDEX document_title IF NOT EXISTS
FOR (d:Document) ON (d.title);

CREATE INDEX document_description IF NOT EXISTS
FOR (d:Document) ON (d.description);

CREATE INDEX document_created_at IF NOT EXISTS
FOR (d:Document) ON (d.created_at);
```

#### 1.3 복합 인덱스

여러 속성을 함께 검색하는 경우:

```cypher
CREATE INDEX document_title_category IF NOT EXISTS
FOR (d:Document) ON (d.title, d.category);
```

### 2. 쿼리 작성 모범 사례

#### 2.1 MATCH 순서 최적화

**나쁜 예:**
```cypher
MATCH (d:Document)-[:HAS_KEYWORD]->(k:Keyword)
WHERE d.api_id = "15002724"
RETURN d, k
```

**좋은 예:**
```cypher
MATCH (d:Document {api_id: "15002724"})-[:HAS_KEYWORD]->(k:Keyword)
RETURN d, k
```

인덱스를 활용하여 먼저 특정 문서를 찾은 후 관계를 탐색합니다.

#### 2.2 WITH 절 활용

중간 결과를 필터링하여 데이터 양 줄이기:

```cypher
MATCH (d:Document)-[:HAS_KEYWORD]->(k:Keyword)
WITH d, collect(k.name) as keywords
WHERE size(keywords) >= 3
RETURN d, keywords
```

#### 2.3 LIMIT 조기 적용

```cypher
MATCH (d:Document)
WHERE d.title CONTAINS "교육"
WITH d
LIMIT 100  // 조기에 결과 제한
MATCH (d)-[:HAS_KEYWORD]->(k:Keyword)
RETURN d, collect(k.name) as keywords
```

#### 2.4 변수 길이 경로 제한

**나쁜 예:**
```cypher
MATCH path = (a)-[*]-(b)  // 무한 탐색 가능
RETURN path
```

**좋은 예:**
```cypher
MATCH path = (a)-[*1..4]-(b)  // 최대 4단계로 제한
RETURN path
```

#### 2.5 DISTINCT 사용 최소화

필요한 경우에만 사용:

```cypher
// DISTINCT가 필요한 경우
MATCH (d:Document)-[:HAS_KEYWORD]->(k:Keyword)
RETURN DISTINCT d  // 중복 제거 필요

// DISTINCT가 불필요한 경우
MATCH (d:Document {api_id: "15002724"})
RETURN d  // api_id가 unique이므로 DISTINCT 불필요
```

### 3. 파라미터 활용

**나쁜 예 (문자열 연결):**
```python
query = f"MATCH (d:Document {{api_id: '{doc_id}'}}) RETURN d"
```

**좋은 예 (파라미터):**
```python
query = "MATCH (d:Document {api_id: $doc_id}) RETURN d"
session.run(query, doc_id=doc_id)
```

파라미터 사용의 장점:
- 쿼리 계획 캐싱
- SQL 인젝션 방지
- 코드 가독성 향상

### 4. 프로파일링 및 모니터링

#### 4.1 EXPLAIN과 PROFILE 사용

```cypher
EXPLAIN MATCH (d:Document {api_id: "15002724"})-[:HAS_KEYWORD]->(k:Keyword) RETURN d, k;
PROFILE MATCH (d:Document {api_id: "15002724"})-[:HAS_KEYWORD]->(k:Keyword) RETURN d, k;
```

- `EXPLAIN`: 실행 계획만 확인 (실제 실행 안 함)
- `PROFILE`: 실제 실행 + 성능 통계

#### 4.2 주요 성능 지표

- **db hits**: 데이터베이스 접근 횟수 (낮을수록 좋음)
- **rows**: 반환된 행 수
- **time**: 실행 시간

---

## 인덱싱 전략

### 1. 현재 인덱스 구조

#### Unique Constraints (자동 인덱스 생성)
- `Document.api_id`
- `Keyword.name`
- `Category.name`
- `Provider.name`

#### 일반 인덱스
- `Document.title`
- `Document.description`

### 2. 추가 권장 인덱스

```cypher
-- 시계열 분석용
CREATE INDEX relationship_created_at IF NOT EXISTS
FOR ()-[r:CUSTOM_RELATED_TO]-() ON (r.created_at);

-- 관계 강도 기반 쿼리용
CREATE INDEX relationship_strength IF NOT EXISTS
FOR ()-[r:CUSTOM_RELATED_TO]-() ON (r.strength);

-- 관계 타입별 필터링용
CREATE INDEX relationship_custom_type IF NOT EXISTS
FOR ()-[r:CUSTOM_RELATED_TO]-() ON (r.custom_type);

-- Full-text 검색용
CREATE FULLTEXT INDEX document_fulltext IF NOT EXISTS
FOR (d:Document) ON EACH [d.title, d.description];
```

### 3. 인덱스 사용 확인

```cypher
-- 인덱스 목록 조회
SHOW INDEXES;

-- 제약조건 목록 조회
SHOW CONSTRAINTS;

-- 인덱스 사용 여부 확인 (EXPLAIN 사용)
EXPLAIN MATCH (d:Document {api_id: "15002724"}) RETURN d;
```

실행 계획에서 `NodeIndexSeek` 또는 `NodeUniqueIndexSeek`가 나타나면 인덱스를 사용 중입니다.

### 4. 인덱스 관리

```python
from app.services.neo4j_indexes import Neo4jIndexManager

# 인덱스 매니저 초기화
manager = Neo4jIndexManager(neo4j_driver)

# 모든 인덱스 생성
manager.create_indexes()

# 인덱스 목록 조회
indexes_info = manager.list_indexes()

# 쿼리 성능 분석
profile = manager.analyze_query_performance("MATCH (d:Document) RETURN d LIMIT 10")
```

---

## 사용 예시

### 예시 1: 특정 주제의 강한 연결망 찾기

```python
from app.services.advanced_query_service import AdvancedQueryService

advanced_service = AdvancedQueryService(neo4j_service)

# 1. 교육 관련 문서 검색
education_docs = advanced_service.search_documents_advanced(
    filters=[
        {"field": "title", "operator": "contains", "value": "교육"}
    ],
    relationship_filters=[
        {
            "rel_type": "HAS_KEYWORD",
            "target_label": "Keyword",
            "target_field": "name",
            "operator": "in",
            "value": ["교육", "학교", "학생"]
        }
    ],
    limit=10
)

# 2. 각 문서의 강한 연결 찾기
for doc in education_docs["documents"]:
    strong_connections = advanced_service.find_strong_connections(
        doc_id=doc["id"],
        min_strength=0.6,
        limit=5
    )
    print(f"{doc['title']} - {len(strong_connections['connections'])}개 강한 연결")
```

### 예시 2: 시계열 트렌드 분석

```python
# 최근 30일간 관계 생성 트렌드
trends = advanced_service.analyze_temporal_patterns(
    time_window_days=30,
    group_by="week"
)

print(f"인사이트: {trends['insights']}")

for period_data in trends["timeline"]:
    print(f"{period_data['period']}: {period_data['relationship_count']}개 관계")
    print(f"  - 관계 타입: {', '.join(period_data['relationship_types'])}")
    print(f"  - 평균 강도: {period_data['avg_strength']}")
```

### 예시 3: 커뮤니티 내 핵심 문서 찾기

```python
from app.services.insight_engine import InsightEngine

insight_engine = InsightEngine(neo4j_service)

# 1. 커뮤니티 탐지
communities = insight_engine.detect_communities(min_size=3)

# 2. 각 커뮤니티에서 중심성 분석
for community in communities["communities"][:3]:  # 상위 3개 커뮤니티
    doc_ids = [node["id"] for node in community["nodes"]]

    # 공통 이웃 찾기
    common = advanced_service.find_common_neighbors(
        doc_ids=doc_ids,
        min_common=2,
        limit=10
    )

    print(f"커뮤니티 {community['community_id']}")
    print(f"  - 크기: {community['size']}")
    print(f"  - 주요 카테고리: {community['dominant_category']}")
    print(f"  - 공통 이웃: {len(common['common_neighbors'])}개")
```

### 예시 4: 다중 경로 분석

```python
# 두 문서 간 모든 경로 찾기
paths = advanced_service.find_all_paths(
    source_id="15002724",
    target_id="15002731",
    max_depth=4,
    limit=5
)

for idx, path in enumerate(paths["paths"], 1):
    print(f"경로 {idx} (길이: {path['length']})")

    # 경로상의 노드들
    for node in path["nodes"]:
        print(f"  - {node['type']}: {node['title']}")

    # 경로상의 관계들
    for rel in path["relationships"]:
        rel_label = rel.get("custom_type") or rel["type"]
        print(f"    → {rel_label}")
```

---

## 성능 모니터링

### 1. 쿼리 실행 시간 측정

```python
import time
from app.services.neo4j_service import neo4j_service

start = time.time()
result = neo4j_service.explore_graph(doc_id="15002724", depth=2)
elapsed = time.time() - start

print(f"쿼리 실행 시간: {elapsed:.3f}초")
print(f"노드 개수: {len(result['nodes'])}")
print(f"엣지 개수: {len(result['edges'])}")
```

### 2. 캐시 효율성 모니터링

```python
from app.services.cache_service import get_cache_service

cache = get_cache_service()

# 캐시 통계 (Redis 사용 시)
# Redis CLI: INFO stats
```

### 3. 성능 벤치마크

```python
queries = [
    ("단일 문서 조회", "MATCH (d:Document {api_id: $id}) RETURN d"),
    ("관계 탐색 (depth 1)", "MATCH (d:Document {api_id: $id})-[r]-(n) RETURN d, r, n"),
    ("관계 탐색 (depth 2)", "MATCH (d:Document {api_id: $id})-[*1..2]-(n) RETURN d, n"),
]

for name, query in queries:
    start = time.time()
    with neo4j_service.get_session() as session:
        result = session.run(query, id="15002724")
        list(result)  # 전체 결과 가져오기
    elapsed = time.time() - start
    print(f"{name}: {elapsed:.3f}초")
```

### 4. 리소스 모니터링

```cypher
-- Neo4j 메모리 사용량
CALL dbms.queryJmx('org.neo4j:instance=kernel#0,name=Memory Pool*')
YIELD attributes
RETURN attributes;

-- 활성 쿼리 목록
CALL dbms.listQueries()
YIELD queryId, query, elapsedTimeMillis
RETURN queryId, query, elapsedTimeMillis
ORDER BY elapsedTimeMillis DESC;
```

---

## 모범 사례 요약

### ✅ DO (권장사항)

1. **인덱스 활용**: 자주 검색하는 속성에 인덱스 생성
2. **파라미터 사용**: 쿼리에 파라미터를 사용하여 계획 캐싱
3. **경로 길이 제한**: 변수 길이 경로는 최대 깊이 설정
4. **조기 필터링**: WHERE 절을 MATCH 패턴에 포함
5. **캐시 활용**: 자주 조회되는 결과는 Redis 캐시 사용
6. **프로파일링**: PROFILE로 쿼리 성능 분석

### ❌ DON'T (피해야 할 사항)

1. **무한 경로 탐색**: `MATCH (a)-[*]-(b)` 사용 금지
2. **과도한 DISTINCT**: 불필요한 DISTINCT 사용 자제
3. **문자열 연결**: 쿼리에 직접 값 삽입 금지
4. **대규모 COLLECT**: 큰 리스트 수집 시 메모리 주의
5. **인덱스 무시**: 인덱스 컬럼을 함수로 감싸지 않기
6. **과도한 JOIN**: 너무 많은 MATCH 패턴 연결 자제

---

## 참고 자료

- [Neo4j Cypher 공식 문서](https://neo4j.com/docs/cypher-manual/current/)
- [Neo4j Performance Tuning](https://neo4j.com/docs/operations-manual/current/performance/)
- [Graph Algorithms](https://neo4j.com/docs/graph-data-science/current/)
- NARA Service 코드베이스:
  - `backend/app/services/neo4j_service.py`
  - `backend/app/services/advanced_query_service.py`
  - `backend/app/services/insight_engine.py`

---

**작성일**: 2025-12-23
**버전**: 1.0
**작성자**: NARA Development Team

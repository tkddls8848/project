# Advanced Query Service 사용 가이드

## 📚 목차
1. [시작하기](#시작하기)
2. [기본 사용법](#기본-사용법)
3. [고급 활용 예시](#고급-활용-예시)
4. [API 통합](#api-통합)
5. [성능 최적화 팁](#성능-최적화-팁)

---

## 시작하기

### 설치 및 초기화

```python
from app.services.neo4j_service import neo4j_service
from app.services.advanced_query_service import AdvancedQueryService

# 서비스 초기화
advanced_service = AdvancedQueryService(neo4j_service)
```

### 인덱스 생성 (최초 1회)

```python
# Neo4j 인덱스 생성 (성능 향상)
neo4j_service.initialize_indexes()
```

---

## 기본 사용법

### 1. 복잡한 검색 쿼리

```python
# 예시: "교육" 관련 문서를 사회복지 카테고리에서 검색
result = advanced_service.search_documents_advanced(
    filters=[
        {"field": "title", "operator": "contains", "value": "교육"}
    ],
    relationship_filters=[
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
    limit=20
)

print(f"검색 결과: {result['total']}개")
for doc in result["documents"]:
    print(f"- {doc['title']}")
```

### 2. 강한 관계만 필터링

```python
# 특정 문서의 강한 연결만 조회 (strength >= 0.7)
connections = advanced_service.find_strong_connections(
    doc_id="15002724",
    min_strength=0.7,
    limit=10
)

for conn in connections["connections"]:
    target = conn["target_doc"]
    rel = conn["relationship"]
    print(f"{target['title']} - 강도: {rel['strength']}")
```

### 3. 패턴 매칭

```python
# 삼각 관계 패턴 찾기
triangles = advanced_service.find_triangular_relationships(
    doc_id="15002724",
    limit=10
)

for triangle in triangles["triangles"]:
    print(triangle["insight"])
```

### 4. 시계열 분석

```python
# 최근 30일간 관계 생성 트렌드
trends = advanced_service.analyze_temporal_patterns(
    time_window_days=30,
    group_by="week"
)

print(trends["insights"])
```

---

## 고급 활용 예시

### 예시 1: 주제별 문서 클러스터 발견

```python
from app.services.insight_engine import InsightEngine

# 1. 커뮤니티 탐지
insight_engine = InsightEngine(neo4j_service)
communities = insight_engine.detect_communities(min_size=3)

# 2. 각 커뮤니티의 핵심 문서 찾기
for community in communities["communities"][:3]:
    print(f"\n커뮤니티 {community['community_id']}")
    print(f"크기: {community['size']}, 카테고리: {community['dominant_category']}")

    # 공통 이웃 분석
    doc_ids = [node["id"] for node in community["nodes"]]
    common = advanced_service.find_common_neighbors(
        doc_ids=doc_ids,
        min_common=2
    )

    print(f"공통 키워드/카테고리: {len(common['common_neighbors'])}개")
```

### 예시 2: 관련 문서 추천 시스템

```python
def recommend_related_documents(doc_id, max_recommendations=5):
    """
    특정 문서와 관련된 문서 추천
    """
    recommendations = []

    # 1. 강한 직접 연결
    strong_conns = advanced_service.find_strong_connections(
        doc_id=doc_id,
        min_strength=0.6,
        limit=3
    )

    for conn in strong_conns["connections"]:
        recommendations.append({
            "doc": conn["target_doc"],
            "reason": f"강한 연결 ({conn['relationship']['custom_type']})",
            "score": conn["relationship"]["strength"]
        })

    # 2. 공통 키워드 기반 (Neo4j 서비스 활용)
    suggestions = neo4j_service.suggest_relationships(
        doc_id=doc_id,
        limit=5
    )

    for sugg in suggestions["suggestions"][:2]:
        recommendations.append({
            "doc": sugg["target_doc"],
            "reason": sugg["reason"],
            "score": sugg["confidence"]
        })

    # 점수 순으로 정렬
    recommendations.sort(key=lambda x: x["score"], reverse=True)

    return recommendations[:max_recommendations]


# 사용
recommendations = recommend_related_documents("15002724")
for rec in recommendations:
    print(f"- {rec['doc']['title']}")
    print(f"  이유: {rec['reason']} (점수: {rec['score']:.2f})")
```

### 예시 3: 데이터 갭 분석

```python
def analyze_data_gaps(category):
    """
    특정 카테고리의 데이터 커버리지 분석
    """
    # 1. 카테고리 문서 조회
    docs = advanced_service.search_documents_advanced(
        relationship_filters=[
            {
                "rel_type": "BELONGS_TO",
                "target_label": "Category",
                "target_field": "name",
                "operator": "eq",
                "value": category
            }
        ],
        limit=100
    )

    print(f"{category} 카테고리: {docs['total']}개 문서")

    # 2. 커버된 키워드 분석
    all_keywords = set()
    for doc in docs["documents"]:
        # 각 문서의 키워드 조회 (별도 쿼리 필요)
        pass

    # 3. 보완 데이터 추천
    insight_engine = InsightEngine(neo4j_service)

    if docs["documents"]:
        sample_doc_id = docs["documents"][0]["id"]
        complementary = insight_engine.suggest_complementary_data(
            doc_id=sample_doc_id,
            limit=10
        )

        print(f"\n보완 추천: {complementary['total']}개")
        for rec in complementary["recommendations"]:
            print(f"- {rec['title']} (관련성: {rec['relevance_score']:.2f})")


# 사용
analyze_data_gaps("사회복지")
```

### 예시 4: 시계열 트렌드 대시보드

```python
def generate_trends_dashboard(days=30):
    """
    관계 생성 트렌드 대시보드 데이터 생성
    """
    # 일별 트렌드
    daily_trends = advanced_service.analyze_temporal_patterns(
        time_window_days=days,
        group_by="day"
    )

    # 주별 트렌드
    weekly_trends = advanced_service.analyze_temporal_patterns(
        time_window_days=days,
        group_by="week"
    )

    # 전체 통계
    stats = advanced_service.get_relationship_statistics()

    dashboard = {
        "period": f"최근 {days}일",
        "insights": daily_trends["insights"],
        "daily_timeline": daily_trends["timeline"],
        "weekly_timeline": weekly_trends["timeline"],
        "total_stats": stats
    }

    return dashboard


# 사용
dashboard = generate_trends_dashboard(30)
print(dashboard["insights"])

# 일별 데이터 출력
for day in dashboard["daily_timeline"][-7:]:  # 최근 7일
    print(f"{day['period']}: {day['relationship_count']}개 관계 생성")
```

### 예시 5: 경로 기반 연관성 분석

```python
def analyze_document_relationship_path(source_id, target_id):
    """
    두 문서 간 연결 경로 상세 분석
    """
    # 모든 경로 찾기
    paths = advanced_service.find_all_paths(
        source_id=source_id,
        target_id=target_id,
        max_depth=4,
        limit=10
    )

    if paths["total"] == 0:
        print("두 문서 간 연결 경로가 없습니다.")
        return

    print(f"발견된 경로: {paths['total']}개\n")

    # 최단 경로
    shortest = paths["paths"][0]
    print(f"최단 경로 (길이: {shortest['length']}):")

    for i, node in enumerate(shortest["nodes"]):
        print(f"  {i+1}. {node.get('title', node.get('id'))}")
        if i < len(shortest["relationships"]):
            rel = shortest["relationships"][i]
            rel_label = rel.get("custom_type") or rel["type"]
            print(f"     ↓ {rel_label}")

    # 경로 패턴 분석
    path_patterns = {}
    for path in paths["paths"]:
        pattern_key = tuple(r["type"] for r in path["relationships"])
        path_patterns[pattern_key] = path_patterns.get(pattern_key, 0) + 1

    print(f"\n경로 패턴:")
    for pattern, count in sorted(path_patterns.items(), key=lambda x: x[1], reverse=True):
        print(f"  {' → '.join(pattern)}: {count}개")


# 사용
analyze_document_relationship_path("15002724", "15002731")
```

---

## API 통합

### FastAPI 라우터 예시

```python
from fastapi import APIRouter, HTTPException, Depends
from app.services.advanced_query_service import AdvancedQueryService
from app.services.neo4j_service import neo4j_service
from app.auth import verify_api_key

router = APIRouter(prefix="/advanced", tags=["advanced-queries"])
advanced_service = AdvancedQueryService(neo4j_service)


@router.post("/search")
async def advanced_search(
    filters: list,
    relationship_filters: list = None,
    sort_by: str = "created_at",
    limit: int = 20,
    _: bool = Depends(verify_api_key)
):
    """고급 문서 검색"""
    try:
        result = advanced_service.search_documents_advanced(
            filters=filters,
            relationship_filters=relationship_filters,
            sort_by=sort_by,
            limit=limit
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strong-connections/{doc_id}")
async def get_strong_connections(
    doc_id: str,
    min_strength: float = 0.5,
    limit: int = 20,
    _: bool = Depends(verify_api_key)
):
    """강한 연결 조회"""
    try:
        result = advanced_service.find_strong_connections(
            doc_id=doc_id,
            min_strength=min_strength,
            limit=limit
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temporal-trends")
async def get_temporal_trends(
    days: int = 30,
    group_by: str = "week",
    _: bool = Depends(verify_api_key)
):
    """시계열 트렌드 조회"""
    try:
        result = advanced_service.analyze_temporal_patterns(
            time_window_days=days,
            group_by=group_by
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 성능 최적화 팁

### 1. 인덱스 활용

```python
# 인덱스가 생성되었는지 확인
from app.services.neo4j_indexes import list_neo4j_indexes

indexes_info = list_neo4j_indexes(neo4j_service._driver)
print(f"인덱스: {len(indexes_info['indexes'])}개")
print(f"제약조건: {len(indexes_info['constraints'])}개")
```

### 2. 쿼리 프로파일링

```python
from app.services.neo4j_indexes import Neo4jIndexManager

manager = Neo4jIndexManager(neo4j_service._driver)

# 쿼리 성능 분석
query = "MATCH (d:Document {api_id: '15002724'})-[:HAS_KEYWORD]->(k:Keyword) RETURN d, k"
profile = manager.analyze_query_performance(query)

if profile:
    print(f"DB Hits: {profile.db_hits}")
```

### 3. 캐시 활용

```python
# 자주 조회되는 결과는 캐시됨
# explore_graph, suggest_relationships, get_graph_summary 등은 자동 캐시

# 캐시 무효화가 필요한 경우 (관계 생성/수정/삭제 시 자동 처리됨)
neo4j_service._invalidate_graph_cache("doc_id_1", "doc_id_2")
```

### 4. 페이지네이션

```python
# 대량 결과 조회 시 페이지네이션 사용
page_size = 50
offset = 0

while True:
    result = advanced_service.search_documents_advanced(
        filters=[...],
        limit=page_size,
        offset=offset
    )

    # 결과 처리
    process_documents(result["documents"])

    # 다음 페이지
    if len(result["documents"]) < page_size:
        break

    offset += page_size
```

### 5. 경로 탐색 깊이 제한

```python
# 성능을 위해 경로 길이를 제한
paths = advanced_service.find_all_paths(
    source_id="15002724",
    target_id="15002731",
    max_depth=3,  # 너무 깊지 않게 (권장: 3-4)
    limit=10
)
```

---

## 주의사항

1. **변수 길이 경로 쿼리**: 최대 깊이를 반드시 설정하세요 (무한 탐색 방지)
2. **관계 강도 필터링**: strength가 NULL인 관계는 자동 제외됩니다
3. **시계열 분석**: created_at이 없는 관계는 결과에 포함되지 않습니다
4. **페이지네이션**: 대량 결과 조회 시 반드시 limit 설정
5. **인덱스**: 성능 최적화를 위해 인덱스를 활성화하세요

---

## 문제 해결

### Q: 쿼리가 너무 느립니다

A: 다음을 확인하세요:
- 인덱스가 생성되었는지 확인
- EXPLAIN/PROFILE로 쿼리 계획 확인
- 경로 탐색 깊이 줄이기
- LIMIT 추가

### Q: 결과가 비어있습니다

A: 다음을 확인하세요:
- 필터 조건이 너무 엄격하지 않은지
- 데이터가 실제로 존재하는지
- 관계 타입/노드 라벨이 정확한지

### Q: 메모리 부족 에러

A: 다음을 시도하세요:
- LIMIT 줄이기
- 경로 탐색 깊이 줄이기
- 페이지네이션 사용
- Neo4j 메모리 설정 증가

---

**작성일**: 2025-12-23
**버전**: 1.0

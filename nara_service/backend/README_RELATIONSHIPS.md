# Neo4j 자동 관계 설정 가이드

## 개요

`relationship_config.py` 파일은 문서 적재 시 자동으로 생성되는 Neo4j 관계를 정의합니다.
이 파일을 수정하여 새로운 관계를 추가하거나 기존 관계를 변경할 수 있습니다.

## 현재 정의된 자동 관계

| 관계 이름 | 관계 타입 | 타겟 노드 | 데이터 경로 | 설명 |
|---------|---------|---------|-----------|------|
| provider | PROVIDED_BY | Provider | metadata.provider | 문서 제공 기관 |
| category | BELONGS_TO | Category | metadata.category | 문서 카테고리 |
| keywords | HAS_KEYWORD | Keyword | metadata.keywords | 문서 키워드 (리스트) |

## 구조 설명

### AutoRelationship 클래스 파라미터

```python
AutoRelationship(
    name="관계_이름",              # 식별용 이름 (고유해야 함)
    description="관계 설명",       # 사람이 읽을 수 있는 설명
    relationship_type="RELATION",  # Neo4j 관계 타입 (대문자 권장)
    target_node_label="NodeLabel", # 타겟 노드 라벨
    target_property="property",    # 타겟 노드의 키 속성
    source_data_path="path.to.value",  # 소스 데이터 경로 (점 표기법)
    is_list=False,                # 리스트 타입 여부
)
```

## 새로운 관계 추가 방법

### 1. 단일 값 관계 추가 예시

문서에 지역(region) 정보가 있고 이를 그래프에 연결하려면:

```python
# relationship_config.py의 AUTO_RELATIONSHIPS에 추가

AUTO_RELATIONSHIPS.append(
    AutoRelationship(
        name="region",
        description="문서 지역 관계",
        relationship_type="LOCATED_IN",
        target_node_label="Region",
        target_property="name",
        source_data_path="metadata.region",
        is_list=False
    )
)
```

**예상 결과:**
```cypher
(Document)-[:LOCATED_IN]->(Region {name: "경상북도"})
```

### 2. 리스트 값 관계 추가 예시

문서에 여러 태그가 있고 각각 연결하려면:

```python
AUTO_RELATIONSHIPS.append(
    AutoRelationship(
        name="tags",
        description="문서 태그 관계",
        relationship_type="TAGGED_WITH",
        target_node_label="Tag",
        target_property="name",
        source_data_path="metadata.tags",
        is_list=True  # 리스트 처리
    )
)
```

**예상 결과:**
```cypher
(Document)-[:TAGGED_WITH]->(Tag {name: "공공데이터"})
(Document)-[:TAGGED_WITH]->(Tag {name: "오픈API"})
(Document)-[:TAGGED_WITH]->(Tag {name: "공공기관"})
```

### 3. 중첩된 데이터 경로 사용

문서 구조가 깊게 중첩되어 있다면:

```python
# 데이터 구조:
{
  "metadata": {
    "extended": {
      "geographic": {
        "city": "울진군"
      }
    }
  }
}

# 관계 정의:
AutoRelationship(
    name="city",
    description="문서 도시 관계",
    relationship_type="IN_CITY",
    target_node_label="City",
    target_property="name",
    source_data_path="metadata.extended.geographic.city",
    is_list=False
)
```

## 주의사항

### 1. graph_schema.py와 동기화

새로운 관계 타입을 추가할 때는 `graph_schema.py`에도 정의하는 것이 좋습니다:

```python
# graph_schema.py
class RelationType:
    # 기존 관계
    HAS_KEYWORD = "HAS_KEYWORD"
    PROVIDED_BY = "PROVIDED_BY"
    BELONGS_TO = "BELONGS_TO"

    # 새로 추가
    LOCATED_IN = "LOCATED_IN"
    TAGGED_WITH = "TAGGED_WITH"
```

### 2. 데이터 누락 처리

- 단일 값 관계: 데이터가 없으면 `"Unknown"` 기본값 사용
- 리스트 관계: 데이터가 없으면 `[]` 빈 리스트 사용

### 3. 성능 고려사항

- 관계가 많을수록 쿼리 실행 시간이 증가합니다
- 불필요한 관계는 추가하지 않는 것이 좋습니다
- 인덱스 생성을 고려하세요 (Neo4j 제약 조건 참고)

## 테스트 방법

변경 후 테스트 스크립트 실행:

```bash
cd backend
python scripts/test_relationship_config.py
```

## 생성된 Cypher 쿼리 확인

현재 설정으로 생성되는 전체 Cypher 쿼리를 확인하려면:

```python
from app.core.relationship_config import generate_full_cypher_query

query = generate_full_cypher_query()
print(query)
```

## 실제 적용

설정 변경 후:
1. 백엔드 재시작
2. 새로 적재되는 문서부터 새 관계 적용
3. 기존 문서는 재적재 필요 (또는 별도 마이그레이션 스크립트 작성)

## 문제 해결

### 관계가 생성되지 않는 경우

1. 데이터 경로가 정확한지 확인
2. 로그에서 에러 메시지 확인: `neo4j_service.py:88`
3. Neo4j 브라우저에서 직접 쿼리 테스트

### 데이터 타입 불일치

```python
# 잘못된 예: 리스트인데 is_list=False
source_data_path="metadata.keywords"  # ["키워드1", "키워드2"]
is_list=False  # 단일 값으로 처리하려 함 -> 오류

# 올바른 예:
is_list=True  # 리스트로 처리
```

## 고급 사용법

### 조건부 관계 생성

특정 조건에서만 관계를 생성하려면 `upsert_document` 함수를 직접 수정하거나,
새로운 메서드를 추가하여 처리할 수 있습니다.

### 관계 속성 추가

현재는 관계에 속성이 없지만, 필요하다면 `AutoRelationship` 클래스를 확장하여
관계에 속성을 추가할 수 있습니다 (예: 관계 생성 시간, 신뢰도 등).

## 참고 자료

- Neo4j Cypher 쿼리: https://neo4j.com/docs/cypher-manual/current/
- 그래프 모델링 모범 사례: https://neo4j.com/developer/guide-data-modeling/

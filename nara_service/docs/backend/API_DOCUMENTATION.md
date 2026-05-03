# Advanced Query API Documentation

## 개요

Advanced Query API는 Neo4j 그래프 데이터베이스에 대한 고급 쿼리 기능을 제공합니다.

**Base URL**: `/api/advanced`

**Architecture**: Clean Architecture 기반으로 리팩토링됨
- Domain Layer: 순수 함수 (쿼리 빌더)
- Application Layer: 비즈니스 로직 (서비스)
- Infrastructure Layer: I/O (Neo4j 실행기)
- Presentation Layer: HTTP API (FastAPI)

---

## 인증

현재 버전에서는 인증이 필요하지 않습니다. (추후 추가 예정)

---

## API 엔드포인트

### 1. 검색 (Search)

#### POST /api/advanced/search

복잡한 다중 조건으로 문서를 검색합니다.

**Request Body**:
```json
{
  "filters": [
    {
      "field": "title",
      "operator": "contains",
      "value": "교육"
    },
    {
      "field": "status",
      "operator": "eq",
      "value": "active"
    }
  ],
  "relationship_filters": [
    {
      "rel_type": "BELONGS_TO",
      "target_label": "Category",
      "target_field": "name",
      "operator": "eq",
      "value": "교육"
    }
  ],
  "sort_by": "created_at",
  "sort_order": "DESC",
  "limit": 50,
  "offset": 0
}
```

**Parameters**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filters` | array | No | 노드 속성 필터 목록 |
| `filters[].field` | string | Yes | 필터링할 필드명 |
| `filters[].operator` | enum | Yes | 연산자 (eq, ne, contains, in, not_in, gt, lt, gte, lte) |
| `filters[].value` | any | Yes | 비교 값 |
| `relationship_filters` | array | No | 관계 필터 목록 |
| `relationship_filters[].rel_type` | string | Yes | 관계 타입 |
| `relationship_filters[].target_label` | string | Yes | 대상 노드 라벨 |
| `relationship_filters[].target_field` | string | Yes | 대상 필드명 |
| `relationship_filters[].operator` | enum | Yes | 연산자 |
| `relationship_filters[].value` | any | Yes | 비교 값 |
| `sort_by` | string | No | 정렬 기준 필드 (기본값: "created_at") |
| `sort_order` | enum | No | 정렬 순서 (ASC, DESC, 기본값: "DESC") |
| `limit` | integer | No | 최대 결과 개수 (1-500, 기본값: 50) |
| `offset` | integer | No | 페이지네이션 오프셋 (기본값: 0) |

**Response** (200 OK):
```json
{
  "documents": [
    {
      "id": "15001001",
      "title": "교육 지원 사업",
      "description": "초중고 학생 대상 교육 지원",
      "url": "https://example.com/api/15001001",
      "created_at": "2024-01-15T10:30:00",
      "updated_at": "2024-01-20T15:45:00",
      "provider": "교육부",
      "category": "교육",
      "keywords": ["교육", "학생", "지원"],
      "properties": {}
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

**Error Responses**:
- `400 Bad Request`: 유효하지 않은 필터 또는 파라미터
- `500 Internal Server Error`: 서버 오류
- `503 Service Unavailable`: Neo4j 연결 실패

**Example**:
```bash
curl -X POST "http://localhost:8000/api/advanced/search" \
  -H "Content-Type: application/json" \
  -d '{
    "filters": [
      {"field": "title", "operator": "contains", "value": "교육"}
    ],
    "limit": 10
  }'
```

---

### 2. 관계 분석 (Relationship Analysis)

#### GET /api/advanced/relationships/strong-connections/{doc_id}

특정 문서와 강한 연결을 가진 문서들을 찾습니다.

**Path Parameters**:
- `doc_id` (string, required): 기준 문서 ID

**Query Parameters**:
- `min_strength` (float, optional): 최소 관계 강도 (0.0-1.0, 기본값: 0.5)
- `relationship_types` (array[string], optional): 특정 관계 타입 필터
- `limit` (integer, optional): 최대 결과 개수 (1-100, 기본값: 20)

**Response** (200 OK):
```json
{
  "doc_id": "15001001",
  "connections": [
    {
      "target_id": "15001002",
      "target_title": "관련 교육 사업",
      "target_description": "...",
      "relationship_type": "RELATED_TO",
      "custom_type": "similar_topic",
      "strength": 0.85,
      "rel_description": "유사한 주제"
    }
  ],
  "total": 5
}
```

**Example**:
```bash
curl "http://localhost:8000/api/advanced/relationships/strong-connections/15001001?min_strength=0.7&limit=10"
```

---

### 3. 패턴 매칭 (Pattern Matching)

#### GET /api/advanced/patterns/triangular

삼각형 관계 패턴을 찾습니다 (A→B→C→A).

**Query Parameters**:
- `relationship_type` (string, required): 관계 타입
- `limit` (integer, optional): 최대 결과 개수 (1-100, 기본값: 20)

**Response** (200 OK):
```json
[
  {
    "doc1_id": "15001001",
    "doc1_title": "문서 A",
    "doc2_id": "15001002",
    "doc2_title": "문서 B",
    "doc3_id": "15001003",
    "doc3_title": "문서 C",
    "rel1_type": "RELATED_TO",
    "rel2_type": "RELATED_TO",
    "rel3_type": "RELATED_TO"
  }
]
```

**Example**:
```bash
curl "http://localhost:8000/api/advanced/patterns/triangular?relationship_type=RELATED_TO&limit=10"
```

---

#### GET /api/advanced/patterns/common-neighbors

두 문서 사이의 공통 이웃을 찾습니다.

**Query Parameters**:
- `doc_id1` (string, required): 첫 번째 문서 ID
- `doc_id2` (string, required): 두 번째 문서 ID
- `relationship_type` (string, optional): 관계 타입 (기본값: "RELATED_TO")
- `limit` (integer, optional): 최대 결과 개수 (1-100, 기본값: 20)

**Response** (200 OK):
```json
[
  {
    "neighbor_id": "15001003",
    "neighbor_title": "공통 관련 문서",
    "neighbor_description": "...",
    "common_count": 2
  }
]
```

**Example**:
```bash
curl "http://localhost:8000/api/advanced/patterns/common-neighbors?doc_id1=15001001&doc_id2=15001002"
```

---

### 4. 시계열 분석 (Temporal Analysis)

#### GET /api/advanced/temporal/patterns

시간에 따른 문서 생성 및 관계 패턴을 분석합니다.

**Query Parameters**:
- `time_window_days` (integer, optional): 분석 기간 (일 단위, 1-365, 기본값: 30)
- `bucket_size_days` (integer, optional): 버킷 크기 (1-30, 기본값: 7)
- `relationship_type` (string, optional): 관계 타입 (기본값: "RELATED_TO")

**Response** (200 OK):
```json
[
  {
    "time_bucket": "2024-01-15",
    "document_count": 42,
    "relationship_count": 156,
    "avg_strength": 0.72
  }
]
```

**Example**:
```bash
curl "http://localhost:8000/api/advanced/temporal/patterns?time_window_days=60&bucket_size_days=7"
```

---

### 5. 경로 탐색 (Path Finding)

#### GET /api/advanced/paths/find

두 문서 사이의 모든 경로를 찾습니다.

**Query Parameters**:
- `source_id` (string, required): 시작 문서 ID
- `target_id` (string, required): 도착 문서 ID
- `max_depth` (integer, optional): 최대 경로 길이 (1-10, 기본값: 4)
- `relationship_types` (array[string], optional): 관계 타입 필터
- `limit` (integer, optional): 최대 경로 개수 (1-50, 기본값: 10)

**Response** (200 OK):
```json
[
  {
    "nodes": [
      {
        "id": "15001001",
        "title": "문서 A",
        "label": "Document"
      },
      {
        "id": "15001002",
        "title": "문서 B",
        "label": "Document"
      }
    ],
    "length": 1,
    "relationships": ["RELATED_TO"]
  }
]
```

**Example**:
```bash
curl "http://localhost:8000/api/advanced/paths/find?source_id=15001001&target_id=15001005&max_depth=3"
```

---

### 6. 통계 및 집계 (Statistics & Aggregation)

#### GET /api/advanced/stats/relationships/{doc_id}

문서의 관계를 타입별로 집계합니다.

**Path Parameters**:
- `doc_id` (string, required): 문서 ID

**Response** (200 OK):
```json
[
  {
    "relationship_type": "HAS_KEYWORD",
    "count": 15,
    "avg_strength": 0.68,
    "min_strength": 0.45,
    "max_strength": 0.92
  }
]
```

**Example**:
```bash
curl "http://localhost:8000/api/advanced/stats/relationships/15001001"
```

---

#### GET /api/advanced/stats/aggregate

특정 필드로 문서를 집계합니다.

**Query Parameters**:
- `group_by_field` (string, required): 그룹화 필드 (예: "category", "provider")
- `limit` (integer, optional): 최대 그룹 개수 (1-200, 기본값: 50)

**Response** (200 OK):
```json
[
  {
    "group_key": "category",
    "group_value": "교육",
    "document_count": 142,
    "total_relationships": 523
  }
]
```

**Example**:
```bash
curl "http://localhost:8000/api/advanced/stats/aggregate?group_by_field=category&limit=20"
```

---

## 데이터 모델

### FilterOperator (Enum)

필터 연산자:
- `eq`: 같음 (=)
- `ne`: 같지 않음 (≠)
- `contains`: 포함 (CONTAINS)
- `in`: 포함됨 (IN)
- `not_in`: 포함되지 않음 (NOT IN)
- `gt`: 크다 (>)
- `lt`: 작다 (<)
- `gte`: 크거나 같다 (≥)
- `lte`: 작거나 같다 (≤)

### NodeFilter

노드 속성 필터:
```typescript
{
  field: string;          // 필드명
  operator: FilterOperator;  // 연산자
  value: string | number | string[];  // 비교 값
}
```

### RelationshipFilter

관계 필터:
```typescript
{
  rel_type: string;       // 관계 타입
  target_label: string;   // 대상 노드 라벨
  target_field: string;   // 대상 필드명
  operator: FilterOperator;  // 연산자
  value: string | string[];  // 비교 값
}
```

---

## 에러 처리

모든 엔드포인트는 Result Pattern을 사용하여 에러를 처리합니다.

### 에러 응답 형식

```json
{
  "detail": "Error message here"
}
```

### HTTP 상태 코드

- `200 OK`: 성공
- `400 Bad Request`: 유효하지 않은 요청
- `404 Not Found`: 리소스를 찾을 수 없음
- `500 Internal Server Error`: 서버 내부 오류
- `503 Service Unavailable`: Neo4j 연결 실패

### 에러 코드 매핑

| ErrorCode | HTTP Status |
|-----------|-------------|
| `VALIDATION_ERROR` | 400 |
| `NOT_FOUND` | 404 |
| `NEO4J_CONNECTION_ERROR` | 503 |
| `NEO4J_QUERY_ERROR` | 500 |
| `UNKNOWN_ERROR` | 500 |

---

## 성능 고려사항

### 페이지네이션

- 기본 limit: 50
- 최대 limit: 500 (검색), 100 (관계/패턴), 50 (경로)
- offset 기반 페이지네이션 사용

### 쿼리 최적화

- 모든 쿼리는 파라미터화되어 쿼리 플랜 캐싱 가능
- Neo4j 인덱스 활용 (api_id, created_at 등)
- 깊이 제한 (경로 탐색: 최대 10 hop)

### 타임아웃

- 기본 타임아웃: 30초
- 복잡한 쿼리의 경우 조정 가능

---

## 사용 예시

### Python (requests)

```python
import requests

# 검색
response = requests.post(
    "http://localhost:8000/api/advanced/search",
    json={
        "filters": [
            {"field": "title", "operator": "contains", "value": "교육"}
        ],
        "limit": 10
    }
)

result = response.json()
print(f"Found {result['total']} documents")
for doc in result['documents']:
    print(f"- {doc['title']}")
```

### JavaScript (fetch)

```javascript
// 강한 연결 찾기
const response = await fetch(
  'http://localhost:8000/api/advanced/relationships/strong-connections/15001001?min_strength=0.7'
);

const result = await response.json();
console.log(`Found ${result.total} connections`);
result.connections.forEach(conn => {
  console.log(`- ${conn.target_title} (strength: ${conn.strength})`);
});
```

### cURL

```bash
# 공통 이웃 찾기
curl -G "http://localhost:8000/api/advanced/patterns/common-neighbors" \
  --data-urlencode "doc_id1=15001001" \
  --data-urlencode "doc_id2=15001002" \
  --data-urlencode "relationship_type=RELATED_TO"
```

---

## 변경 이력

### Version 2.0 (2024-12-25)
- Clean Architecture로 완전 리팩토링
- Result Pattern 도입
- Pydantic 모델로 타입 안전성 확보
- 순수 함수 기반 쿼리 빌더
- 새로운 API 엔드포인트 구조

### Version 1.0
- 초기 구현 (advanced_query_service.py)
- 단일 클래스 구조 (900+ 라인)

---

## 관련 문서

- [아키텍처 문서](./ARCHITECTURE.md)
- [리팩토링 계획](../plans/01/REFACTORING_PLAN.md)
- [CODING_RULES](../CODING_RULES.md)

---

**작성일**: 2024-12-25
**버전**: 2.0
**API Base URL**: `/api/advanced`

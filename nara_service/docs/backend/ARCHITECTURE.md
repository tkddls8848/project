# Advanced Query Service Architecture

## 목차
1. [개요](#개요)
2. [아키텍처 원칙](#아키텍처-원칙)
3. [레이어 구조](#레이어-구조)
4. [디렉토리 구조](#디렉토리-구조)
5. [데이터 흐름](#데이터-흐름)
6. [설계 결정사항](#설계-결정사항)
7. [CODING_RULES 준수](#coding_rules-준수)

---

## 개요

Advanced Query Service는 Clean Architecture 원칙에 따라 설계된 Neo4j 그래프 데이터베이스 쿼리 시스템입니다.

### 핵심 목표

1. **레이어 분리**: 비즈니스 로직을 I/O에서 분리
2. **타입 안전성**: Pydantic 모델로 런타임 검증
3. **테스트 용이성**: 순수 함수 기반 설계
4. **유지보수성**: 단일 책임 원칙 (SRP)
5. **확장성**: 독립적인 서비스 모듈

### 주요 개선사항

기존 설계:
```
AdvancedQueryService (900+ lines)
├── 쿼리 빌드 + 실행 + 파싱 혼재
├── Dict[str, Any] 타입 (타입 안전성 낮음)
└── 7가지 책임 (SRP 위반)
```

새로운 설계:
```
Domain (순수 함수)
├── Application (유스케이스)
├── Infrastructure (I/O)
└── Presentation (HTTP)
```

---

## 아키텍처 원칙

### 1. Clean Architecture

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│         (FastAPI Routers)               │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Application Layer               │
│         (Services)                      │
│  - DocumentSearchService                │
│  - RelationshipQueryService             │
│  - PatternQueryService                  │
└──────────────┬──────────────────────────┘
               │ uses
┌──────────────▼──────────────────────────┐
│         Domain Layer                    │
│         (Pure Functions)                │
│  - CypherFilterBuilder                  │
│  - CypherMatchBuilder                   │
│  - Pydantic Models                      │
└──────────────┬──────────────────────────┘
               │ uses
┌──────────────▼──────────────────────────┐
│         Infrastructure Layer            │
│         (I/O)                           │
│  - Neo4jQueryExecutor                   │
└─────────────────────────────────────────┘
```

### 2. Dependency Rule

**의존성은 항상 안쪽(Domain)을 향함**

- ✅ Application → Domain
- ✅ Infrastructure → Domain
- ✅ Presentation → Application
- ❌ Domain → Infrastructure (금지)
- ❌ Domain → Application (금지)

### 3. FP First (Functional Programming First)

**순수 함수 우선 원칙**

```python
# ✅ Good: Pure function (Domain Layer)
def build_filter_clause(filter_spec, node_alias, param_prefix):
    # Input → Output, no side effects
    clause = f"{node_alias}.{filter_spec.field} = ${param_prefix}"
    params = {param_prefix: filter_spec.value}
    return clause, params

# ❌ Bad: Side effect mixed with logic
def build_and_execute_filter(filter_spec):
    clause = ...  # Pure logic
    result = neo4j.run(clause)  # Side effect!
    return result
```

### 4. Result Pattern

**예외 대신 명시적 성공/실패 표현**

```python
# ✅ Good: Result Pattern
def search(query_spec):
    try:
        result = execute_query(...)
        return QueryResult.ok(result)
    except Neo4jError as e:
        return QueryResult.fail(str(e), ErrorCode.NEO4J_ERROR)

# ❌ Bad: Exception propagation
def search(query_spec):
    result = execute_query(...)  # Throws exception
    return result
```

---

## 레이어 구조

### 1. Domain Layer

**책임**: 비즈니스 규칙 및 순수 함수

**특징**:
- 외부 의존성 없음
- 모든 함수는 순수 함수
- I/O 없음, 전역 상태 변경 없음
- 쉽게 테스트 가능

**구성 요소**:

#### 1.1 Models (Pydantic)

```python
# app/domain/query/models/filters.py

class NodeFilter(BaseModel):
    """타입 안전 필터 모델"""
    field: str
    operator: FilterOperator
    value: Union[str, int, float, List[str]]

    @validator("field")
    def validate_field(cls, v):
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v
```

**설계 결정**:
- Pydantic 사용: 런타임 검증 + IDE 자동완성
- Enum 사용: 타입 안전한 연산자
- Validator: 경계에서 검증

#### 1.2 Builders (Pure Functions)

```python
# app/domain/query/builders/filter_builder.py

class CypherFilterBuilder:
    """순수 함수만 포함하는 정적 클래스"""

    @staticmethod
    def build_node_filter(
        filter_spec: NodeFilter,
        node_alias: str,
        param_prefix: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        순수 함수: 입력만으로 출력 결정

        Design Decision:
        - Static method: 상태 없음
        - Parameterized query: SQL injection 방지
        - Lambda for operators: 지연 평가
        """
        # ... pure implementation
```

**설계 결정**:
- Static methods only: 숨겨진 상태 없음
- 파라미터화: Cypher injection 방지
- DRY: 중복 제거 (operator mapping)

#### 1.3 Result Pattern

```python
# app/domain/query/models/result.py

class QueryResult(BaseModel, Generic[T]):
    """성공/실패 명시적 표현"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[ErrorCode] = None

    @staticmethod
    def ok(data: T) -> 'QueryResult[T]':
        return QueryResult(success=True, data=data)

    @staticmethod
    def fail(error: str, code: ErrorCode) -> 'QueryResult[T]':
        return QueryResult(success=False, error=error, error_code=code)
```

**설계 결정**:
- Generic type: 타입 안전성
- Factory methods: 명시적 생성
- Pydantic: 직렬화 가능

---

### 2. Infrastructure Layer

**책임**: I/O 작업 (Neo4j, 파일, 외부 API 등)

**특징**:
- 모든 부작용(side effects)을 이 레이어에 격리
- Domain 빌더를 사용하여 쿼리 생성 (쿼리 생성 책임은 Domain)
- 오직 실행만 담당

**구성 요소**:

```python
# app/infrastructure/neo4j/query_executor.py

class Neo4jQueryExecutor:
    """Neo4j 쿼리 실행 전담"""

    def execute_read(
        self,
        query: str,  # Domain이 생성
        parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Design Decision:
        - 쿼리 생성하지 않음 (Domain의 책임)
        - 오직 실행만 담당
        - 에러 래핑 (추상화)
        """
        try:
            with self.neo4j_service.get_session() as session:
                result = session.run(query, **parameters)
                return [dict(record) for record in result]
        except Neo4jError as e:
            raise Neo4jConnectionError(str(e))
```

**설계 결정**:
- 쿼리 빌드 책임 없음 (Domain이 담당)
- 에러 래핑: Neo4j 세부사항 숨김
- 로깅: 관찰 가능성

---

### 3. Application Layer

**책임**: 유스케이스 오케스트레이션

**특징**:
- Domain 순수 함수 조합
- Infrastructure I/O 호출
- Result Pattern 반환
- 비즈니스 흐름 제어

**구성 요소**:

```python
# app/services/query/search_service.py

class DocumentSearchService:
    """문서 검색 유스케이스"""

    def __init__(self, query_executor: Neo4jQueryExecutor):
        self.executor = query_executor

    def search(self, query_spec: SearchQuery) -> QueryResult[SearchResult]:
        """
        3단계 프로세스:
        1. Domain: 쿼리 생성 (순수 함수)
        2. Infrastructure: 쿼리 실행 (I/O)
        3. Application: 결과 매핑
        """
        try:
            # Step 1: Build query (Domain)
            query, params = self._build_search_query(query_spec)

            # Step 2: Execute (Infrastructure)
            records = self.executor.execute_read(query, params)

            # Step 3: Map results (Application)
            documents = self._map_to_documents(records)

            return QueryResult.ok(SearchResult(documents=documents, ...))

        except Neo4jConnectionError as e:
            return QueryResult.fail(str(e), ErrorCode.NEO4J_CONNECTION_ERROR)
```

**설계 결정**:
- 단일 책임: 하나의 유스케이스만
- Domain 함수 조합: 순수 로직 재사용
- Result Pattern: 명시적 에러 핸들링
- 의존성 주입: 테스트 용이

**서비스 분리**:

```
services/query/
├── search_service.py         # 복잡한 검색
├── relationship_service.py   # 관계 강도 기반
├── pattern_service.py        # 패턴 매칭
├── temporal_service.py       # 시계열 분석
├── path_service.py          # 경로 탐색
└── stats_service.py         # 통계/집계
```

각 서비스: 100-200 라인, 단일 책임

---

### 4. Presentation Layer

**책임**: HTTP 요청/응답 처리

**특징**:
- FastAPI 엔드포인트
- Pydantic 자동 검증
- Dependency Injection
- Result → HTTP 상태 코드 매핑

**구성 요소**:

```python
# app/routers/advanced_queries.py

@router.post("/search")
async def advanced_search(
    query: SearchQuery,  # Pydantic 자동 검증
    search_service: DocumentSearchService = Depends(get_search_service)
):
    """
    Design Decision:
    - Dependency injection: 테스트 용이
    - Pydantic 검증: 자동 400 에러
    - Result Pattern → HTTP 매핑
    """
    result = search_service.search(query)

    if not result.success:
        # ErrorCode → HTTP status
        status_code = 500
        if result.error_code == ErrorCode.NOT_FOUND:
            status_code = 404
        elif result.error_code == ErrorCode.VALIDATION_ERROR:
            status_code = 400

        raise HTTPException(status_code=status_code, detail=result.error)

    return result.data
```

**설계 결정**:
- Dependency injection: 서비스 생성 자동화
- ErrorCode 매핑: 일관된 HTTP 응답
- 비즈니스 로직 없음: Application에 위임

---

## 디렉토리 구조

```
backend/app/
├── domain/                          # Domain Layer
│   └── query/
│       ├── models/
│       │   ├── filters.py          # Pydantic 모델
│       │   ├── result.py           # Result Pattern
│       │   └── search_result.py    # 검색 결과 모델
│       └── builders/
│           ├── filter_builder.py   # WHERE 절 빌더
│           └── match_builder.py    # MATCH 패턴 빌더
│
├── infrastructure/                  # Infrastructure Layer
│   └── neo4j/
│       └── query_executor.py       # Neo4j I/O
│
├── services/                        # Application Layer
│   └── query/
│       ├── search_service.py
│       ├── relationship_service.py
│       ├── pattern_service.py
│       ├── temporal_service.py
│       ├── path_service.py
│       └── stats_service.py
│
└── routers/                         # Presentation Layer
    └── advanced_queries.py
```

---

## 데이터 흐름

### 요청 흐름 (예: 검색)

```
1. HTTP Request
   ↓
2. FastAPI Router (Presentation)
   - Pydantic 검증
   - Dependency injection
   ↓
3. DocumentSearchService (Application)
   - Domain 빌더 호출
   - Infrastructure 실행기 호출
   - 결과 매핑
   ↓
4. CypherFilterBuilder (Domain)
   - 순수 함수로 쿼리 생성
   - 파라미터 생성
   ↓
5. Neo4jQueryExecutor (Infrastructure)
   - Neo4j 쿼리 실행
   - 에러 래핑
   ↓
6. Application Layer
   - 결과 → DocumentInfo 매핑
   - QueryResult.ok() 생성
   ↓
7. Presentation Layer
   - QueryResult → HTTP Response
   - ErrorCode → HTTP status
   ↓
8. HTTP Response
```

### 의존성 흐름

```
Presentation
    ↓ depends on
Application
    ↓ depends on
Domain (pure) ← Infrastructure uses
    ↓
  Models
```

---

## 설계 결정사항

### 1. 왜 순수 함수인가?

**문제**: 기존 코드는 쿼리 생성과 실행이 혼재되어 테스트가 어려웠음

```python
# Before: 테스트 시 Neo4j 모킹 필수
def search(self, filters):
    query = self._build_query(filters)  # Pure
    result = session.run(query)  # Side effect
    return result
```

**해결**: 순수 함수 분리

```python
# After: 쿼리 빌더는 모킹 없이 테스트 가능
@staticmethod
def build_query(filters):
    # Pure function - easy to test
    return query, params

def test_build_query():
    query, params = build_query([...])
    assert query == "MATCH ..."
    assert params == {...}
```

**이점**:
- 빠른 단위 테스트 (Neo4j 불필요)
- 예측 가능한 동작
- 병렬 처리 안전

### 2. 왜 Result Pattern인가?

**문제**: 예외 기반 흐름은 타입 시스템에서 보이지 않음

```python
# Before: 예외가 어디서 발생할지 모름
def search(query):
    result = execute(query)  # 무슨 예외가?
    return result
```

**해결**: 명시적 Result 타입

```python
# After: 성공/실패가 타입에 명시됨
def search(query) -> QueryResult[SearchResult]:
    try:
        ...
        return QueryResult.ok(result)
    except Neo4jError as e:
        return QueryResult.fail(str(e), ErrorCode.NEO4J_ERROR)

# 사용처에서 명시적 처리
result = search(query)
if result.success:
    return result.data
else:
    logger.error(f"{result.error_code}: {result.error}")
```

**이점**:
- 타입 안전성
- 명시적 에러 핸들링
- API 일관성

### 3. 왜 서비스를 분리했는가?

**문제**: 900+ 라인 클래스는 수정하기 어려움

```python
# Before: 단일 거대 클래스
class AdvancedQueryService:
    def search(...): pass          # 200 lines
    def find_connections(...): pass  # 150 lines
    def find_patterns(...): pass     # 180 lines
    # ... 7 methods, 900+ lines
```

**해결**: 단일 책임 원칙 (SRP)

```python
# After: 각 서비스는 하나의 책임만
class DocumentSearchService:
    def search(...): pass  # 150 lines

class RelationshipQueryService:
    def find_connections(...): pass  # 120 lines
```

**이점**:
- 독립적 수정 가능
- 명확한 책임 분리
- 팀 협업 용이
- 테스트 용이

### 4. 왜 Pydantic인가?

**문제**: Dict[str, Any]는 타입 체크 불가

```python
# Before: 런타임 에러
def search(filters: List[Dict[str, Any]]):
    field = filters[0]["filed"]  # 오타! 런타임 에러
```

**해결**: Pydantic 모델

```python
# After: IDE에서 오타 감지
class NodeFilter(BaseModel):
    field: str
    operator: FilterOperator
    value: Any

def search(filters: List[NodeFilter]):
    field = filters[0].field  # 자동완성, 타입 체크
```

**이점**:
- IDE 자동완성
- 컴파일 타임 에러 감지
- 자동 검증
- API 문서 자동 생성

---

## CODING_RULES 준수

### Rule 1: FP First

✅ **적용**:
- Domain Layer 전체가 순수 함수
- 부작용은 Infrastructure에 격리
- 테스트 시 모킹 불필요

### Rule 1: KISS

✅ **적용**:
- 각 함수는 하나의 일만 수행
- 복잡한 로직은 작은 함수로 분해
- 명확한 함수명

### Rule 1: DRY

✅ **적용**:
- CypherFilterBuilder: 중복 제거
- Operator mapping: 단일 정의
- Result Pattern: 재사용 가능

### Rule 2: Architecture

✅ **적용**:
- Clean Architecture 4계층
- 의존성 규칙 준수
- 레이어별 명확한 책임

### Rule 4: Type Safety

✅ **적용**:
- Dict[str, Any] → Pydantic 모델
- Generic types (QueryResult[T])
- Enum for operators

### Rule 5: Error Handling

✅ **적용**:
- Result Pattern 사용
- 명시적 ErrorCode
- HTTP 매핑 일관성

### Rule 9: Documentation

✅ **적용**:
- Docstring에 "Why" 설명
- Design Decision 명시
- API 문서 자동 생성

---

## 성능 고려사항

### 쿼리 최적화

1. **파라미터화**:
   - 모든 쿼리는 파라미터화
   - Neo4j 쿼리 플랜 캐싱 가능

2. **인덱스 활용**:
   - api_id, created_at 등 인덱스 사용
   - WHERE 절 최적화

3. **깊이 제한**:
   - 경로 탐색: 최대 10 hop
   - 무한 루프 방지

### 확장성

1. **수평 확장**:
   - 서비스는 stateless
   - 여러 인스턴스 배포 가능

2. **캐싱**:
   - 자주 사용되는 쿼리 결과 캐싱 가능
   - Redis 통합 고려

---

## 테스트 전략

### 단위 테스트 (Domain)

```python
# tests/unit/domain/test_filter_builder.py

def test_build_node_filter_equals():
    """순수 함수 테스트 - 모킹 불필요"""
    filter_spec = NodeFilter(field="title", operator=FilterOperator.EQUALS, value="교육")
    clause, params = CypherFilterBuilder.build_node_filter(filter_spec, "d", "f0")

    assert clause == "d.title = $f0_title"
    assert params == {"f0_title": "교육"}
```

### 통합 테스트 (Application)

```python
# tests/integration/test_search_service.py

@pytest.mark.integration
def test_search_with_filter(search_service):
    """실제 Neo4j와 통합 테스트"""
    query = SearchQuery(filters=[...])
    result = search_service.search(query)

    assert result.success is True
    assert len(result.data.documents) > 0
```

### API 테스트 (Presentation)

```python
# tests/api/test_advanced_queries.py

def test_search_endpoint(client):
    """FastAPI 엔드포인트 테스트"""
    response = client.post("/api/advanced/search", json={...})

    assert response.status_code == 200
    assert "documents" in response.json()
```

---

## 마이그레이션 가이드

### 기존 코드에서 전환

```python
# Before
from app.services.advanced_query_service import AdvancedQueryService

service = AdvancedQueryService(neo4j_service)
result = service.search_documents_advanced(filters=[...])

# After
from app.services.query import DocumentSearchService
from app.infrastructure.neo4j import Neo4jQueryExecutor
from app.domain.query.models import SearchQuery, NodeFilter, FilterOperator

executor = Neo4jQueryExecutor(neo4j_service)
service = DocumentSearchService(executor)

query = SearchQuery(
    filters=[
        NodeFilter(field="title", operator=FilterOperator.CONTAINS, value="교육")
    ]
)
result = service.search(query)

if result.success:
    documents = result.data.documents
else:
    logger.error(result.error)
```

---

## 향후 개선 방향

### 1. 캐싱 레이어
- Redis 통합
- 쿼리 결과 캐싱
- TTL 기반 무효화

### 2. 배치 쿼리
- 여러 쿼리를 하나의 트랜잭션으로
- 성능 최적화

### 3. GraphQL 지원
- 유연한 쿼리 인터페이스
- 클라이언트 중심 API

### 4. 실시간 쿼리
- WebSocket 지원
- 변경 알림

---

**작성일**: 2024-12-25
**버전**: 2.0
**Author**: Advanced Query Team
**Review**: Architecture Team

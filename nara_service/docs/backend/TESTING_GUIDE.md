# Testing Guide

## 개요

리팩토링된 Advanced Query Service의 테스트 가이드입니다.

테스트는 3가지 레벨로 구성됩니다:
1. **단위 테스트** (Unit Tests): 순수 함수 테스트
2. **통합 테스트** (Integration Tests): 서비스 + Neo4j 테스트
3. **API 테스트** (API Tests): 엔드포인트 테스트

---

## 테스트 환경 설정

### 1. 의존성 설치

```bash
cd backend
pip install pytest pytest-cov pytest-asyncio
```

### 2. Neo4j 테스트 인스턴스 (통합 테스트용)

**Option A: Docker**
```bash
docker run -d \
  --name neo4j-test \
  -p 7687:7687 \
  -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/testpassword \
  neo4j:latest
```

**Option B: 로컬 Neo4j**
- 별도의 테스트 데이터베이스 사용 권장
- `.env.test` 파일에 테스트 DB 설정

---

## 테스트 구조

```
backend/tests/
├── __init__.py
├── conftest.py                    # Pytest fixtures
├── unit/                          # 단위 테스트 (빠름, 모킹 불필요)
│   └── domain/
│       ├── test_filter_builder.py
│       ├── test_match_builder.py
│       └── test_result_pattern.py
├── integration/                   # 통합 테스트 (Neo4j 필요)
│   └── test_search_service.py
└── api/                          # API 테스트 (FastAPI client)
    └── test_advanced_queries.py
```

---

## 테스트 실행

### 모든 테스트 실행

```bash
cd backend
pytest
```

### 단위 테스트만 실행 (빠름)

```bash
# Domain layer 순수 함수 테스트 (Neo4j 불필요)
pytest tests/unit/
```

### 통합 테스트만 실행

```bash
# Neo4j 연결 필요
pytest -m integration
```

### 통합 테스트 제외하고 실행

```bash
# CI 환경에서 유용
pytest -m "not integration"
```

### 특정 파일 테스트

```bash
pytest tests/unit/domain/test_filter_builder.py
```

### 특정 테스트 함수

```bash
pytest tests/unit/domain/test_filter_builder.py::TestCypherFilterBuilder::test_build_node_filter_equals
```

### 커버리지와 함께 실행

```bash
pytest --cov=app --cov-report=html
```

커버리지 리포트: `htmlcov/index.html`

---

## 단위 테스트 (Unit Tests)

### 특징
- ✅ 매우 빠름 (Neo4j 불필요)
- ✅ 순수 함수 테스트
- ✅ 모킹 불필요
- ✅ CI/CD에 적합

### 예시: Filter Builder 테스트

```python
# tests/unit/domain/test_filter_builder.py

from app.domain.query.models.filters import NodeFilter, FilterOperator
from app.domain.query.builders.filter_builder import CypherFilterBuilder


def test_build_node_filter_equals():
    """EQUALS 연산자 테스트"""
    # Given
    filter_spec = NodeFilter(
        field="title",
        operator=FilterOperator.EQUALS,
        value="교육"
    )

    # When
    clause, params = CypherFilterBuilder.build_node_filter(
        filter_spec, "d", "filter_0"
    )

    # Then
    assert clause == "d.title = $filter_0_title"
    assert params == {"filter_0_title": "교육"}


def test_build_filters_clause_multiple():
    """여러 필터 AND 조합 테스트"""
    # Given
    filters = [
        NodeFilter(field="title", operator=FilterOperator.CONTAINS, value="교육"),
        NodeFilter(field="status", operator=FilterOperator.EQUALS, value="active")
    ]

    # When
    clause, params = CypherFilterBuilder.build_filters_clause(filters, "d", "f")

    # Then
    assert "d.title CONTAINS $f_0_title" in clause
    assert "d.status = $f_1_status" in clause
    assert " AND " in clause
    assert params == {
        "f_0_title": "교육",
        "f_1_status": "active"
    }
```

### 실행

```bash
pytest tests/unit/domain/test_filter_builder.py -v
```

**출력 예시**:
```
test_filter_builder.py::test_build_node_filter_equals PASSED
test_filter_builder.py::test_build_node_filter_contains PASSED
test_filter_builder.py::test_build_filters_clause_multiple PASSED
...

=============== 15 passed in 0.12s ===============
```

---

## 통합 테스트 (Integration Tests)

### 특징
- ⚠️ 느림 (실제 Neo4j 사용)
- ✅ End-to-end 검증
- ✅ 실제 데이터로 테스트
- ⚠️ 테스트 데이터 준비 필요

### 예시: Search Service 통합 테스트

```python
# tests/integration/test_search_service.py

import pytest
from app.services.query.search_service import DocumentSearchService
from app.infrastructure.neo4j.query_executor import Neo4jQueryExecutor
from app.domain.query.models.filters import NodeFilter, FilterOperator, SearchQuery
from app.services.neo4j_service import neo4j_service


@pytest.fixture
def query_executor():
    """Fixture: Neo4j query executor"""
    return Neo4jQueryExecutor(neo4j_service)


@pytest.fixture
def search_service(query_executor):
    """Fixture: Document search service"""
    return DocumentSearchService(query_executor)


@pytest.mark.integration
def test_search_with_simple_filter(search_service):
    """단일 필터로 검색 테스트"""
    # Given
    query = SearchQuery(
        filters=[
            NodeFilter(
                field="title",
                operator=FilterOperator.CONTAINS,
                value="교육"
            )
        ],
        limit=10
    )

    # When
    result = search_service.search(query)

    # Then
    assert result.success is True
    assert result.data is not None
    assert isinstance(result.data.documents, list)
    assert result.data.limit == 10


@pytest.mark.integration
def test_search_pagination(search_service):
    """페이지네이션 테스트"""
    # Given - 첫 페이지
    query_page1 = SearchQuery(filters=[], limit=5, offset=0)

    # When
    result_page1 = search_service.search(query_page1)

    # Given - 두 번째 페이지
    query_page2 = SearchQuery(filters=[], limit=5, offset=5)

    # When
    result_page2 = search_service.search(query_page2)

    # Then
    assert result_page1.success is True
    assert result_page2.success is True

    if result_page1.data.total > 5:
        # 페이지가 다른지 확인
        docs_page1 = [d.id for d in result_page1.data.documents]
        docs_page2 = [d.id for d in result_page2.data.documents]
        assert len(set(docs_page1) & set(docs_page2)) == 0
```

### 실행

```bash
# 통합 테스트만 실행
pytest -m integration -v

# 특정 통합 테스트
pytest tests/integration/test_search_service.py::test_search_with_simple_filter -v
```

**출력 예시**:
```
test_search_service.py::test_search_with_simple_filter PASSED
test_search_service.py::test_search_pagination PASSED
...

=============== 7 passed in 2.34s ===============
```

---

## API 테스트 (API Tests)

### 특징
- ✅ FastAPI TestClient 사용
- ✅ 실제 HTTP 요청/응답 검증
- ✅ End-to-end 시나리오 테스트

### 예시: Advanced Queries 엔드포인트 테스트

```python
# tests/api/test_advanced_queries.py

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Fixture: FastAPI test client"""
    return TestClient(app)


@pytest.mark.api
def test_search_endpoint(client):
    """검색 엔드포인트 테스트"""
    # Given
    request_body = {
        "filters": [
            {
                "field": "title",
                "operator": "contains",
                "value": "교육"
            }
        ],
        "limit": 10,
        "offset": 0
    }

    # When
    response = client.post("/api/advanced/search", json=request_body)

    # Then
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["documents"], list)


@pytest.mark.api
def test_search_endpoint_validation_error(client):
    """검증 에러 테스트"""
    # Given - 잘못된 operator
    request_body = {
        "filters": [
            {
                "field": "title",
                "operator": "invalid_operator",
                "value": "교육"
            }
        ]
    }

    # When
    response = client.post("/api/advanced/search", json=request_body)

    # Then
    assert response.status_code == 422  # Validation Error


@pytest.mark.api
def test_strong_connections_endpoint(client):
    """강한 연결 엔드포인트 테스트"""
    # When
    response = client.get(
        "/api/advanced/relationships/strong-connections/15001001?min_strength=0.7&limit=10"
    )

    # Then
    assert response.status_code in [200, 404]  # 문서가 있으면 200, 없으면 404
```

### 실행

```bash
# API 테스트만 실행
pytest -m api -v

# 특정 API 테스트
pytest tests/api/test_advanced_queries.py::test_search_endpoint -v
```

---

## 테스트 작성 가이드

### 1. Given-When-Then 패턴 사용

```python
def test_example():
    # Given: 테스트 준비
    filter_spec = NodeFilter(...)

    # When: 테스트 실행
    result = CypherFilterBuilder.build_node_filter(filter_spec, ...)

    # Then: 검증
    assert result == expected_value
```

### 2. 명확한 테스트 이름

```python
# ✅ Good
def test_build_node_filter_with_contains_operator():
    pass

# ❌ Bad
def test_filter():
    pass
```

### 3. 하나의 테스트는 하나의 개념만

```python
# ✅ Good
def test_equals_operator():
    # EQUALS만 테스트
    pass

def test_contains_operator():
    # CONTAINS만 테스트
    pass

# ❌ Bad
def test_all_operators():
    # 모든 operator를 한 번에 테스트
    pass
```

### 4. Fixture 활용

```python
# conftest.py
@pytest.fixture
def sample_filter():
    """재사용 가능한 테스트 데이터"""
    return NodeFilter(
        field="title",
        operator=FilterOperator.CONTAINS,
        value="교육"
    )

# test file
def test_something(sample_filter):
    # sample_filter 자동 주입
    clause, params = build_filter(sample_filter)
    assert ...
```

---

## CI/CD 통합

### GitHub Actions 예시

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      neo4j:
        image: neo4j:latest
        env:
          NEO4J_AUTH: neo4j/testpassword
        ports:
          - 7687:7687

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run unit tests
        run: |
          cd backend
          pytest tests/unit/ -v

      - name: Run integration tests
        run: |
          cd backend
          pytest -m integration -v
        env:
          NEO4J_URI: bolt://localhost:7687
          NEO4J_USER: neo4j
          NEO4J_PASSWORD: testpassword

      - name: Generate coverage report
        run: |
          cd backend
          pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## 테스트 디버깅

### Verbose 모드

```bash
pytest -v
```

### 실패한 테스트만 재실행

```bash
pytest --lf
```

### pdb 디버거 사용

```python
def test_example():
    filter_spec = NodeFilter(...)

    import pdb; pdb.set_trace()  # 여기서 멈춤

    result = build_filter(filter_spec)
    assert ...
```

### 로그 출력

```bash
pytest -v --log-cli-level=DEBUG
```

---

## 커버리지 목표

### 현재 커버리지

- Domain Layer: **100%** (순수 함수, 쉬움)
- Application Layer: **80%+**
- Infrastructure Layer: **70%+** (모킹 필요)
- Presentation Layer: **80%+**

### 커버리지 확인

```bash
pytest --cov=app --cov-report=term-missing
```

**출력 예시**:
```
Name                                        Stmts   Miss  Cover   Missing
-------------------------------------------------------------------------
app/domain/query/builders/filter_builder.py   45      0   100%
app/domain/query/builders/match_builder.py    38      0   100%
app/services/query/search_service.py          78      8    90%   45-52
-------------------------------------------------------------------------
TOTAL                                        325     15    95%
```

---

## 모범 사례

### 1. 순수 함수는 모킹하지 말 것

```python
# ✅ Good: 순수 함수는 직접 호출
def test_filter_builder():
    result = CypherFilterBuilder.build_node_filter(...)
    assert result == expected

# ❌ Bad: 순수 함수 모킹 (불필요)
def test_filter_builder(mocker):
    mocker.patch('...CypherFilterBuilder.build_node_filter', return_value=...)
```

### 2. I/O는 통합 테스트에서

```python
# ✅ Good: 통합 테스트에서 실제 Neo4j 사용
@pytest.mark.integration
def test_search_service(search_service):
    result = search_service.search(...)
    assert result.success

# ⚠️ OK: 단위 테스트에서는 모킹 가능
def test_search_service_unit(mocker):
    mock_executor = mocker.Mock()
    service = DocumentSearchService(mock_executor)
    ...
```

### 3. 테스트 데이터 관리

```python
# fixtures/test_data.py
TEST_FILTERS = [
    NodeFilter(field="title", operator=FilterOperator.CONTAINS, value="교육"),
    NodeFilter(field="status", operator=FilterOperator.EQUALS, value="active")
]

# 테스트에서 사용
from fixtures.test_data import TEST_FILTERS

def test_with_test_data():
    result = build_filters(TEST_FILTERS)
    assert ...
```

---

## 문제 해결

### Neo4j 연결 실패

```bash
# Neo4j가 실행 중인지 확인
docker ps | grep neo4j

# 연결 테스트
python -c "from app.services.neo4j_service import neo4j_service; neo4j_service.verify_connectivity()"
```

### Fixture not found

```python
# conftest.py에 fixture 정의했는지 확인
# pytest가 conftest.py를 찾는지 확인
pytest --fixtures
```

### Import 에러

```bash
# PYTHONPATH 설정
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
pytest
```

---

## 추가 자료

- [pytest 공식 문서](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Clean Architecture Testing](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

**작성일**: 2024-12-25
**버전**: 1.0

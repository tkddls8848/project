# OpenAPI 명세 문서의 그래프 DB 관계 설정 전략

## 📋 목차
1. [현재 문제 분석](#현재-문제-분석)
2. [추출 가능한 관계 요소](#추출-가능한-관계-요소)
3. [그래프 스키마 확장안](#그래프-스키마-확장안)
4. [구현 전략](#구현-전략)
5. [활용 사례](#활용-사례)

---

## 현재 문제 분석

### 기존 데이터 구조
```json
{
  "api_id": "15002731",
  "metadata": {
    "title": "산림청_백두대간_등산로정보",
    "provider": "산림청",
    "category": "농림 - 농업·농촌",
    "keywords": ["산정보", "등산로", "백두대간"]
  },
  "content": {
    "endpoints": [...],      // ✅ 활용 가능
    "base_url": "...",       // ✅ 활용 가능
  },
  "swagger_json": {          // ✅ 풍부한 구조 정보
    "paths": {...},
    "parameters": {...},
    "responses": {...}
  }
}
```

### 현재 그래프 관계 (제한적)
```cypher
// 현재는 메타데이터만 사용
(Document)-[:HAS_KEYWORD]->(Keyword)
(Document)-[:BELONGS_TO]->(Category)
(Document)-[:PROVIDED_BY]->(Provider)

// ❌ API 구조 정보는 활용 안됨
```

**문제점:**
- OpenAPI 명세의 풍부한 구조 정보를 버리고 있음
- 같은 엔드포인트/파라미터를 가진 API들의 연관성 파악 불가
- 기술적 호환성(같은 스키마 사용) 분석 불가

---

## 추출 가능한 관계 요소

### 1. 엔드포인트 기반 관계

#### 1.1 같은 경로 패턴
```json
// 예시: 두 문서가 같은 엔드포인트 패턴 사용
Doc A: "/gettrailservice"
Doc B: "/gettrailservice"  // 같은 경로

→ (DocA)-[:SHARES_ENDPOINT_PATTERN]->(DocB)
```

**활용:**
- 유사한 API 구조를 가진 문서 발견
- API 버전 간 비교 (v1 vs v2)

#### 1.2 HTTP 메서드 그룹화
```json
"method": "GET"
"method": "POST"

→ (Document)-[:USES_METHOD]->(HTTPMethod:GET)
```

**활용:**
- GET 전용 API vs POST 전용 API 분류
- RESTful 설계 패턴 분석

---

### 2. 파라미터 기반 관계

#### 2.1 공통 파라미터 공유
```json
// 많은 API가 공통으로 사용하는 파라미터
{
  "name": "ServiceKey",
  "required": true,
  "type": "string"
}

→ (Document)-[:REQUIRES_PARAMETER]->(Parameter:ServiceKey)
```

**활용 예시:**
```cypher
// "ServiceKey" 파라미터를 사용하는 모든 API 찾기
MATCH (d:Document)-[:REQUIRES_PARAMETER]->(p:Parameter {name: "ServiceKey"})
RETURN d.title, count(p) as usage_count
ORDER BY usage_count DESC
```

**발견 가능한 인사이트:**
- 인증 방식이 같은 API 그룹화
- 페이지네이션 패턴 공유 (pageNo, numOfRows)

#### 2.2 파라미터 타입 패턴
```json
{
  "name": "pageNo",
  "type": "integer",
  "description": "페이지번호"
}

→ (Parameter)-[:HAS_TYPE]->(DataType:Integer)
```

---

### 3. 응답 스키마 기반 관계

#### 3.1 공통 응답 필드
```json
// 표준 응답 구조
{
  "resultCode": {"type": "integer"},
  "resultMsg": {"type": "string"},
  "totalCount": {"type": "integer"}
}

→ (Document)-[:RETURNS_FIELD]->(Field:resultCode)
```

**활용:**
```cypher
// 같은 응답 구조를 가진 API 발견 (호환성 분석)
MATCH (d1:Document)-[:RETURNS_FIELD]->(f:Field {name: "resultCode"})<-[:RETURNS_FIELD]-(d2:Document)
WHERE d1 <> d2
RETURN d1.title, d2.title, "호환 가능" as compatibility
```

#### 3.2 중첩 스키마 패턴
```json
// items > item > baekduId 같은 중첩 구조
"items": {
  "item": {
    "baekduId": "..."
  }
}

→ (Field:items)-[:CONTAINS]->(Field:item)-[:CONTAINS]->(Field:baekduId)
```

---

### 4. 도메인/서비스 기반 관계

#### 4.1 Base URL 공유 (같은 서비스)
```json
"base_url": "https://openapi.forest.go.kr/openapi/service/trailInfoService"
"host": "openapi.forest.go.kr"

→ (Document)-[:BELONGS_TO_SERVICE]->(Service:forest.go.kr)
```

**활용:**
```cypher
// 같은 서비스 제공자의 API 그룹화
MATCH (d:Document)-[:BELONGS_TO_SERVICE]->(s:Service {host: "openapi.forest.go.kr"})
RETURN d.title, s.host
```

#### 4.2 Tag 기반 그룹화
```json
"tags": ["API 목록"]

→ (Document)-[:HAS_TAG]->(Tag:"API 목록")
```

---

### 5. 데이터 포맷 기반 관계

#### 5.1 Content Type
```json
"produces": ["application/xml", "application/json"]
"consumes": ["application/json"]

→ (Document)-[:PRODUCES]->(Format:XML)
→ (Document)-[:CONSUMES]->(Format:JSON)
```

**활용:**
```cypher
// XML 응답을 제공하는 API 찾기
MATCH (d:Document)-[:PRODUCES]->(f:Format {name: "XML"})
RETURN d.title
```

---

## 그래프 스키마 확장안

### 새로운 노드 타입

```python
# backend/app/graph_schema.py 확장

class NodeLabel:
    # 기존
    DOCUMENT = "Document"
    KEYWORD = "Keyword"
    PROVIDER = "Provider"
    CATEGORY = "Category"

    # 새로운 노드 (OpenAPI 전용)
    ENDPOINT = "Endpoint"           # API 엔드포인트
    PARAMETER = "Parameter"         # 파라미터
    RESPONSE_FIELD = "ResponseField" # 응답 필드
    HTTP_METHOD = "HTTPMethod"      # HTTP 메서드 (GET, POST)
    DATA_TYPE = "DataType"          # 데이터 타입 (string, integer)
    FORMAT = "Format"               # 데이터 포맷 (XML, JSON)
    SERVICE = "Service"             # API 서비스 (host 기반)
    TAG = "Tag"                     # API 태그

class RelationType:
    # 기존
    HAS_KEYWORD = "HAS_KEYWORD"
    PROVIDED_BY = "PROVIDED_BY"
    BELONGS_TO = "BELONGS_TO"
    CUSTOM_RELATED_TO = "CUSTOM_RELATED_TO"

    # 새로운 관계 (OpenAPI 전용)
    HAS_ENDPOINT = "HAS_ENDPOINT"           # Document -> Endpoint
    REQUIRES_PARAMETER = "REQUIRES_PARAMETER" # Endpoint -> Parameter
    RETURNS_FIELD = "RETURNS_FIELD"         # Endpoint -> ResponseField
    USES_METHOD = "USES_METHOD"             # Endpoint -> HTTPMethod
    HAS_TYPE = "HAS_TYPE"                   # Parameter/Field -> DataType
    PRODUCES = "PRODUCES"                   # Endpoint -> Format
    CONSUMES = "CONSUMES"                   # Endpoint -> Format
    BELONGS_TO_SERVICE = "BELONGS_TO_SERVICE" # Document -> Service
    HAS_TAG = "HAS_TAG"                     # Endpoint -> Tag

    # 의미적 관계
    SHARES_ENDPOINT_PATTERN = "SHARES_ENDPOINT_PATTERN"  # Doc <-> Doc
    COMPATIBLE_SCHEMA = "COMPATIBLE_SCHEMA"               # Doc <-> Doc
    SIMILAR_PARAMETERS = "SIMILAR_PARAMETERS"             # Doc <-> Doc
```

### 확장된 그래프 구조

```cypher
// 예시: 산림청 백두대간 등산로 API
(doc:Document {api_id: "15002731"})
  -[:HAS_ENDPOINT]->
    (ep:Endpoint {path: "/gettrailservice", method: "GET"})
      -[:REQUIRES_PARAMETER]->
        (p1:Parameter {name: "searchWrd", type: "string", required: false})
      -[:REQUIRES_PARAMETER]->
        (p2:Parameter {name: "ServiceKey", type: "string", required: true})
      -[:REQUIRES_PARAMETER]->
        (p3:Parameter {name: "pageNo", type: "integer"})
      -[:RETURNS_FIELD]->
        (f1:ResponseField {name: "resultCode", type: "integer"})
      -[:RETURNS_FIELD]->
        (f2:ResponseField {name: "items"})
          -[:CONTAINS]->
            (f3:ResponseField {name: "baekduId"})
      -[:PRODUCES]->
        (fmt1:Format {name: "XML"})
      -[:PRODUCES]->
        (fmt2:Format {name: "JSON"})
      -[:HAS_TAG]->
        (tag:Tag {name: "API 목록"})

(doc)-[:BELONGS_TO_SERVICE]->(svc:Service {host: "openapi.forest.go.kr"})
```

---

## 구현 전략

### Phase 1: 스키마 확장

**파일:** `backend/app/graph_schema_openapi.py` (신규)

```python
"""
OpenAPI 전용 그래프 스키마 확장

CODING_RULES 준수:
- Rule 7: 문서 타입(openapi_old, openapi_new 등)은 관계 분석에서 제외
- 대신 API 구조적 요소(엔드포인트, 파라미터, 스키마)를 활용
"""

class OpenAPINodeLabel:
    """OpenAPI 관련 노드 라벨"""
    ENDPOINT = "Endpoint"
    PARAMETER = "Parameter"
    RESPONSE_FIELD = "ResponseField"
    HTTP_METHOD = "HTTPMethod"
    DATA_TYPE = "DataType"
    FORMAT = "Format"
    SERVICE = "Service"
    TAG = "Tag"


class OpenAPIRelationType:
    """OpenAPI 관련 관계 타입"""
    HAS_ENDPOINT = "HAS_ENDPOINT"
    REQUIRES_PARAMETER = "REQUIRES_PARAMETER"
    OPTIONAL_PARAMETER = "OPTIONAL_PARAMETER"
    RETURNS_FIELD = "RETURNS_FIELD"
    USES_METHOD = "USES_METHOD"
    HAS_TYPE = "HAS_TYPE"
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    BELONGS_TO_SERVICE = "BELONGS_TO_SERVICE"
    HAS_TAG = "HAS_TAG"
    CONTAINS = "CONTAINS"  # 중첩 필드

    # 문서 간 의미적 관계
    SHARES_ENDPOINT = "SHARES_ENDPOINT"
    COMPATIBLE_RESPONSE = "COMPATIBLE_RESPONSE"
    SAME_SERVICE_FAMILY = "SAME_SERVICE_FAMILY"
```

---

### Phase 2: OpenAPI 파서 및 그래프 생성기

**파일:** `backend/app/services/openapi_graph_builder.py` (신규)

```python
"""
OpenAPI 명세를 Neo4j 그래프로 변환

Design Decision:
- Domain Layer: 순수 함수로 그래프 구조 생성
- Infrastructure Layer: Neo4j에 저장
"""

import logging
from typing import Dict, Any, List
from app.graph_schema_openapi import OpenAPINodeLabel, OpenAPIRelationType
from app.services.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)


class OpenAPIGraphBuilder:
    """
    OpenAPI 명세를 그래프 구조로 변환

    CODING_RULES 준수:
    - FP First: 순수 함수로 그래프 구조 생성
    - SRP: 각 메서드가 하나의 책임만
    """

    def __init__(self, neo4j_service):
        self.neo4j_service = neo4j_service

    def build_openapi_graph(self, doc_data: Dict[str, Any]) -> None:
        """
        OpenAPI 문서를 그래프로 변환 및 저장

        Args:
            doc_data: refined JSON 데이터
        """
        api_id = doc_data.get("api_id")
        content = doc_data.get("content", {})

        if not content or content.get("data_type") != "API":
            logger.debug(f"Not an API document: {api_id}")
            return

        try:
            # 1. 서비스 노드 생성
            self._create_service_node(doc_data)

            # 2. 엔드포인트 및 파라미터 생성
            self._create_endpoints_and_parameters(api_id, content)

            # 3. 응답 스키마 생성
            self._create_response_schema(api_id, content)

            # 4. 포맷/프로토콜 노드 생성
            self._create_format_nodes(api_id, content)

            # 5. 문서 간 유사성 관계 생성 (선택적)
            self._create_similarity_relationships(api_id)

            logger.info(f"OpenAPI graph built for {api_id}")

        except Exception as e:
            logger.error(f"Error building OpenAPI graph for {api_id}: {e}")

    def _create_service_node(self, doc_data: Dict[str, Any]) -> None:
        """
        API 서비스 노드 생성 (host 기반)

        Design Decision:
        - 같은 host를 가진 문서들을 그룹화
        - 예: openapi.forest.go.kr의 모든 API
        """
        api_id = doc_data.get("api_id")
        content = doc_data.get("content", {})
        swagger = doc_data.get("swagger_json", {})

        host = swagger.get("host")
        base_path = swagger.get("basePath", "")

        if not host:
            return

        query = """
        MATCH (d:Document {api_id: $api_id})
        MERGE (s:Service {host: $host})
        ON CREATE SET
            s.name = $host,
            s.base_path = $base_path
        MERGE (d)-[:BELONGS_TO_SERVICE]->(s)
        """

        with self.neo4j_service.get_session() as session:
            session.run(query, api_id=api_id, host=host, base_path=base_path)

    def _create_endpoints_and_parameters(
        self,
        api_id: str,
        content: Dict[str, Any]
    ) -> None:
        """
        엔드포인트 및 파라미터 노드 생성

        관계:
        - (Document)-[:HAS_ENDPOINT]->(Endpoint)
        - (Endpoint)-[:REQUIRES_PARAMETER]->(Parameter)
        - (Endpoint)-[:USES_METHOD]->(HTTPMethod)
        """
        endpoints = content.get("endpoints", [])

        for ep_data in endpoints:
            path = ep_data.get("path")
            method = ep_data.get("method", "GET")
            description = ep_data.get("description", "")

            # 엔드포인트 노드 생성
            ep_id = f"{api_id}_{method}_{path}"

            ep_query = """
            MATCH (d:Document {api_id: $api_id})
            MERGE (ep:Endpoint {id: $ep_id})
            ON CREATE SET
                ep.path = $path,
                ep.method = $method,
                ep.description = $description
            MERGE (d)-[:HAS_ENDPOINT]->(ep)

            // HTTP Method 노드
            MERGE (m:HTTPMethod {name: $method})
            MERGE (ep)-[:USES_METHOD]->(m)
            """

            with self.neo4j_service.get_session() as session:
                session.run(
                    ep_query,
                    api_id=api_id,
                    ep_id=ep_id,
                    path=path,
                    method=method,
                    description=description
                )

            # 파라미터 생성
            parameters = ep_data.get("parameters", [])
            self._create_parameters(ep_id, parameters)

    def _create_parameters(
        self,
        ep_id: str,
        parameters: List[Dict[str, Any]]
    ) -> None:
        """
        파라미터 노드 생성

        중요: 같은 이름의 파라미터는 MERGE하여 재사용
        → 여러 API에서 공통 파라미터를 공유하면 자동으로 연결됨
        """
        for param in parameters:
            name = param.get("name")
            param_type = param.get("type", "string")
            required = param.get("required", False)
            description = param.get("description", "")

            # 파라미터 노드 (이름으로 MERGE)
            param_query = """
            MATCH (ep:Endpoint {id: $ep_id})
            MERGE (p:Parameter {name: $name})
            ON CREATE SET
                p.type = $param_type,
                p.description = $description

            // 관계: required 여부에 따라 다른 관계 타입
            """

            if required:
                param_query += "MERGE (ep)-[:REQUIRES_PARAMETER]->(p)"
            else:
                param_query += "MERGE (ep)-[:OPTIONAL_PARAMETER]->(p)"

            # DataType 노드
            param_query += """
            MERGE (dt:DataType {name: $param_type})
            MERGE (p)-[:HAS_TYPE]->(dt)
            """

            with self.neo4j_service.get_session() as session:
                session.run(
                    param_query,
                    ep_id=ep_id,
                    name=name,
                    param_type=param_type,
                    description=description
                )

    def _create_response_schema(
        self,
        api_id: str,
        content: Dict[str, Any]
    ) -> None:
        """
        응답 스키마를 그래프로 변환

        중첩 구조 처리:
        - items > item > baekduId
        → (items)-[:CONTAINS]->(item)-[:CONTAINS]->(baekduId)
        """
        endpoints = content.get("endpoints", [])

        for ep_data in endpoints:
            path = ep_data.get("path")
            method = ep_data.get("method", "GET")
            ep_id = f"{api_id}_{method}_{path}"

            responses = ep_data.get("responses", [])
            for resp in responses:
                if resp.get("status_code") == "200":
                    # swagger_json에서 상세 스키마 추출
                    self._extract_schema_from_swagger(api_id, ep_id, path, method)

    def _extract_schema_from_swagger(
        self,
        api_id: str,
        ep_id: str,
        path: str,
        method: str
    ) -> None:
        """
        swagger_json에서 응답 스키마 추출

        복잡한 중첩 구조를 재귀적으로 처리
        """
        # swagger_json 로드
        with self.neo4j_service.get_session() as session:
            result = session.run(
                "MATCH (d:Document {api_id: $api_id}) RETURN d.swagger_json as swagger",
                api_id=api_id
            )
            record = result.single()
            if not record:
                return

            # 실제 구현에서는 Document 노드에 swagger_json을 저장하거나
            # 별도로 파일에서 읽어야 함
            # 여기서는 개념적 구현

    def _create_format_nodes(
        self,
        api_id: str,
        content: Dict[str, Any]
    ) -> None:
        """
        데이터 포맷 노드 생성 (XML, JSON 등)

        활용:
        - XML 응답 API만 필터링
        - JSON 전용 API 검색
        """
        endpoints = content.get("endpoints", [])

        # swagger_json에서 produces/consumes 정보 추출 필요
        # 간단한 예시만 제시

    def _create_similarity_relationships(self, api_id: str) -> None:
        """
        문서 간 유사성 관계 자동 생성

        규칙:
        1. 같은 파라미터 3개 이상 공유 → SIMILAR_PARAMETERS
        2. 같은 응답 필드 5개 이상 공유 → COMPATIBLE_RESPONSE
        3. 같은 Service 소속 → SAME_SERVICE_FAMILY

        Design Decision:
        - 이 관계는 시스템이 자동 생성 (created_by: "system")
        - 사용자 정의 관계와 구분
        """
        query = """
        // 1. 같은 파라미터를 많이 공유하는 문서 찾기
        MATCH (d1:Document {api_id: $api_id})-[:HAS_ENDPOINT]->()-[:REQUIRES_PARAMETER]->(p:Parameter)
              <-[:REQUIRES_PARAMETER]-()<-[:HAS_ENDPOINT]-(d2:Document)
        WHERE d1 <> d2
        WITH d1, d2, collect(DISTINCT p.name) as common_params
        WHERE size(common_params) >= 3

        MERGE (d1)-[r:SIMILAR_PARAMETERS]->(d2)
        ON CREATE SET
            r.common_parameters = common_params,
            r.similarity_score = size(common_params) * 0.1,
            r.created_by = "system",
            r.created_at = datetime()
        """

        with self.neo4j_service.get_session() as session:
            session.run(query, api_id=api_id)
```

---

### Phase 3: 크롤러 통합

**파일:** `backend/app/services/graph_ingestion_service.py` (수정)

```python
"""
문서 적재 시 OpenAPI 그래프도 함께 생성
"""

from app.services.openapi_graph_builder import OpenAPIGraphBuilder

class GraphIngestionService:
    def __init__(self, neo4j_service):
        self.neo4j_service = neo4j_service
        self.openapi_builder = OpenAPIGraphBuilder(neo4j_service)

    def ingest_document(self, doc_data: Dict[str, Any]) -> None:
        """
        문서를 Neo4j에 적재

        1. 기본 문서 노드 생성 (기존)
        2. OpenAPI인 경우 추가 그래프 생성 (신규)
        """
        # 기존: 기본 노드 및 관계 생성
        self.neo4j_service.upsert_document(doc_data)

        # 신규: OpenAPI 전용 그래프 생성
        if self._is_openapi_document(doc_data):
            self.openapi_builder.build_openapi_graph(doc_data)

    def _is_openapi_document(self, doc_data: Dict[str, Any]) -> bool:
        """OpenAPI 문서인지 확인"""
        content = doc_data.get("content", {})
        return content.get("data_type") == "API"
```

---

## 활용 사례

### 사례 1: 호환 가능한 API 찾기

```cypher
// 같은 파라미터를 사용하는 API 찾기 (통합 가능성)
MATCH (d1:Document {api_id: "15002731"})-[:HAS_ENDPOINT]->()-[:REQUIRES_PARAMETER]->(p:Parameter)
      <-[:REQUIRES_PARAMETER]-()<-[:HAS_ENDPOINT]-(d2:Document)
WHERE d1 <> d2
WITH d1, d2, collect(DISTINCT p.name) as common_params
WHERE size(common_params) >= 3
RETURN
    d1.title as api_1,
    d2.title as api_2,
    common_params,
    size(common_params) as compatibility_score
ORDER BY compatibility_score DESC
```

**결과 예시:**
```
api_1: "산림청_백두대간_등산로정보"
api_2: "산림청_둘레길_정보"
common_params: ["ServiceKey", "pageNo", "numOfRows"]
compatibility_score: 3
```

---

### 사례 2: 같은 서비스 제공자의 API 패밀리

```cypher
// forest.go.kr의 모든 API 찾기
MATCH (d:Document)-[:BELONGS_TO_SERVICE]->(s:Service {host: "openapi.forest.go.kr"})
RETURN d.title, d.api_id
```

**활용:**
- 산림청의 모든 API를 한눈에 파악
- 서비스 단위 문서화

---

### 사례 3: 특정 응답 필드를 가진 API 검색

```cypher
// "resultCode" 필드를 반환하는 모든 API (표준 응답 구조)
MATCH (d:Document)-[:HAS_ENDPOINT]->()-[:RETURNS_FIELD]->(f:ResponseField {name: "resultCode"})
RETURN DISTINCT d.title, d.provider
```

**활용:**
- 표준 에러 핸들링 가능 API 식별
- 같은 응답 포맷 = 클라이언트 코드 재사용 가능

---

### 사례 4: 페이지네이션 패턴 분석

```cypher
// pageNo + numOfRows 패턴을 사용하는 API (표준 페이지네이션)
MATCH (d:Document)-[:HAS_ENDPOINT]->(ep:Endpoint)
WHERE
    (ep)-[:REQUIRES_PARAMETER]->(:Parameter {name: "pageNo"})
    AND (ep)-[:REQUIRES_PARAMETER]->(:Parameter {name: "numOfRows"})
RETURN d.title, d.provider
```

**활용:**
- 일관된 페이지네이션 인터페이스 제공 API 그룹화
- SDK 개발 시 공통 모듈 적용 가능

---

### 사례 5: XML vs JSON API 비교

```cypher
// XML만 지원하는 API vs JSON도 지원하는 API
MATCH (d:Document)-[:HAS_ENDPOINT]->(ep:Endpoint)-[:PRODUCES]->(f:Format)
WITH d, collect(DISTINCT f.name) as formats
RETURN
    d.title,
    formats,
    CASE
        WHEN "JSON" IN formats THEN "Modern"
        ELSE "Legacy"
    END as api_category
```

---

## 구현 우선순위

### Phase 1: 기본 구조 (Week 1)
- [ ] `graph_schema_openapi.py` - 스키마 확장
- [ ] `openapi_graph_builder.py` - 기본 빌더
  - [ ] 서비스 노드 생성
  - [ ] 엔드포인트 노드 생성
  - [ ] 파라미터 노드 생성

### Phase 2: 고급 기능 (Week 2)
- [ ] 응답 스키마 파싱 (중첩 구조)
- [ ] 포맷/프로토콜 노드
- [ ] 자동 유사성 관계 생성

### Phase 3: 통합 (Week 3)
- [ ] 크롤러 통합
- [ ] 기존 문서 재처리 스크립트
- [ ] 관계 추천 알고리즘 개선

### Phase 4: 활용 (Week 4)
- [ ] 고급 쿼리 서비스에 OpenAPI 쿼리 추가
- [ ] API 탐색 UI 개선
- [ ] 문서화 및 예시

---

## 예상 효과

### 📈 개선 지표

| 항목 | Before | After | 개선 |
|------|--------|-------|------|
| **관계 타입** | 3개 (키워드/카테고리/제공자) | 13개+ (API 구조 포함) | +333% |
| **문서 간 연결성** | 메타데이터만 | 기술적 호환성 포함 | ✅ |
| **API 발견성** | 키워드 검색만 | 구조 기반 검색 가능 | ✅ |
| **통합 가능성 분석** | 불가능 | 자동 분석 가능 | ✅ |

### 🎯 비즈니스 가치

1. **API 재사용성 향상**
   - 같은 파라미터/스키마 → SDK 공유 가능

2. **통합 비용 절감**
   - 호환 가능한 API 자동 발견

3. **표준화 촉진**
   - 비표준 API 식별 → 개선 유도

4. **개발자 경험 개선**
   - "이 API와 호환되는 다른 API는?" 즉시 답변

---

## 주의사항 (CODING_RULES 준수)

### ✅ 허용
- API 구조 요소 활용 (엔드포인트, 파라미터, 스키마)
- 기술적 호환성 분석
- 서비스 단위 그룹화

### ❌ 금지
- 문서 타입(`openapi_old`, `openapi_new`) 기반 관계 설정
- "OpenAPI이기 때문에 연관" 같은 타입 기반 추론

**올바른 예:**
```cypher
// ✅ OK: 구조적 유사성
(DocA)-[:SHARES_PARAMETER {name: "ServiceKey"}]->(DocB)

// ❌ NG: 타입 기반
(DocA:openapi_old)-[:RELATED_TO]->(DocB:openapi_old)
```

---

**작성일**: 2025-12-23
**버전**: 1.0
**다음 단계**: 구현 승인 후 Phase 1 시작

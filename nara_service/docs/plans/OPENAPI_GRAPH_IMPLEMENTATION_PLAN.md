# OpenAPI 그래프 구조 확장 구현 계획

## 📋 Executive Summary

**목표:** OpenAPI 명세 문서의 구조적 정보(엔드포인트, 파라미터, 스키마)를 Neo4j 그래프로 변환하여 API 간 기술적 호환성 분석 및 자동 관계 발견 기능 구축

**기간:** 4주 (28일)
**우선순위:** Medium (현재 시스템 개선, 새 기능 추가)
**리스크 레벨:** Low (기존 기능에 영향 없는 추가 기능)

---

## 📊 현재 상태 (AS-IS)

### 기존 그래프 구조
```cypher
// 현재: 메타데이터만 활용
(Document {api_id, title, description})
  -[:HAS_KEYWORD]->(Keyword {name})
  -[:BELONGS_TO]->(Category {name})
  -[:PROVIDED_BY]->(Provider {name})
  -[:CUSTOM_RELATED_TO]->(Document)
```

**문제점:**
- ❌ OpenAPI 명세의 구조 정보(900+ 라인) 중 90%가 버려짐
- ❌ API 간 기술적 호환성 판단 불가
- ❌ 같은 파라미터/스키마를 가진 API 발견 어려움
- ❌ 서비스 단위 그룹화 불가

### 데이터 분석
```bash
# 현재 refined JSON 파일 분석
backend/storage/refine_data/
├── openapi_old/  # 16개 파일
├── openapi_new/  # 1개 파일
└── standard/     # 115개 파일 (OpenAPI 아님)

총 OpenAPI 문서: 17개
→ 각 문서당 평균 1-3개 엔드포인트
→ 각 엔드포인트당 평균 3-5개 파라미터
→ 총 추출 가능 노드: ~200개 이상
```

---

## 🎯 목표 상태 (TO-BE)

### 확장된 그래프 구조
```cypher
// 신규: API 구조 정보 포함
(Document)
  -[:HAS_ENDPOINT]->(Endpoint {path, method})
    -[:REQUIRES_PARAMETER]->(Parameter {name, type, required})
      -[:HAS_TYPE]->(DataType {name})
    -[:RETURNS_FIELD]->(ResponseField {name, type})
      -[:CONTAINS]->(ResponseField) // 중첩 구조
    -[:PRODUCES]->(Format {name: "XML"|"JSON"})
    -[:USES_METHOD]->(HTTPMethod {name: "GET"|"POST"})
  -[:BELONGS_TO_SERVICE]->(Service {host, base_path})

// 자동 생성 관계
(Doc1)-[:SIMILAR_PARAMETERS {score, common_params}]->(Doc2)
(Doc1)-[:COMPATIBLE_SCHEMA {common_fields}]->(Doc2)
(Doc1)-[:SAME_SERVICE_FAMILY]->(Doc2)
```

### 성공 지표 (KPI)

| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|----------|
| **노드 타입** | 4개 | 12개 | `CALL db.labels()` |
| **관계 타입** | 4개 | 13개 | `CALL db.relationshipTypes()` |
| **총 노드 수** | ~500 | ~700+ | `MATCH (n) RETURN count(n)` |
| **API 간 자동 관계** | 0개 | 20+개 | `MATCH ()-[r:SIMILAR_PARAMETERS]->() RETURN count(r)` |
| **파라미터 재사용률** | - | 70%+ | 같은 이름 파라미터 / 총 파라미터 |

---

## 📅 4주 구현 일정

### Week 1: Foundation (Dec 23-29)
**목표:** Domain Layer 구축 및 기본 스키마 설계

**Day 1-2 (Dec 23-24): 스키마 설계**
- [ ] `graph_schema_openapi.py` 작성
  - 8개 새 노드 라벨 정의
  - 9개 새 관계 타입 정의
- [ ] `models/openapi_models.py` - Pydantic 모델
  - EndpointInfo
  - ParameterInfo
  - ResponseFieldInfo
- [ ] 인덱스 전략 수립

**Day 3-4 (Dec 25-26): Domain Layer - 파서**
- [ ] `domain/openapi/parser.py` - 순수 함수
  - `parse_endpoints()` - 엔드포인트 추출
  - `parse_parameters()` - 파라미터 추출
  - `parse_swagger_schema()` - 스키마 추출
- [ ] 단위 테스트 작성 (pytest)

**Day 5-7 (Dec 27-29): Infrastructure Layer**
- [ ] `infrastructure/neo4j/openapi_executor.py`
  - 노드 생성 쿼리 실행
  - 관계 생성 쿼리 실행
- [ ] 통합 테스트 (Neo4j Test Container)

**Deliverable:**
- ✅ 8개 파일 작성
- ✅ 테스트 커버리지 80%+
- ✅ 1개 샘플 문서 처리 가능

---

### Week 2: Core Builder (Dec 30 - Jan 5)
**목표:** OpenAPI 그래프 빌더 완성 및 기본 관계 생성

**Day 8-10 (Dec 30 - Jan 1): Application Layer**
- [ ] `services/openapi_graph_builder.py`
  - `build_openapi_graph()` - 메인 오케스트레이터
  - `_create_service_node()` - 서비스 노드
  - `_create_endpoints()` - 엔드포인트
  - `_create_parameters()` - 파라미터
- [ ] 에러 핸들링 (Result Pattern)

**Day 11-12 (Jan 2-3): 응답 스키마 처리**
- [ ] `_create_response_schema()` - 스키마 노드
- [ ] 중첩 구조 재귀 처리 (items > item > field)
- [ ] 포맷 노드 생성 (XML, JSON)

**Day 13-14 (Jan 4-5): 통합 및 테스트**
- [ ] 크롤러와 통합
- [ ] 전체 플로우 테스트
- [ ] 에러 케이스 처리

**Deliverable:**
- ✅ OpenAPI 문서 1개 → 그래프 변환 완료
- ✅ 평균 처리 시간 < 2초/문서
- ✅ 통합 테스트 통과

---

### Week 3: Auto Relationships & Migration (Jan 6-12)
**목표:** 자동 관계 생성 및 기존 데이터 마이그레이션

**Day 15-17 (Jan 6-8): 자동 관계 알고리즘**
- [ ] `services/openapi_relationship_analyzer.py`
  - `find_similar_parameters()` - 파라미터 유사도
  - `find_compatible_schemas()` - 스키마 호환성
  - `find_service_family()` - 서비스 그룹
- [ ] 관계 생성 규칙 설정
  - 3개 이상 공통 파라미터 → SIMILAR_PARAMETERS
  - 5개 이상 공통 필드 → COMPATIBLE_SCHEMA

**Day 18-19 (Jan 9-10): 데이터 마이그레이션**
- [ ] `scripts/migrate_openapi_graph.py`
  - 기존 17개 OpenAPI 문서 재처리
  - 진행률 표시
  - 에러 복구
- [ ] 검증 스크립트 작성

**Day 20-21 (Jan 11-12): 쿼리 서비스 확장**
- [ ] `services/query/openapi_query_service.py`
  - `find_compatible_apis()` - 호환 API 검색
  - `find_by_parameter()` - 파라미터 기반 검색
  - `find_by_service()` - 서비스별 조회
- [ ] API 라우터 추가

**Deliverable:**
- ✅ 17개 OpenAPI 문서 그래프 변환 완료
- ✅ 자동 관계 20+개 생성
- ✅ 새 API 엔드포인트 3개 추가

---

### Week 4: Polish & Documentation (Jan 13-19)
**목표:** 최적화, 문서화, UI 통합

**Day 22-23 (Jan 13-14): 성능 최적화**
- [ ] 인덱스 최적화
  - `CREATE INDEX param_name ON :Parameter(name)`
  - `CREATE INDEX endpoint_path ON :Endpoint(path)`
- [ ] 쿼리 프로파일링 (EXPLAIN/PROFILE)
- [ ] 캐시 전략 적용

**Day 24-25 (Jan 15-16): Frontend 통합**
- [ ] API 탐색 UI 개선
  - 엔드포인트 상세 정보 표시
  - 파라미터 목록 표시
  - 호환 API 추천 섹션
- [ ] 그래프 시각화 확장

**Day 26-27 (Jan 17-18): 문서화**
- [ ] API 문서 업데이트 (OpenAPI spec)
- [ ] 사용자 가이드 작성
- [ ] Cypher 쿼리 예시 모음
- [ ] 트러블슈팅 가이드

**Day 28 (Jan 19): 최종 검증**
- [ ] E2E 테스트
- [ ] 성능 벤치마크
- [ ] 배포 준비

**Deliverable:**
- ✅ 전체 시스템 안정화
- ✅ 문서 완성
- ✅ 프로덕션 배포 준비

---

## 🏗️ 상세 구현 스펙

### 1. 스키마 정의

**파일:** `backend/app/graph_schema_openapi.py`

```python
"""
OpenAPI 전용 그래프 스키마

CODING_RULES 준수:
- Rule 7: 문서 타입(openapi_old 등)은 관계 분석 제외
- 구조적 요소(엔드포인트, 파라미터)만 사용
"""

class OpenAPINodeLabel:
    """OpenAPI 노드 라벨 (8개)"""
    ENDPOINT = "Endpoint"              # API 엔드포인트
    PARAMETER = "Parameter"            # 파라미터 (공유 가능)
    RESPONSE_FIELD = "ResponseField"   # 응답 필드 (공유 가능)
    HTTP_METHOD = "HTTPMethod"         # GET, POST, PUT, DELETE
    DATA_TYPE = "DataType"             # string, integer, boolean
    FORMAT = "Format"                  # XML, JSON
    SERVICE = "Service"                # API 서비스 (host 기반)
    TAG = "Tag"                        # Swagger tags


class OpenAPIRelationType:
    """OpenAPI 관계 타입 (9개 + 3개 자동)"""
    # Document → 구조 요소
    HAS_ENDPOINT = "HAS_ENDPOINT"              # Doc → Endpoint
    BELONGS_TO_SERVICE = "BELONGS_TO_SERVICE"  # Doc → Service

    # Endpoint → 속성
    REQUIRES_PARAMETER = "REQUIRES_PARAMETER"  # Endpoint → Parameter (required=true)
    OPTIONAL_PARAMETER = "OPTIONAL_PARAMETER"  # Endpoint → Parameter (required=false)
    RETURNS_FIELD = "RETURNS_FIELD"            # Endpoint → ResponseField
    USES_METHOD = "USES_METHOD"                # Endpoint → HTTPMethod
    PRODUCES = "PRODUCES"                      # Endpoint → Format
    CONSUMES = "CONSUMES"                      # Endpoint → Format
    HAS_TAG = "HAS_TAG"                        # Endpoint → Tag

    # 타입 관계
    HAS_TYPE = "HAS_TYPE"                      # Parameter/Field → DataType

    # 중첩 구조
    CONTAINS = "CONTAINS"                      # ResponseField → ResponseField

    # 자동 생성 관계 (시스템)
    SIMILAR_PARAMETERS = "SIMILAR_PARAMETERS"  # Doc ↔ Doc (3+ 공통 파라미터)
    COMPATIBLE_SCHEMA = "COMPATIBLE_SCHEMA"    # Doc ↔ Doc (5+ 공통 필드)
    SAME_SERVICE_FAMILY = "SAME_SERVICE_FAMILY" # Doc ↔ Doc (같은 Service)


class OpenAPIPropKey:
    """OpenAPI 속성 키"""
    # Endpoint
    PATH = "path"
    METHOD = "method"
    DESCRIPTION = "description"
    OPERATION_ID = "operation_id"

    # Parameter
    NAME = "name"
    TYPE = "type"
    REQUIRED = "required"
    IN = "in"  # query, path, header, body

    # ResponseField
    FIELD_NAME = "name"
    FIELD_TYPE = "type"
    FIELD_DESCRIPTION = "description"

    # Service
    HOST = "host"
    BASE_PATH = "base_path"
    SCHEMES = "schemes"  # http, https

    # 자동 관계 속성
    COMMON_PARAMS = "common_parameters"
    COMMON_FIELDS = "common_fields"
    SIMILARITY_SCORE = "similarity_score"
```

---

### 2. Pydantic 모델

**파일:** `backend/app/domain/openapi/models.py`

```python
"""
OpenAPI 도메인 모델

CODING_RULES 준수:
- Rule 4: Type Safety - Pydantic으로 타입 명시
- Rule 1: DRY - 단일 진실 공급원
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from enum import Enum


class HTTPMethod(str, Enum):
    """HTTP 메서드"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class ParameterLocation(str, Enum):
    """파라미터 위치"""
    QUERY = "query"
    PATH = "path"
    HEADER = "header"
    BODY = "body"


class ParameterInfo(BaseModel):
    """파라미터 정보"""
    name: str = Field(..., min_length=1)
    type: str = Field(default="string")
    required: bool = Field(default=False)
    description: str = Field(default="")
    location: ParameterLocation = Field(default=ParameterLocation.QUERY)

    @validator("name")
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Parameter name cannot be empty")
        return v.strip()


class ResponseFieldInfo(BaseModel):
    """응답 필드 정보"""
    name: str
    type: str
    description: str = ""
    nested_fields: List['ResponseFieldInfo'] = Field(default_factory=list)

    class Config:
        # 자기 참조 허용 (중첩 구조)
        arbitrary_types_allowed = True


class EndpointInfo(BaseModel):
    """엔드포인트 정보"""
    path: str = Field(..., min_length=1)
    method: HTTPMethod
    operation_id: Optional[str] = None
    description: str = ""
    parameters: List[ParameterInfo] = Field(default_factory=list)
    response_fields: List[ResponseFieldInfo] = Field(default_factory=list)
    produces: List[str] = Field(default_factory=list)  # ["application/xml", "application/json"]
    consumes: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class ServiceInfo(BaseModel):
    """API 서비스 정보"""
    host: str = Field(..., min_length=1)
    base_path: str = Field(default="")
    schemes: List[str] = Field(default_factory=lambda: ["https"])


class OpenAPIDocument(BaseModel):
    """OpenAPI 문서 전체 구조"""
    api_id: str
    service: ServiceInfo
    endpoints: List[EndpointInfo]


# 자기 참조 업데이트
ResponseFieldInfo.update_forward_refs()
```

---

### 3. Domain Layer - Parser (순수 함수)

**파일:** `backend/app/domain/openapi/parser.py`

```python
"""
OpenAPI 명세 파서 (순수 함수)

CODING_RULES 준수:
- Rule 1: FP First - 모든 함수는 순수 함수
- Rule 4: Type Safety - 명시적 타입
- 부작용 없음, 테스트 용이
"""
import logging
from typing import Dict, Any, List, Optional
from app.domain.openapi.models import (
    EndpointInfo, ParameterInfo, ResponseFieldInfo,
    ServiceInfo, OpenAPIDocument, HTTPMethod, ParameterLocation
)

logger = logging.getLogger(__name__)


class OpenAPIParser:
    """OpenAPI 명세 파서 (Static Methods Only)"""

    @staticmethod
    def parse_document(doc_data: Dict[str, Any]) -> Optional[OpenAPIDocument]:
        """
        refined JSON → OpenAPIDocument 변환 (순수 함수)

        Args:
            doc_data: refined JSON 전체

        Returns:
            OpenAPIDocument or None (API 문서가 아닌 경우)

        Design Decision:
        - 입력만으로 출력 결정 (순수 함수)
        - I/O 없음, 전역 상태 변경 없음
        - 테스트 용이
        """
        content = doc_data.get("content", {})

        # API 문서가 아니면 None 반환
        if content.get("data_type") != "API":
            return None

        api_id = doc_data.get("api_id")

        # 서비스 정보 추출
        service = OpenAPIParser._parse_service(doc_data)

        # 엔드포인트 추출
        endpoints = OpenAPIParser._parse_endpoints(content)

        return OpenAPIDocument(
            api_id=api_id,
            service=service,
            endpoints=endpoints
        )

    @staticmethod
    def _parse_service(doc_data: Dict[str, Any]) -> ServiceInfo:
        """
        서비스 정보 추출 (순수 함수)

        swagger_json.host, basePath 사용
        """
        swagger = doc_data.get("swagger_json", {})

        host = swagger.get("host", "")
        base_path = swagger.get("basePath", "")
        schemes = swagger.get("schemes", ["https"])

        return ServiceInfo(
            host=host,
            base_path=base_path,
            schemes=schemes
        )

    @staticmethod
    def _parse_endpoints(content: Dict[str, Any]) -> List[EndpointInfo]:
        """
        엔드포인트 목록 추출 (순수 함수)

        content.endpoints 배열 파싱
        """
        endpoints_data = content.get("endpoints", [])
        endpoints = []

        for ep_data in endpoints_data:
            try:
                endpoint = OpenAPIParser._parse_single_endpoint(ep_data)
                endpoints.append(endpoint)
            except Exception as e:
                logger.warning(f"Failed to parse endpoint: {e}")
                continue

        return endpoints

    @staticmethod
    def _parse_single_endpoint(ep_data: Dict[str, Any]) -> EndpointInfo:
        """
        단일 엔드포인트 파싱 (순수 함수)
        """
        path = ep_data.get("path", "")
        method_str = ep_data.get("method", "GET").upper()

        # Enum 변환
        try:
            method = HTTPMethod(method_str)
        except ValueError:
            method = HTTPMethod.GET

        description = ep_data.get("description", "")

        # 파라미터 파싱
        parameters = OpenAPIParser._parse_parameters(ep_data.get("parameters", []))

        # 응답 필드는 swagger_json에서 추출 필요 (복잡)
        # 일단 빈 리스트로 시작
        response_fields = []

        # produces/consumes (content.endpoints에는 없고 swagger_json에 있음)
        produces = []
        consumes = []

        # tags
        tags = ep_data.get("tags", [])

        return EndpointInfo(
            path=path,
            method=method,
            description=description,
            parameters=parameters,
            response_fields=response_fields,
            produces=produces,
            consumes=consumes,
            tags=tags
        )

    @staticmethod
    def _parse_parameters(params_data: List[Dict[str, Any]]) -> List[ParameterInfo]:
        """
        파라미터 목록 파싱 (순수 함수)
        """
        parameters = []

        for param_data in params_data:
            try:
                name = param_data.get("name", "")
                param_type = param_data.get("type", "string")
                required = param_data.get("required", False)
                description = param_data.get("description", "")
                location_str = param_data.get("in", "query")

                # Enum 변환
                try:
                    location = ParameterLocation(location_str)
                except ValueError:
                    location = ParameterLocation.QUERY

                parameters.append(ParameterInfo(
                    name=name,
                    type=param_type,
                    required=required,
                    description=description,
                    location=location
                ))
            except Exception as e:
                logger.warning(f"Failed to parse parameter: {e}")
                continue

        return parameters

    @staticmethod
    def _parse_response_schema(
        swagger_paths: Dict[str, Any],
        path: str,
        method: str
    ) -> List[ResponseFieldInfo]:
        """
        응답 스키마 파싱 (순수 함수, 복잡)

        swagger_json.paths[path][method].responses["200"].schema 파싱
        중첩 구조를 재귀적으로 처리
        """
        # TODO: Week 2에서 구현
        return []

    @staticmethod
    def _parse_nested_fields(
        schema: Dict[str, Any],
        parent_name: str = ""
    ) -> List[ResponseFieldInfo]:
        """
        중첩 필드 재귀 파싱 (순수 함수)

        items > item > baekduId 같은 구조
        """
        # TODO: Week 2에서 구현
        return []
```

---

### 4. Infrastructure Layer - Query Executor

**파일:** `backend/app/infrastructure/neo4j/openapi_executor.py`

```python
"""
OpenAPI 그래프 Neo4j 실행기

CODING_RULES 준수:
- Rule 2: Infrastructure Layer - I/O만 담당
- 쿼리 생성은 Domain, 실행만 여기서
"""
import logging
from typing import Dict, Any, List
from app.services.neo4j_service import neo4j_service
from app.graph_schema_openapi import (
    OpenAPINodeLabel,
    OpenAPIRelationType,
    OpenAPIPropKey
)

logger = logging.getLogger(__name__)


class OpenAPIGraphExecutor:
    """OpenAPI 그래프 Neo4j 실행기 (Infrastructure)"""

    def __init__(self, neo4j_service):
        self.neo4j_service = neo4j_service

    def create_service_node(
        self,
        api_id: str,
        host: str,
        base_path: str,
        schemes: List[str]
    ) -> None:
        """
        서비스 노드 생성 및 문서 연결

        Design Decision:
        - 같은 host는 MERGE하여 재사용
        - 여러 문서가 같은 Service 노드 공유
        """
        query = f"""
        MATCH (d:Document {{api_id: $api_id}})
        MERGE (s:{OpenAPINodeLabel.SERVICE} {{host: $host}})
        ON CREATE SET
            s.{OpenAPIPropKey.BASE_PATH} = $base_path,
            s.{OpenAPIPropKey.SCHEMES} = $schemes
        MERGE (d)-[:{OpenAPIRelationType.BELONGS_TO_SERVICE}]->(s)
        """

        try:
            with self.neo4j_service.get_session() as session:
                session.run(
                    query,
                    api_id=api_id,
                    host=host,
                    base_path=base_path,
                    schemes=schemes
                )
            logger.debug(f"Service node created: {host}")
        except Exception as e:
            logger.error(f"Error creating service node: {e}")
            raise

    def create_endpoint_node(
        self,
        api_id: str,
        endpoint_id: str,
        path: str,
        method: str,
        description: str
    ) -> None:
        """
        엔드포인트 노드 생성 및 연결

        엔드포인트 ID = {api_id}_{method}_{path}
        """
        query = f"""
        MATCH (d:Document {{api_id: $api_id}})
        MERGE (ep:{OpenAPINodeLabel.ENDPOINT} {{id: $endpoint_id}})
        ON CREATE SET
            ep.{OpenAPIPropKey.PATH} = $path,
            ep.{OpenAPIPropKey.METHOD} = $method,
            ep.{OpenAPIPropKey.DESCRIPTION} = $description
        MERGE (d)-[:{OpenAPIRelationType.HAS_ENDPOINT}]->(ep)

        // HTTP Method 노드
        MERGE (m:{OpenAPINodeLabel.HTTP_METHOD} {{name: $method}})
        MERGE (ep)-[:{OpenAPIRelationType.USES_METHOD}]->(m)
        """

        try:
            with self.neo4j_service.get_session() as session:
                session.run(
                    query,
                    api_id=api_id,
                    endpoint_id=endpoint_id,
                    path=path,
                    method=method,
                    description=description
                )
            logger.debug(f"Endpoint node created: {endpoint_id}")
        except Exception as e:
            logger.error(f"Error creating endpoint node: {e}")
            raise

    def create_parameter_node(
        self,
        endpoint_id: str,
        name: str,
        param_type: str,
        required: bool,
        description: str,
        location: str
    ) -> None:
        """
        파라미터 노드 생성 및 연결

        Design Decision:
        - 파라미터는 name으로 MERGE (여러 API가 공유)
        - 예: "ServiceKey"는 모든 API에서 같은 노드 재사용
        """
        rel_type = (
            OpenAPIRelationType.REQUIRES_PARAMETER if required
            else OpenAPIRelationType.OPTIONAL_PARAMETER
        )

        query = f"""
        MATCH (ep:{OpenAPINodeLabel.ENDPOINT} {{id: $endpoint_id}})

        // 파라미터 노드 (name으로 MERGE - 공유 가능)
        MERGE (p:{OpenAPINodeLabel.PARAMETER} {{name: $name}})
        ON CREATE SET
            p.{OpenAPIPropKey.TYPE} = $param_type,
            p.{OpenAPIPropKey.DESCRIPTION} = $description,
            p.{OpenAPIPropKey.IN} = $location

        // 관계 생성 (required 여부에 따라)
        MERGE (ep)-[:{rel_type}]->(p)

        // DataType 노드
        MERGE (dt:{OpenAPINodeLabel.DATA_TYPE} {{name: $param_type}})
        MERGE (p)-[:{OpenAPIRelationType.HAS_TYPE}]->(dt)
        """

        try:
            with self.neo4j_service.get_session() as session:
                session.run(
                    query,
                    endpoint_id=endpoint_id,
                    name=name,
                    param_type=param_type,
                    location=location
                )
            logger.debug(f"Parameter node created: {name}")
        except Exception as e:
            logger.error(f"Error creating parameter node: {e}")
            raise

    def create_format_relationships(
        self,
        endpoint_id: str,
        produces: List[str],
        consumes: List[str]
    ) -> None:
        """
        포맷 노드 및 관계 생성 (PRODUCES, CONSUMES)
        """
        # produces (응답 포맷)
        for fmt in produces:
            fmt_name = self._extract_format_name(fmt)
            if not fmt_name:
                continue

            query = f"""
            MATCH (ep:{OpenAPINodeLabel.ENDPOINT} {{id: $endpoint_id}})
            MERGE (f:{OpenAPINodeLabel.FORMAT} {{name: $fmt_name}})
            MERGE (ep)-[:{OpenAPIRelationType.PRODUCES}]->(f)
            """

            try:
                with self.neo4j_service.get_session() as session:
                    session.run(query, endpoint_id=endpoint_id, fmt_name=fmt_name)
            except Exception as e:
                logger.error(f"Error creating produces relationship: {e}")

        # consumes (요청 포맷)
        for fmt in consumes:
            fmt_name = self._extract_format_name(fmt)
            if not fmt_name:
                continue

            query = f"""
            MATCH (ep:{OpenAPINodeLabel.ENDPOINT} {{id: $endpoint_id}})
            MERGE (f:{OpenAPINodeLabel.FORMAT} {{name: $fmt_name}})
            MERGE (ep)-[:{OpenAPIRelationType.CONSUMES}]->(f)
            """

            try:
                with self.neo4j_service.get_session() as session:
                    session.run(query, endpoint_id=endpoint_id, fmt_name=fmt_name)
            except Exception as e:
                logger.error(f"Error creating consumes relationship: {e}")

    def _extract_format_name(self, content_type: str) -> str:
        """
        Content-Type에서 포맷명 추출

        "application/xml" → "XML"
        "application/json" → "JSON"
        """
        if not content_type:
            return ""

        content_type = content_type.lower()

        if "xml" in content_type:
            return "XML"
        elif "json" in content_type:
            return "JSON"
        else:
            return content_type.split("/")[-1].upper()
```

---

### 5. Application Layer - Builder

**파일:** `backend/app/services/openapi_graph_builder.py`

```python
"""
OpenAPI 그래프 빌더 (Application Layer)

CODING_RULES 준수:
- Rule 2: Application Layer - 유스케이스 오케스트레이션
- Domain 파서 + Infrastructure 실행기 조합
"""
import logging
from typing import Dict, Any
from app.domain.openapi.parser import OpenAPIParser
from app.domain.openapi.models import OpenAPIDocument
from app.infrastructure.neo4j.openapi_executor import OpenAPIGraphExecutor
from app.services.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)


class OpenAPIGraphBuilder:
    """
    OpenAPI 문서 → Neo4j 그래프 변환 (Application)

    책임: 파싱과 실행의 오케스트레이션
    """

    def __init__(self, neo4j_service):
        self.executor = OpenAPIGraphExecutor(neo4j_service)

    def build(self, doc_data: Dict[str, Any]) -> bool:
        """
        OpenAPI 문서를 그래프로 변환

        Args:
            doc_data: refined JSON 전체

        Returns:
            성공 여부

        Design Decision:
        - Domain 파서로 구조 추출 (순수 함수)
        - Infrastructure 실행기로 Neo4j 저장 (부작용)
        """
        try:
            # 1. Domain: 파싱 (순수 함수)
            openapi_doc = OpenAPIParser.parse_document(doc_data)

            if not openapi_doc:
                logger.debug(f"Not an OpenAPI document: {doc_data.get('api_id')}")
                return False

            # 2. Infrastructure: 저장 (부작용)
            self._save_to_graph(openapi_doc)

            logger.info(f"OpenAPI graph built for {openapi_doc.api_id}")
            return True

        except Exception as e:
            logger.error(f"Error building OpenAPI graph: {e}", exc_info=True)
            return False

    def _save_to_graph(self, doc: OpenAPIDocument) -> None:
        """
        파싱된 OpenAPIDocument를 Neo4j에 저장

        순서:
        1. Service 노드
        2. Endpoint 노드들
        3. Parameter 노드들
        4. Format 관계들
        """
        # 1. 서비스 노드
        self.executor.create_service_node(
            api_id=doc.api_id,
            host=doc.service.host,
            base_path=doc.service.base_path,
            schemes=doc.service.schemes
        )

        # 2. 각 엔드포인트 처리
        for endpoint in doc.endpoints:
            endpoint_id = f"{doc.api_id}_{endpoint.method.value}_{endpoint.path}"

            # 엔드포인트 노드
            self.executor.create_endpoint_node(
                api_id=doc.api_id,
                endpoint_id=endpoint_id,
                path=endpoint.path,
                method=endpoint.method.value,
                description=endpoint.description
            )

            # 파라미터 노드들
            for param in endpoint.parameters:
                self.executor.create_parameter_node(
                    endpoint_id=endpoint_id,
                    name=param.name,
                    param_type=param.type,
                    required=param.required,
                    description=param.description,
                    location=param.location.value
                )

            # 포맷 관계
            if endpoint.produces or endpoint.consumes:
                self.executor.create_format_relationships(
                    endpoint_id=endpoint_id,
                    produces=endpoint.produces,
                    consumes=endpoint.consumes
                )

            # TODO: Week 2 - 응답 스키마
```

---

### 6. 마이그레이션 스크립트

**파일:** `backend/scripts/migrate_openapi_graph.py`

```python
"""
기존 OpenAPI 문서 재처리

17개 OpenAPI 문서를 그래프로 변환
"""
import sys
import os
import json
import glob
from pathlib import Path
from tqdm import tqdm

# 프로젝트 루트
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.neo4j_service import neo4j_service
from app.services.openapi_graph_builder import OpenAPIGraphBuilder
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """메인 마이그레이션 함수"""
    print("="*80)
    print("OpenAPI 그래프 마이그레이션 시작")
    print("="*80)

    builder = OpenAPIGraphBuilder(neo4j_service)

    # refined JSON 파일 찾기
    base_path = project_root / "storage" / "refine_data"

    openapi_paths = []
    openapi_paths.extend(glob.glob(str(base_path / "openapi_old" / "*.json")))
    openapi_paths.extend(glob.glob(str(base_path / "openapi_new" / "*.json")))

    print(f"\n총 {len(openapi_paths)}개 OpenAPI 문서 발견\n")

    success_count = 0
    fail_count = 0
    skip_count = 0

    # 진행률 표시
    for file_path in tqdm(openapi_paths, desc="Processing"):
        try:
            # JSON 로드
            with open(file_path, 'r', encoding='utf-8') as f:
                doc_data = json.load(f)

            api_id = doc_data.get("api_id")

            # 그래프 변환
            if builder.build(doc_data):
                success_count += 1
            else:
                skip_count += 1

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            fail_count += 1
            continue

    # 결과 출력
    print("\n" + "="*80)
    print("마이그레이션 완료")
    print("="*80)
    print(f"✅ 성공: {success_count}")
    print(f"⏭️  스킵: {skip_count}")
    print(f"❌ 실패: {fail_count}")
    print(f"📊 총: {len(openapi_paths)}")

    # 그래프 통계
    print("\n그래프 통계:")
    print_graph_stats()


def print_graph_stats():
    """그래프 통계 출력"""
    queries = {
        "Service 노드": "MATCH (s:Service) RETURN count(s) as cnt",
        "Endpoint 노드": "MATCH (e:Endpoint) RETURN count(e) as cnt",
        "Parameter 노드": "MATCH (p:Parameter) RETURN count(p) as cnt",
        "Format 노드": "MATCH (f:Format) RETURN count(f) as cnt",
    }

    with neo4j_service.get_session() as session:
        for label, query in queries.items():
            result = session.run(query)
            count = result.single()["cnt"]
            print(f"  - {label}: {count}")


if __name__ == "__main__":
    main()
```

---

## 🧪 테스트 전략

### 단위 테스트 (Domain Layer)

**파일:** `backend/tests/domain/test_openapi_parser.py`

```python
import pytest
from app.domain.openapi.parser import OpenAPIParser
from app.domain.openapi.models import HTTPMethod


def test_parse_document_valid():
    """정상 OpenAPI 문서 파싱"""
    doc_data = {
        "api_id": "15002731",
        "content": {
            "data_type": "API",
            "endpoints": [
                {
                    "method": "GET",
                    "path": "/gettrailservice",
                    "parameters": [
                        {
                            "name": "ServiceKey",
                            "type": "string",
                            "required": True
                        }
                    ]
                }
            ]
        },
        "swagger_json": {
            "host": "openapi.forest.go.kr",
            "basePath": "/openapi/service"
        }
    }

    result = OpenAPIParser.parse_document(doc_data)

    assert result is not None
    assert result.api_id == "15002731"
    assert result.service.host == "openapi.forest.go.kr"
    assert len(result.endpoints) == 1
    assert result.endpoints[0].method == HTTPMethod.GET
    assert len(result.endpoints[0].parameters) == 1
    assert result.endpoints[0].parameters[0].name == "ServiceKey"


def test_parse_document_not_api():
    """API가 아닌 문서는 None 반환"""
    doc_data = {
        "api_id": "15021098",
        "content": {
            "data_type": "FILE"
        }
    }

    result = OpenAPIParser.parse_document(doc_data)
    assert result is None


def test_parse_parameters():
    """파라미터 파싱"""
    params_data = [
        {"name": "pageNo", "type": "integer", "required": False},
        {"name": "numOfRows", "type": "integer", "required": False}
    ]

    result = OpenAPIParser._parse_parameters(params_data)

    assert len(result) == 2
    assert result[0].name == "pageNo"
    assert result[0].type == "integer"
    assert result[0].required is False
```

---

### 통합 테스트

**파일:** `backend/tests/integration/test_openapi_graph_builder.py`

```python
import pytest
from app.services.openapi_graph_builder import OpenAPIGraphBuilder
from app.services.neo4j_service import neo4j_service


@pytest.fixture(scope="function")
def clean_neo4j():
    """각 테스트 전후로 Neo4j 정리"""
    # 테스트 전: 정리
    yield
    # 테스트 후: 정리
    with neo4j_service.get_session() as session:
        session.run("MATCH (n:Service) DETACH DELETE n")
        session.run("MATCH (n:Endpoint) DETACH DELETE n")
        session.run("MATCH (n:Parameter) DETACH DELETE n")


def test_build_complete_flow(clean_neo4j):
    """전체 플로우 테스트"""
    # Given
    doc_data = load_sample_openapi_doc()
    builder = OpenAPIGraphBuilder(neo4j_service)

    # When
    result = builder.build(doc_data)

    # Then
    assert result is True

    # 검증: Neo4j에서 노드 확인
    with neo4j_service.get_session() as session:
        # Service 노드 존재
        service_count = session.run(
            "MATCH (s:Service {host: 'openapi.forest.go.kr'}) RETURN count(s) as cnt"
        ).single()["cnt"]
        assert service_count == 1

        # Endpoint 노드 존재
        ep_count = session.run(
            "MATCH (e:Endpoint) RETURN count(e) as cnt"
        ).single()["cnt"]
        assert ep_count > 0

        # Parameter 노드 존재
        param_count = session.run(
            "MATCH (p:Parameter {name: 'ServiceKey'}) RETURN count(p) as cnt"
        ).single()["cnt"]
        assert param_count == 1
```

---

## 🔐 리스크 관리

### 식별된 리스크

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|-----------|
| **응답 스키마 파싱 복잡도** | 높음 | 중간 | Week 2에 집중, 실패 시 간단한 구조만 먼저 처리 |
| **Neo4j 성능 저하** | 중간 | 높음 | 인덱스 최적화, 배치 처리, 프로파일링 |
| **기존 데이터 손상** | 낮음 | 높음 | 백업 필수, Dry-run 모드, 롤백 계획 |
| **마이그레이션 시간 초과** | 낮음 | 중간 | 배치 크기 조정, 비동기 처리 |

### 롤백 계획

```cypher
// 롤백: OpenAPI 관련 노드/관계 전체 삭제
MATCH (n:Service) DETACH DELETE n;
MATCH (n:Endpoint) DETACH DELETE n;
MATCH (n:Parameter) DETACH DELETE n;
MATCH (n:ResponseField) DETACH DELETE n;
MATCH (n:Format) DETACH DELETE n;
MATCH (n:HTTPMethod) DETACH DELETE n;
MATCH (n:DataType) DETACH DELETE n;

// 자동 생성 관계만 삭제
MATCH ()-[r:SIMILAR_PARAMETERS]->() DELETE r;
MATCH ()-[r:COMPATIBLE_SCHEMA]->() DELETE r;
MATCH ()-[r:SAME_SERVICE_FAMILY]->() DELETE r;
```

---

## ✅ 체크리스트

### Week 1 (Foundation)
- [ ] `graph_schema_openapi.py` - 8개 노드, 12개 관계 정의
- [ ] `domain/openapi/models.py` - 5개 Pydantic 모델
- [ ] `domain/openapi/parser.py` - 순수 함수 파서
- [ ] `infrastructure/neo4j/openapi_executor.py` - I/O 실행기
- [ ] 단위 테스트 10+ 케이스
- [ ] 통합 테스트 5+ 케이스

### Week 2 (Core Builder)
- [ ] `services/openapi_graph_builder.py` - 빌더 완성
- [ ] 응답 스키마 파싱 구현
- [ ] 포맷/프로토콜 노드 생성
- [ ] 크롤러 통합
- [ ] E2E 테스트

### Week 3 (Auto Relationships & Migration)
- [ ] `services/openapi_relationship_analyzer.py` - 유사도 알고리즘
- [ ] 자동 관계 생성 (SIMILAR_PARAMETERS 등)
- [ ] `scripts/migrate_openapi_graph.py` - 마이그레이션
- [ ] 17개 문서 전체 처리
- [ ] 검증 스크립트
- [ ] `services/query/openapi_query_service.py` - 쿼리 서비스
- [ ] API 라우터 3개 추가

### Week 4 (Polish & Documentation)
- [ ] 인덱스 최적화 (6개 인덱스 추가)
- [ ] 쿼리 프로파일링 및 개선
- [ ] Frontend UI 통합
- [ ] API 문서 업데이트
- [ ] 사용자 가이드 작성
- [ ] Cypher 쿼리 예시 모음
- [ ] 최종 E2E 테스트
- [ ] 성능 벤치마크
- [ ] 프로덕션 배포

---

## 📝 성공 기준

### Must Have (필수)
- ✅ 17개 OpenAPI 문서 → 그래프 변환 100%
- ✅ 자동 관계 20+개 생성
- ✅ 새 API 엔드포인트 3개 동작
- ✅ 테스트 커버리지 70%+
- ✅ 기존 기능 정상 동작 (회귀 없음)

### Should Have (권장)
- ✅ 응답 스키마 파싱 (중첩 구조)
- ✅ Frontend UI 통합
- ✅ 성능: 문서당 처리 시간 < 3초

### Could Have (선택)
- ⭐ Tag 노드 및 관계
- ⭐ 복잡한 응답 스키마 (3단계 이상 중첩)
- ⭐ 실시간 API 문서 동기화

---

**작성일**: 2025-12-23
**버전**: 1.0
**작성자**: Development Team
**승인 대기**: Product Owner

---

**다음 단계:**
1. ✅ 이 플랜 검토 및 승인
2. ✅ Week 1 Day 1 시작
3. ✅ Daily 진행률 체크

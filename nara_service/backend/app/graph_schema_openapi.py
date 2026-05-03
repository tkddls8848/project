"""
OpenAPI 전용 Neo4j Graph Schema Definitions

OpenAPI/Swagger 명세 문서의 구조적 정보(엔드포인트, 파라미터, 스키마)를
Neo4j 그래프로 변환하기 위한 스키마 정의

CODING_RULES 준수:
- Rule 7: 문서 타입(openapi_old, openapi_new 등)은 관계 분석에서 제외
- 구조적 요소(엔드포인트, 파라미터, 응답 스키마)만 사용하여 관계 설정
"""


# ==========================================
# 1. Node Labels (OpenAPI 노드 라벨)
# ==========================================
class OpenAPINodeLabel:
    """OpenAPI 전용 노드 라벨 (8개)"""

    # API 구조 요소
    ENDPOINT = "Endpoint"              # API 엔드포인트 (path + method 조합)
    PARAMETER = "Parameter"            # 요청 파라미터 (여러 API가 공유 가능)
    RESPONSE_FIELD = "ResponseField"   # 응답 필드 (여러 API가 공유 가능)

    # 메타 노드 (공유 리소스)
    HTTP_METHOD = "HTTPMethod"         # HTTP 메서드 (GET, POST, PUT, DELETE)
    DATA_TYPE = "DataType"             # 데이터 타입 (string, integer, boolean)
    FORMAT = "Format"                  # 데이터 포맷 (XML, JSON)
    SERVICE = "Service"                # API 서비스 (host 기반 그룹)
    TAG = "Tag"                        # Swagger 태그 (카테고리)


# ==========================================
# 2. Relationship Types (OpenAPI 관계 타입)
# ==========================================
class OpenAPIRelationType:
    """OpenAPI 관계 타입 (12개)"""

    # Document → 구조 요소 (문서와 API 요소 연결)
    HAS_ENDPOINT = "HAS_ENDPOINT"              # Document → Endpoint
    BELONGS_TO_SERVICE = "BELONGS_TO_SERVICE"  # Document → Service

    # Endpoint → 속성 (엔드포인트 상세 정보)
    REQUIRES_PARAMETER = "REQUIRES_PARAMETER"  # Endpoint → Parameter (required=true)
    OPTIONAL_PARAMETER = "OPTIONAL_PARAMETER"  # Endpoint → Parameter (required=false)
    RETURNS_FIELD = "RETURNS_FIELD"            # Endpoint → ResponseField
    USES_METHOD = "USES_METHOD"                # Endpoint → HTTPMethod
    PRODUCES = "PRODUCES"                      # Endpoint → Format (응답 포맷)
    CONSUMES = "CONSUMES"                      # Endpoint → Format (요청 포맷)
    HAS_TAG = "HAS_TAG"                        # Endpoint → Tag

    # 타입 관계 (데이터 타입 정의)
    HAS_TYPE = "HAS_TYPE"                      # Parameter/ResponseField → DataType

    # 중첩 구조 (응답 스키마의 계층 구조)
    CONTAINS = "CONTAINS"                      # ResponseField → ResponseField

    # 자동 생성 관계 (시스템이 자동으로 발견하는 관계)
    SIMILAR_PARAMETERS = "SIMILAR_PARAMETERS"  # Document ↔ Document (3+ 공통 파라미터)
    COMPATIBLE_SCHEMA = "COMPATIBLE_SCHEMA"    # Document ↔ Document (5+ 공통 응답 필드)
    SAME_SERVICE_FAMILY = "SAME_SERVICE_FAMILY" # Document ↔ Document (같은 Service 노드 공유)


# ==========================================
# 3. Property Keys (OpenAPI 속성 키)
# ==========================================
class OpenAPIPropKey:
    """OpenAPI 속성 키"""

    # Common
    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"

    # Endpoint
    PATH = "path"                      # API 경로 (예: /gettrailservice)
    METHOD = "method"                  # HTTP 메서드
    OPERATION_ID = "operation_id"      # Swagger operationId

    # Parameter
    PARAM_NAME = "name"                # 파라미터 이름 (예: ServiceKey, pageNo)
    PARAM_TYPE = "type"                # 파라미터 타입 (string, integer)
    REQUIRED = "required"              # 필수 여부 (true/false)
    IN = "in"                          # 파라미터 위치 (query, path, header, body)

    # ResponseField
    FIELD_NAME = "name"                # 필드 이름
    FIELD_TYPE = "type"                # 필드 타입
    FIELD_DESCRIPTION = "description"  # 필드 설명

    # Service
    HOST = "host"                      # API 호스트 (예: openapi.forest.go.kr)
    BASE_PATH = "base_path"            # API 기본 경로
    SCHEMES = "schemes"                # 프로토콜 (http, https)

    # 자동 생성 관계 속성
    COMMON_PARAMS = "common_parameters"       # 공통 파라미터 목록 (JSON array)
    COMMON_FIELDS = "common_fields"           # 공통 응답 필드 목록 (JSON array)
    SIMILARITY_SCORE = "similarity_score"     # 유사도 점수 (0.0 - 1.0)


# ==========================================
# 4. Schema Constraints (제약 조건 - 참조용)
# ==========================================
# 실제 적용은 코드에서 수행하지만, 구조 파악을 위해 명시
OPENAPI_CONSTRAINTS = [
    # (Label, Property) - Unique Key
    (OpenAPINodeLabel.ENDPOINT, OpenAPIPropKey.ID),          # 엔드포인트 ID는 고유
    (OpenAPINodeLabel.PARAMETER, OpenAPIPropKey.PARAM_NAME), # 파라미터 이름으로 공유
    (OpenAPINodeLabel.SERVICE, OpenAPIPropKey.HOST),         # 서비스 호스트는 고유
    (OpenAPINodeLabel.HTTP_METHOD, OpenAPIPropKey.NAME),     # HTTP 메서드 이름 고유
    (OpenAPINodeLabel.DATA_TYPE, OpenAPIPropKey.NAME),       # 데이터 타입 이름 고유
    (OpenAPINodeLabel.FORMAT, OpenAPIPropKey.NAME),          # 포맷 이름 고유
    (OpenAPINodeLabel.TAG, OpenAPIPropKey.NAME),             # 태그 이름 고유
]


# ==========================================
# 5. Index Recommendations (인덱스 권장사항)
# ==========================================
# Week 4에서 성능 최적화 시 적용할 인덱스 목록
RECOMMENDED_INDEXES = [
    # 검색 성능 향상
    "CREATE INDEX endpoint_path IF NOT EXISTS FOR (e:Endpoint) ON (e.path)",
    "CREATE INDEX parameter_name IF NOT EXISTS FOR (p:Parameter) ON (p.name)",
    "CREATE INDEX service_host IF NOT EXISTS FOR (s:Service) ON (s.host)",

    # 관계 필터링 성능 향상
    "CREATE INDEX param_type IF NOT EXISTS FOR (p:Parameter) ON (p.type)",
    "CREATE INDEX param_required IF NOT EXISTS FOR (p:Parameter) ON (p.required)",

    # 자동 관계 생성 성능 향상
    "CREATE INDEX similarity_score IF NOT EXISTS FOR ()-[r:SIMILAR_PARAMETERS]-() ON (r.similarity_score)",
]

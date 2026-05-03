"""
OpenAPI 도메인 모델

OpenAPI/Swagger 명세의 구조를 표현하는 Pydantic 모델

CODING_RULES 준수:
- Rule 4: Type Safety - Pydantic으로 타입 명시, Dict[str, Any] 최소화
- Rule 1: DRY - 단일 진실 공급원
- FP First - 불변 데이터 구조
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum


# ==========================================
# 1. Enums (열거형)
# ==========================================
class HTTPMethod(str, Enum):
    """HTTP 메서드"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class ParameterLocation(str, Enum):
    """파라미터 위치"""
    QUERY = "query"      # URL 쿼리 파라미터 (?key=value)
    PATH = "path"        # URL 경로 파라미터 (/users/{id})
    HEADER = "header"    # HTTP 헤더
    BODY = "body"        # 요청 본문
    FORMDATA = "formData"  # Form 데이터


# ==========================================
# 2. Value Objects (값 객체)
# ==========================================
class ParameterInfo(BaseModel):
    """
    파라미터 정보

    여러 API에서 공유 가능한 파라미터를 표현
    예: ServiceKey, pageNo, numOfRows
    """
    name: str = Field(..., min_length=1, description="파라미터 이름")
    type: str = Field(default="string", description="파라미터 타입")
    required: bool = Field(default=False, description="필수 여부")
    description: str = Field(default="", description="파라미터 설명")
    location: ParameterLocation = Field(
        default=ParameterLocation.QUERY,
        description="파라미터 위치"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """파라미터 이름 검증"""
        if not v or not v.strip():
            raise ValueError("Parameter name cannot be empty")
        return v.strip()

    class Config:
        frozen = False  # Pydantic v2에서는 이 설정이 변경됨


class ResponseFieldInfo(BaseModel):
    """
    응답 필드 정보

    API 응답 스키마의 필드를 표현
    중첩 구조 지원 (items > item > baekduId)
    """
    name: str = Field(..., min_length=1, description="필드 이름")
    type: str = Field(default="string", description="필드 타입")
    description: str = Field(default="", description="필드 설명")
    nested_fields: List['ResponseFieldInfo'] = Field(
        default_factory=list,
        description="중첩된 필드 목록"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """필드 이름 검증"""
        if not v or not v.strip():
            raise ValueError("Field name cannot be empty")
        return v.strip()

    class Config:
        # 자기 참조 허용 (중첩 구조)
        frozen = False


class EndpointInfo(BaseModel):
    """
    엔드포인트 정보

    API 엔드포인트의 완전한 정의
    """
    path: str = Field(..., min_length=1, description="API 경로")
    method: HTTPMethod = Field(..., description="HTTP 메서드")
    operation_id: Optional[str] = Field(None, description="Swagger operationId")
    description: str = Field(default="", description="엔드포인트 설명")
    parameters: List[ParameterInfo] = Field(
        default_factory=list,
        description="파라미터 목록"
    )
    response_fields: List[ResponseFieldInfo] = Field(
        default_factory=list,
        description="응답 필드 목록"
    )
    produces: List[str] = Field(
        default_factory=list,
        description="응답 Content-Type 목록"
    )
    consumes: List[str] = Field(
        default_factory=list,
        description="요청 Content-Type 목록"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Swagger 태그 목록"
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """경로 검증"""
        if not v or not v.strip():
            raise ValueError("Path cannot be empty")
        path = v.strip()
        if not path.startswith("/"):
            path = "/" + path
        return path


class ServiceInfo(BaseModel):
    """
    API 서비스 정보

    같은 host를 가진 API들은 같은 Service로 그룹화됨
    """
    host: str = Field(..., min_length=1, description="API 호스트")
    base_path: str = Field(default="", description="API 기본 경로")
    schemes: List[str] = Field(
        default_factory=lambda: ["https"],
        description="프로토콜 목록"
    )

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """호스트 검증"""
        if not v or not v.strip():
            raise ValueError("Host cannot be empty")
        # http:// 또는 https:// 제거
        host = v.strip().lower()
        for prefix in ["https://", "http://"]:
            if host.startswith(prefix):
                host = host[len(prefix):]
        # 마지막 / 제거
        return host.rstrip("/")


# ==========================================
# 3. Aggregate Root (집합 루트)
# ==========================================
class OpenAPIDocument(BaseModel):
    """
    OpenAPI 문서 전체 구조

    하나의 refined JSON 파일을 표현하는 집합 루트
    """
    api_id: str = Field(..., description="API ID")
    service: ServiceInfo = Field(..., description="서비스 정보")
    endpoints: List[EndpointInfo] = Field(
        default_factory=list,
        description="엔드포인트 목록"
    )

    @field_validator("api_id")
    @classmethod
    def validate_api_id(cls, v: str) -> str:
        """API ID 검증"""
        if not v or not v.strip():
            raise ValueError("API ID cannot be empty")
        return v.strip()

    def get_all_parameters(self) -> List[ParameterInfo]:
        """
        모든 엔드포인트의 파라미터를 수집

        Returns:
            중복 제거된 파라미터 목록 (name 기준)
        """
        params_dict = {}
        for endpoint in self.endpoints:
            for param in endpoint.parameters:
                if param.name not in params_dict:
                    params_dict[param.name] = param
        return list(params_dict.values())

    def get_all_response_fields(self) -> List[ResponseFieldInfo]:
        """
        모든 엔드포인트의 응답 필드를 수집

        Returns:
            중복 제거된 응답 필드 목록 (name 기준)
        """
        fields_dict = {}
        for endpoint in self.endpoints:
            for field in endpoint.response_fields:
                if field.name not in fields_dict:
                    fields_dict[field.name] = field
        return list(fields_dict.values())


# ==========================================
# 4. Update Forward References (자기 참조 업데이트)
# ==========================================
# ResponseFieldInfo가 자기 자신을 참조하므로 업데이트 필요
ResponseFieldInfo.model_rebuild()

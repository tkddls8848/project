"""
OpenAPI 명세 파서 (순수 함수)

refined JSON → OpenAPIDocument 변환

CODING_RULES 준수:
- Rule 1: FP First - 모든 함수는 순수 함수
- Rule 4: Type Safety - 명시적 타입 사용
- 부작용 없음, I/O 없음, 테스트 용이
"""
import logging
from typing import Dict, Any, List, Optional
from app.domain.openapi.models import (
    EndpointInfo,
    ParameterInfo,
    ResponseFieldInfo,
    ServiceInfo,
    OpenAPIDocument,
    HTTPMethod,
    ParameterLocation
)

logger = logging.getLogger(__name__)


class OpenAPIParser:
    """
    OpenAPI 명세 파서 (Static Methods Only)

    모든 메서드는 순수 함수로 작성
    - 입력만으로 출력 결정
    - 전역 상태 변경 없음
    - I/O 없음
    """

    @staticmethod
    def parse_document(doc_data: Dict[str, Any]) -> Optional[OpenAPIDocument]:
        """
        refined JSON → OpenAPIDocument 변환 (순수 함수)

        Args:
            doc_data: refined JSON 전체

        Returns:
            OpenAPIDocument or None (API 문서가 아닌 경우)

        Design Decision:
        - API가 아닌 문서는 None 반환하여 조기에 필터링
        - 실패 시 None 반환 (예외 던지지 않음)
        """
        try:
            content = doc_data.get("content", {})

            # API 문서 여부 확인
            if content.get("data_type") != "API":
                logger.debug(f"Not an API document: {doc_data.get('api_id')}")
                return None

            api_id = doc_data.get("api_id", "")
            if not api_id:
                logger.warning("API document without api_id")
                return None

            # 서비스 정보 추출
            service = OpenAPIParser._parse_service(doc_data)
            if not service:
                logger.warning(f"Failed to parse service info for {api_id}")
                return None

            # 엔드포인트 추출
            endpoints = OpenAPIParser._parse_endpoints(content)

            return OpenAPIDocument(
                api_id=api_id,
                service=service,
                endpoints=endpoints
            )

        except Exception as e:
            logger.error(f"Error parsing OpenAPI document: {e}", exc_info=True)
            return None

    @staticmethod
    def _parse_service(doc_data: Dict[str, Any]) -> Optional[ServiceInfo]:
        """
        서비스 정보 추출 (순수 함수)

        swagger_json.host, basePath 사용

        Args:
            doc_data: refined JSON 전체

        Returns:
            ServiceInfo or None
        """
        try:
            swagger = doc_data.get("swagger_json", {})

            host = swagger.get("host", "")
            if not host:
                logger.debug("No host found in swagger_json")
                return None

            base_path = swagger.get("basePath", "")
            schemes = swagger.get("schemes", ["https"])

            return ServiceInfo(
                host=host,
                base_path=base_path,
                schemes=schemes if isinstance(schemes, list) else [schemes]
            )

        except Exception as e:
            logger.error(f"Error parsing service info: {e}")
            return None

    @staticmethod
    def _parse_endpoints(content: Dict[str, Any]) -> List[EndpointInfo]:
        """
        엔드포인트 목록 추출 (순수 함수)

        content.endpoints 배열 파싱

        Args:
            content: refined JSON의 content 객체

        Returns:
            EndpointInfo 목록 (빈 리스트 가능)
        """
        endpoints_data = content.get("endpoints", [])
        if not isinstance(endpoints_data, list):
            logger.warning("endpoints is not a list")
            return []

        endpoints = []

        for ep_data in endpoints_data:
            try:
                endpoint = OpenAPIParser._parse_single_endpoint(ep_data)
                if endpoint:
                    endpoints.append(endpoint)
            except Exception as e:
                logger.warning(f"Failed to parse endpoint: {e}")
                continue

        return endpoints

    @staticmethod
    def _parse_single_endpoint(ep_data: Dict[str, Any]) -> Optional[EndpointInfo]:
        """
        단일 엔드포인트 파싱 (순수 함수)

        Args:
            ep_data: 엔드포인트 데이터

        Returns:
            EndpointInfo or None
        """
        try:
            path = ep_data.get("path", "")
            if not path:
                logger.debug("Endpoint without path")
                return None

            method_str = ep_data.get("method", "GET").upper()

            # Enum 변환
            try:
                method = HTTPMethod(method_str)
            except ValueError:
                logger.debug(f"Unknown HTTP method: {method_str}, using GET")
                method = HTTPMethod.GET

            description = ep_data.get("description", "")
            operation_id = ep_data.get("operationId")

            # 파라미터 파싱
            parameters = OpenAPIParser._parse_parameters(
                ep_data.get("parameters", [])
            )

            # 응답 필드는 Week 2에서 구현 예정
            response_fields = []

            # produces/consumes
            produces = ep_data.get("produces", [])
            consumes = ep_data.get("consumes", [])

            # tags
            tags = ep_data.get("tags", [])
            if not isinstance(tags, list):
                tags = []

            return EndpointInfo(
                path=path,
                method=method,
                operation_id=operation_id,
                description=description,
                parameters=parameters,
                response_fields=response_fields,
                produces=produces if isinstance(produces, list) else [],
                consumes=consumes if isinstance(consumes, list) else [],
                tags=tags
            )

        except Exception as e:
            logger.error(f"Error parsing single endpoint: {e}")
            return None

    @staticmethod
    def _parse_parameters(params_data: List[Dict[str, Any]]) -> List[ParameterInfo]:
        """
        파라미터 목록 파싱 (순수 함수)

        Args:
            params_data: 파라미터 데이터 배열

        Returns:
            ParameterInfo 목록 (빈 리스트 가능)
        """
        if not isinstance(params_data, list):
            logger.debug("params_data is not a list")
            return []

        parameters = []

        for param_data in params_data:
            try:
                name = param_data.get("name", "")
                if not name or not name.strip():
                    continue

                param_type = param_data.get("type", "string")
                required = param_data.get("required", False)
                description = param_data.get("description", "")
                location_str = param_data.get("in", "query")

                # Enum 변환
                try:
                    location = ParameterLocation(location_str)
                except ValueError:
                    logger.debug(f"Unknown location: {location_str}, using query")
                    location = ParameterLocation.QUERY

                parameters.append(ParameterInfo(
                    name=name.strip(),
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

        TODO: Week 2에서 구현

        Args:
            swagger_paths: swagger_json.paths 객체
            path: API 경로
            method: HTTP 메서드

        Returns:
            ResponseFieldInfo 목록
        """
        # Week 2에서 구현 예정
        return []

    @staticmethod
    def _parse_nested_fields(
        schema: Dict[str, Any],
        parent_name: str = ""
    ) -> List[ResponseFieldInfo]:
        """
        중첩 필드 재귀 파싱 (순수 함수)

        items > item > baekduId 같은 구조 처리

        TODO: Week 2에서 구현

        Args:
            schema: 스키마 객체
            parent_name: 부모 필드 이름

        Returns:
            ResponseFieldInfo 목록
        """
        # Week 2에서 구현 예정
        return []

    @staticmethod
    def _extract_content_type_format(content_type: str) -> str:
        """
        Content-Type에서 포맷명 추출 (순수 함수)

        Args:
            content_type: Content-Type 문자열

        Returns:
            포맷명 (XML, JSON 등)

        Examples:
            >>> OpenAPIParser._extract_content_type_format("application/xml")
            "XML"
            >>> OpenAPIParser._extract_content_type_format("application/json")
            "JSON"
        """
        if not content_type:
            return ""

        content_type = content_type.lower()

        if "xml" in content_type:
            return "XML"
        elif "json" in content_type:
            return "JSON"
        else:
            # application/octet-stream → OCTET-STREAM
            parts = content_type.split("/")
            if len(parts) > 1:
                return parts[-1].upper()
            return content_type.upper()

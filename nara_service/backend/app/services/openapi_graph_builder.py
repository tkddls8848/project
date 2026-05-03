"""
OpenAPI 그래프 빌더 (Application Layer)

OpenAPI 문서를 Neo4j 그래프로 변환하는 유스케이스 오케스트레이션

CODING_RULES 준수:
- Rule 2: Application Layer - 유스케이스 오케스트레이션
- Domain 파서 + Infrastructure 실행기 조합
- 비즈니스 로직 조율
"""
import logging
from typing import Dict, Any
from app.domain.openapi.parser import OpenAPIParser
from app.domain.openapi.models import OpenAPIDocument
from app.infrastructure.neo4j.openapi_executor import OpenAPIGraphExecutor

logger = logging.getLogger(__name__)


class OpenAPIGraphBuilder:
    """
    OpenAPI 문서 → Neo4j 그래프 변환 (Application)

    책임: 파싱과 실행의 오케스트레이션
    - Domain 파서로 구조 추출 (순수 함수)
    - Infrastructure 실행기로 Neo4j 저장 (부작용)
    """

    def __init__(self, neo4j_service):
        """
        Args:
            neo4j_service: Neo4jService 인스턴스
        """
        self.executor = OpenAPIGraphExecutor(neo4j_service)

    def build(self, doc_data: Dict[str, Any]) -> bool:
        """
        OpenAPI 문서를 그래프로 변환

        Args:
            doc_data: refined JSON 전체

        Returns:
            성공 여부

        Design Decision:
        - Domain 파서로 구조 추출 (순수 함수, I/O 없음)
        - Infrastructure 실행기로 Neo4j 저장 (부작용, I/O)
        - 실패 시 False 반환 (예외 던지지 않음)
        """
        try:
            # 1. Domain: 파싱 (순수 함수)
            openapi_doc = OpenAPIParser.parse_document(doc_data)

            if not openapi_doc:
                logger.debug(f"Not an OpenAPI document or parsing failed: {doc_data.get('api_id')}")
                return False

            # 2. Infrastructure: 저장 (부작용)
            self._save_to_graph(openapi_doc)

            logger.info(f"✅ OpenAPI graph built for {openapi_doc.api_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error building OpenAPI graph: {e}", exc_info=True)
            return False

    def _save_to_graph(self, doc: OpenAPIDocument) -> None:
        """
        파싱된 OpenAPIDocument를 Neo4j에 저장

        실행 순서:
        1. Service 노드 생성
        2. 각 Endpoint 처리:
           - Endpoint 노드 생성
           - Parameter 노드들 생성
           - Format 관계 생성
           - Tag 관계 생성

        Args:
            doc: 파싱된 OpenAPIDocument

        Raises:
            Exception: Neo4j 저장 실패 시
        """
        try:
            # 1. 서비스 노드 생성
            self.executor.create_service_node(
                api_id=doc.api_id,
                host=doc.service.host,
                base_path=doc.service.base_path,
                schemes=doc.service.schemes
            )

            # 2. 각 엔드포인트 처리
            for endpoint in doc.endpoints:
                # 엔드포인트 ID 생성: {api_id}_{method}_{path}
                endpoint_id = self._generate_endpoint_id(
                    doc.api_id,
                    endpoint.method.value,
                    endpoint.path
                )

                # 엔드포인트 노드 생성
                self.executor.create_endpoint_node(
                    api_id=doc.api_id,
                    endpoint_id=endpoint_id,
                    path=endpoint.path,
                    method=endpoint.method.value,
                    description=endpoint.description
                )

                # 파라미터 노드들 생성
                for param in endpoint.parameters:
                    self.executor.create_parameter_node(
                        endpoint_id=endpoint_id,
                        name=param.name,
                        param_type=param.type,
                        required=param.required,
                        description=param.description,
                        location=param.location.value
                    )

                # 포맷 관계 생성
                if endpoint.produces or endpoint.consumes:
                    self.executor.create_format_relationships(
                        endpoint_id=endpoint_id,
                        produces=endpoint.produces,
                        consumes=endpoint.consumes
                    )

                # 태그 관계 생성
                if endpoint.tags:
                    self.executor.create_tag_relationships(
                        endpoint_id=endpoint_id,
                        tags=endpoint.tags
                    )

            logger.debug(f"Graph saved for {doc.api_id}: {len(doc.endpoints)} endpoints")

        except Exception as e:
            logger.error(f"Error saving to graph: {e}")
            raise

    def _generate_endpoint_id(self, api_id: str, method: str, path: str) -> str:
        """
        엔드포인트 고유 ID 생성 (순수 함수)

        Args:
            api_id: API ID
            method: HTTP 메서드
            path: API 경로

        Returns:
            엔드포인트 ID

        Examples:
            >>> builder._generate_endpoint_id("15002731", "GET", "/gettrailservice")
            "15002731_GET_/gettrailservice"
        """
        # 경로에서 특수 문자 제거 (Neo4j 노드 ID로 사용 가능하도록)
        safe_path = path.replace(" ", "_")
        return f"{api_id}_{method}_{safe_path}"

    def get_stats(self) -> Dict[str, int]:
        """
        OpenAPI 그래프 통계 조회

        Returns:
            통계 딕셔너리

        Examples:
            {
                "service_count": 5,
                "endpoint_count": 17,
                "parameter_count": 10,
                "format_count": 2
            }
        """
        from app.graph_schema_openapi import OpenAPINodeLabel

        stats = {}

        try:
            # Neo4j 세션을 통해 통계 조회
            session = self.executor.neo4j_service.get_session()

            # Service 노드 개수
            result = session.run(
                f"MATCH (s:{OpenAPINodeLabel.SERVICE}) RETURN count(s) as cnt"
            )
            stats["service_count"] = result.single()["cnt"]

            # Endpoint 노드 개수
            result = session.run(
                f"MATCH (e:{OpenAPINodeLabel.ENDPOINT}) RETURN count(e) as cnt"
            )
            stats["endpoint_count"] = result.single()["cnt"]

            # Parameter 노드 개수
            result = session.run(
                f"MATCH (p:{OpenAPINodeLabel.PARAMETER}) RETURN count(p) as cnt"
            )
            stats["parameter_count"] = result.single()["cnt"]

            # Format 노드 개수
            result = session.run(
                f"MATCH (f:{OpenAPINodeLabel.FORMAT}) RETURN count(f) as cnt"
            )
            stats["format_count"] = result.single()["cnt"]

            session.close()

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            stats = {
                "service_count": 0,
                "endpoint_count": 0,
                "parameter_count": 0,
                "format_count": 0
            }

        return stats

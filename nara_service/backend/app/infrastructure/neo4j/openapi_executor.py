"""
OpenAPI 그래프 Neo4j 실행기

Neo4j 데이터베이스에 OpenAPI 구조를 저장하는 I/O 작업 담당

CODING_RULES 준수:
- Rule 2: Infrastructure Layer - I/O만 담당
- 쿼리 생성은 Domain, 실행만 여기서
- 순수 함수와 부작용 분리
"""
import logging
from typing import List
from app.graph_schema_openapi import (
    OpenAPINodeLabel,
    OpenAPIRelationType,
    OpenAPIPropKey
)

logger = logging.getLogger(__name__)


class OpenAPIGraphExecutor:
    """
    OpenAPI 그래프 Neo4j 실행기 (Infrastructure)

    책임: Neo4j에 노드와 관계 생성 (I/O만)
    """

    def __init__(self, neo4j_service):
        """
        Args:
            neo4j_service: Neo4jService 인스턴스
        """
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
        - openapi.forest.go.kr 같은 호스트는 하나의 노드로 통합

        Args:
            api_id: Document의 API ID
            host: 서비스 호스트
            base_path: API 기본 경로
            schemes: 프로토콜 목록

        Raises:
            Exception: Neo4j 쿼리 실행 실패 시
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
            logger.debug(f"Service node created/merged: {host}")
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
        예: 15002731_GET_/gettrailservice

        Args:
            api_id: Document의 API ID
            endpoint_id: 엔드포인트 고유 ID
            path: API 경로
            method: HTTP 메서드
            description: 엔드포인트 설명

        Raises:
            Exception: Neo4j 쿼리 실행 실패 시
        """
        query = f"""
        MATCH (d:Document {{api_id: $api_id}})
        MERGE (ep:{OpenAPINodeLabel.ENDPOINT} {{id: $endpoint_id}})
        ON CREATE SET
            ep.{OpenAPIPropKey.PATH} = $path,
            ep.{OpenAPIPropKey.METHOD} = $method,
            ep.{OpenAPIPropKey.DESCRIPTION} = $description
        MERGE (d)-[:{OpenAPIRelationType.HAS_ENDPOINT}]->(ep)

        // HTTP Method 노드 (재사용)
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
        - 이를 통해 "ServiceKey를 사용하는 모든 API" 쿼리 가능

        Args:
            endpoint_id: 엔드포인트 ID
            name: 파라미터 이름
            param_type: 파라미터 타입
            required: 필수 여부
            description: 파라미터 설명
            location: 파라미터 위치 (query, path 등)

        Raises:
            Exception: Neo4j 쿼리 실행 실패 시
        """
        # required 여부에 따라 관계 타입 결정
        rel_type = (
            OpenAPIRelationType.REQUIRES_PARAMETER if required
            else OpenAPIRelationType.OPTIONAL_PARAMETER
        )

        query = f"""
        MATCH (ep:{OpenAPINodeLabel.ENDPOINT} {{id: $endpoint_id}})

        // 파라미터 노드 (name으로 MERGE - 공유 가능)
        MERGE (p:{OpenAPINodeLabel.PARAMETER} {{name: $name}})
        ON CREATE SET
            p.{OpenAPIPropKey.PARAM_TYPE} = $param_type,
            p.{OpenAPIPropKey.DESCRIPTION} = $description,
            p.{OpenAPIPropKey.IN} = $location

        // 관계 생성 (required 여부에 따라)
        MERGE (ep)-[:{rel_type}]->(p)

        // DataType 노드 (재사용)
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
            logger.debug(f"Parameter node created/merged: {name}")
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

        Args:
            endpoint_id: 엔드포인트 ID
            produces: 응답 포맷 목록 (예: ["application/xml"])
            consumes: 요청 포맷 목록 (예: ["application/json"])
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
                logger.debug(f"PRODUCES relationship created: {fmt_name}")
            except Exception as e:
                logger.error(f"Error creating PRODUCES relationship: {e}")
                # 계속 진행 (일부 실패해도 전체 중단하지 않음)

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
                logger.debug(f"CONSUMES relationship created: {fmt_name}")
            except Exception as e:
                logger.error(f"Error creating CONSUMES relationship: {e}")
                # 계속 진행

    def create_tag_relationships(
        self,
        endpoint_id: str,
        tags: List[str]
    ) -> None:
        """
        태그 노드 및 관계 생성 (HAS_TAG)

        Args:
            endpoint_id: 엔드포인트 ID
            tags: 태그 목록
        """
        for tag in tags:
            if not tag or not tag.strip():
                continue

            tag_name = tag.strip()

            query = f"""
            MATCH (ep:{OpenAPINodeLabel.ENDPOINT} {{id: $endpoint_id}})
            MERGE (t:{OpenAPINodeLabel.TAG} {{name: $tag_name}})
            MERGE (ep)-[:{OpenAPIRelationType.HAS_TAG}]->(t)
            """

            try:
                with self.neo4j_service.get_session() as session:
                    session.run(query, endpoint_id=endpoint_id, tag_name=tag_name)
                logger.debug(f"Tag relationship created: {tag_name}")
            except Exception as e:
                logger.error(f"Error creating tag relationship: {e}")
                # 계속 진행

    def _extract_format_name(self, content_type: str) -> str:
        """
        Content-Type에서 포맷명 추출 (순수 함수)

        Args:
            content_type: Content-Type 문자열

        Returns:
            포맷명 (XML, JSON 등)

        Examples:
            >>> executor._extract_format_name("application/xml")
            "XML"
            >>> executor._extract_format_name("application/json")
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

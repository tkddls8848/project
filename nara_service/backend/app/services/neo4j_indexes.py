"""
Neo4j 인덱스 및 제약조건 설정

성능 최적화를 위한 인덱스와 데이터 무결성을 위한 제약조건
"""

import logging
from neo4j import Driver
from app.graph_schema import NodeLabel, PropKey

logger = logging.getLogger(__name__)


class Neo4jIndexManager:
    """Neo4j 인덱스 및 제약조건 관리"""

    def __init__(self, driver: Driver):
        """
        Args:
            driver: Neo4j 드라이버 인스턴스
        """
        self.driver = driver

    def create_indexes(self):
        """
        모든 필수 인덱스 및 제약조건 생성

        Returns:
            생성된 인덱스 수
        """
        created_count = 0

        # 제약조건 (UNIQUE) - 데이터 무결성
        constraints = [
            # Document.api_id는 유니크해야 함
            f"CREATE CONSTRAINT document_api_id IF NOT EXISTS FOR (d:{NodeLabel.DOCUMENT}) REQUIRE d.{PropKey.API_ID} IS UNIQUE",

            # Keyword.name은 유니크해야 함
            f"CREATE CONSTRAINT keyword_name IF NOT EXISTS FOR (k:{NodeLabel.KEYWORD}) REQUIRE k.{PropKey.NAME} IS UNIQUE",

            # Category.name은 유니크해야 함
            f"CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:{NodeLabel.CATEGORY}) REQUIRE c.{PropKey.NAME} IS UNIQUE",

            # Provider.name은 유니크해야 함
            f"CREATE CONSTRAINT provider_name IF NOT EXISTS FOR (p:{NodeLabel.PROVIDER}) REQUIRE p.{PropKey.NAME} IS UNIQUE",
        ]

        # 인덱스 - 성능 최적화
        indexes = [
            # Document 인덱스
            f"CREATE INDEX document_title IF NOT EXISTS FOR (d:{NodeLabel.DOCUMENT}) ON (d.{PropKey.TITLE})",
            f"CREATE INDEX document_description IF NOT EXISTS FOR (d:{NodeLabel.DOCUMENT}) ON (d.{PropKey.DESCRIPTION})",
            f"CREATE INDEX document_created_at IF NOT EXISTS FOR (d:{NodeLabel.DOCUMENT}) ON (d.{PropKey.CREATED_AT})",

            # Keyword 인덱스 (이미 UNIQUE 제약조건으로 자동 생성되지만 명시적으로)
            # Category, Provider도 마찬가지
        ]

        # 관계 속성 인덱스 (Neo4j 5.x 이상)
        # CUSTOM_RELATED_TO 관계의 주요 속성들
        relationship_indexes = [
            # 관계 생성 시간 (시계열 분석용)
            f"CREATE INDEX rel_custom_created_at IF NOT EXISTS FOR ()-[r:CUSTOM_RELATED_TO]-() ON (r.{PropKey.CREATED_AT})",

            # 관계 강도 (강도 기반 필터링용)
            f"CREATE INDEX rel_custom_strength IF NOT EXISTS FOR ()-[r:CUSTOM_RELATED_TO]-() ON (r.{PropKey.STRENGTH})",

            # 사용자 정의 관계 타입 (타입별 필터링용)
            f"CREATE INDEX rel_custom_type IF NOT EXISTS FOR ()-[r:CUSTOM_RELATED_TO]-() ON (r.{PropKey.CUSTOM_TYPE})",

            # 관계 생성자 (생성자별 필터링용)
            f"CREATE INDEX rel_custom_created_by IF NOT EXISTS FOR ()-[r:CUSTOM_RELATED_TO]-() ON (r.{PropKey.CREATED_BY})",
        ]

        # 복합 인덱스 (여러 속성 조합)
        composite_indexes = [
            # Document: category + provider 복합 검색
            # Note: Neo4j에서 복합 인덱스는 제한적으로 지원됨
        ]

        # Full-text 검색 인덱스 (선택적)
        fulltext_indexes = [
            # Document의 title과 description에 대한 full-text 검색
            # f"CREATE FULLTEXT INDEX document_fulltext IF NOT EXISTS FOR (d:{NodeLabel.DOCUMENT}) ON EACH [d.{PropKey.TITLE}, d.{PropKey.DESCRIPTION}]",
        ]

        try:
            with self.driver.session() as session:
                # 제약조건 생성
                logger.info("Creating Neo4j constraints...")
                for constraint_query in constraints:
                    try:
                        session.run(constraint_query)
                        created_count += 1
                        logger.info(f"✅ Constraint created: {constraint_query[:60]}...")
                    except Exception as e:
                        # 이미 존재하는 제약조건은 에러가 나지 않지만, 다른 에러는 로깅
                        if "already exists" not in str(e).lower():
                            logger.warning(f"⚠️ Error creating constraint: {e}")

                # 인덱스 생성
                logger.info("Creating Neo4j indexes...")
                for index_query in indexes:
                    try:
                        session.run(index_query)
                        created_count += 1
                        logger.info(f"✅ Index created: {index_query[:60]}...")
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            logger.warning(f"⚠️ Error creating index: {e}")

                # 관계 인덱스 생성
                logger.info("Creating relationship indexes...")
                for index_query in relationship_indexes:
                    try:
                        session.run(index_query)
                        created_count += 1
                        logger.info(f"✅ Relationship index created: {index_query[:60]}...")
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            logger.warning(f"⚠️ Error creating relationship index: {e}")

                # 복합 인덱스 생성
                if composite_indexes:
                    logger.info("Creating composite indexes...")
                    for index_query in composite_indexes:
                        try:
                            session.run(index_query)
                            created_count += 1
                            logger.info(f"✅ Composite index created: {index_query[:60]}...")
                        except Exception as e:
                            if "already exists" not in str(e).lower():
                                logger.warning(f"⚠️ Error creating composite index: {e}")

                logger.info(f"🎯 Index creation completed. Created/verified: {created_count} items")
                return created_count

        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
            raise

    def list_indexes(self):
        """
        현재 데이터베이스의 모든 인덱스 및 제약조건 조회

        Returns:
            {
                "indexes": [인덱스 목록],
                "constraints": [제약조건 목록]
            }
        """
        try:
            with self.driver.session() as session:
                # 인덱스 조회
                index_result = session.run("SHOW INDEXES")
                indexes = [dict(record) for record in index_result]

                # 제약조건 조회
                constraint_result = session.run("SHOW CONSTRAINTS")
                constraints = [dict(record) for record in constraint_result]

                logger.info(f"Found {len(indexes)} indexes and {len(constraints)} constraints")
                return {
                    "indexes": indexes,
                    "constraints": constraints
                }

        except Exception as e:
            logger.error(f"Error listing indexes: {e}")
            return {
                "indexes": [],
                "constraints": []
            }

    def analyze_query_performance(self, query: str):
        """
        쿼리 성능 분석 (EXPLAIN/PROFILE)

        Args:
            query: 분석할 Cypher 쿼리

        Returns:
            쿼리 실행 계획
        """
        try:
            with self.driver.session() as session:
                # PROFILE: 실제 실행 + 통계
                profile_query = f"PROFILE {query}"
                result = session.run(profile_query)

                # 실행 계획 추출
                profile = result.consume().profile

                logger.info(f"Query profiled: {query[:60]}...")
                return profile

        except Exception as e:
            logger.error(f"Error profiling query: {e}")
            return None

    def drop_all_indexes(self):
        """
        모든 인덱스 삭제 (주의: 프로덕션에서 사용 금지!)

        개발/테스트 환경에서만 사용
        """
        try:
            with self.driver.session() as session:
                # 인덱스 목록 조회
                index_result = session.run("SHOW INDEXES")
                indexes = list(index_result)

                dropped_count = 0
                for index in indexes:
                    index_name = index.get("name")
                    if index_name:
                        try:
                            session.run(f"DROP INDEX {index_name} IF EXISTS")
                            dropped_count += 1
                            logger.info(f"Dropped index: {index_name}")
                        except Exception as e:
                            logger.warning(f"Error dropping index {index_name}: {e}")

                # 제약조건 삭제
                constraint_result = session.run("SHOW CONSTRAINTS")
                constraints = list(constraint_result)

                for constraint in constraints:
                    constraint_name = constraint.get("name")
                    if constraint_name:
                        try:
                            session.run(f"DROP CONSTRAINT {constraint_name} IF EXISTS")
                            dropped_count += 1
                            logger.info(f"Dropped constraint: {constraint_name}")
                        except Exception as e:
                            logger.warning(f"Error dropping constraint {constraint_name}: {e}")

                logger.warning(f"⚠️ Dropped {dropped_count} indexes/constraints")
                return dropped_count

        except Exception as e:
            logger.error(f"Error dropping indexes: {e}")
            raise


def create_neo4j_indexes(driver: Driver) -> int:
    """
    Neo4j 인덱스 생성 헬퍼 함수

    Args:
        driver: Neo4j 드라이버

    Returns:
        생성된 인덱스 수
    """
    manager = Neo4jIndexManager(driver)
    return manager.create_indexes()


def list_neo4j_indexes(driver: Driver) -> dict:
    """
    Neo4j 인덱스 목록 조회 헬퍼 함수

    Args:
        driver: Neo4j 드라이버

    Returns:
        {
            "indexes": [...],
            "constraints": [...]
        }
    """
    manager = Neo4jIndexManager(driver)
    return manager.list_indexes()

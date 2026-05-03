"""
Neo4j 자동 데이터 적재 서비스
서버 시작 시 index.json의 데이터를 Neo4j에 자동으로 적재합니다.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.services.neo4j_service import neo4j_service

logger = logging.getLogger(__name__)


def check_neo4j_has_data() -> bool:
    """Neo4j에 데이터가 있는지 확인"""
    try:
        with neo4j_service.get_session() as session:
            result = session.run("MATCH (d:Document) RETURN count(d) as count")
            count = result.single()["count"]
            return count > 0
    except Exception as e:
        logger.error(f"Neo4j 데이터 확인 실패: {e}")
        return False


def load_index_json() -> Optional[Dict[str, Any]]:
    """storage/index.json 파일 로드"""
    index_path = settings.storage_path / "index.json"

    if not index_path.exists():
        logger.warning(f"index.json 파일을 찾을 수 없습니다: {index_path}")
        return None

    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"index.json 로드 완료: {len(data)} 카테고리")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {e}")
        return None
    except Exception as e:
        logger.error(f"index.json 로드 실패: {e}")
        return None


def flatten_documents(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    index.json의 중첩 구조를 평탄화하여 문서 리스트 생성

    구조:
    {
        "fileData": { "15000635": {...}, ... },
        "openapi_link": { "15010052": {...}, ... },
        ...
    }
    """
    documents = []

    for category, items in data.items():
        if not isinstance(items, dict):
            continue

        for doc_id, doc_data in items.items():
            # 기본 키워드 파싱
            keywords = []
            keyword_str = doc_data.get('keyword', '')
            if keyword_str and isinstance(keyword_str, str):
                keywords = [k.strip() for k in keyword_str.split(',') if k.strip()]

            # 문서 구조 생성
            doc = {
                'id': doc_id,
                'api_id': doc_id,
                'category': category,
                'type': doc_data.get('type', ''),
                'title': doc_data.get('title', ''),
                'description': doc_data.get('description', ''),
                'url': doc_data.get('URL', ''),
                'crawled_url': doc_data.get('URL', ''),
                'org': doc_data.get('org', ''),
                'org_code': doc_data.get('org_code', ''),
                'keyword': keyword_str,
                'metadata': {
                    'title': doc_data.get('title', ''),
                    'description': doc_data.get('description', ''),
                    'provider': doc_data.get('org') or 'Unknown',
                    'category': category,
                    'keywords': keywords
                }
            }

            documents.append(doc)

    return documents


def load_documents_to_neo4j_silent(documents: List[Dict[str, Any]]) -> tuple[int, int]:
    """
    문서들을 Neo4j에 적재 (조용한 모드 - 서버 시작용)

    Returns:
        (success_count, error_count)
    """
    total = len(documents)
    success_count = 0
    error_count = 0

    logger.info(f"Neo4j 데이터 적재 시작: {total}개 문서")

    for idx, doc in enumerate(documents, 1):
        try:
            neo4j_service.upsert_document(doc)
            success_count += 1

            # 100개마다 진행상황 출력
            if idx % 100 == 0:
                logger.info(f"  진행: {idx}/{total} ({idx/total*100:.0f}%)")

        except Exception as e:
            error_count += 1
            if error_count <= 5:  # 처음 5개 에러만 로깅
                logger.error(f"  문서 적재 실패 [{doc.get('id')}]: {e}")

    logger.info(f"Neo4j 적재 완료: 성공 {success_count}/{total}, 실패 {error_count}")
    return success_count, error_count


def auto_load_neo4j_data(force_reload: bool = False) -> bool:
    """
    서버 시작 시 자동으로 Neo4j 데이터 적재

    Args:
        force_reload: True면 기존 데이터가 있어도 재적재

    Returns:
        적재 성공 여부
    """
    try:
        logger.info("=" * 60)
        logger.info("Neo4j 자동 데이터 적재 확인 중...")

        # 1. Neo4j 연결 확인
        try:
            with neo4j_service.get_session() as session:
                session.run("RETURN 1")
            logger.info("  - Neo4j 연결: OK")
        except Exception as e:
            logger.error(f"  - Neo4j 연결 실패: {e}")
            logger.warning("Neo4j를 사용할 수 없습니다. 서비스는 계속 실행됩니다.")
            return False

        # 2. 이미 데이터가 있는지 확인
        if not force_reload:
            has_data = check_neo4j_has_data()
            if has_data:
                logger.info("  - Neo4j에 이미 데이터가 있습니다. 스킵.")
                logger.info("=" * 60)
                return True

        # 3. index.json 로드
        data = load_index_json()
        if not data:
            logger.warning("  - index.json을 찾을 수 없습니다. Neo4j 적재 스킵.")
            logger.info("=" * 60)
            return False

        # 4. 문서 평탄화
        documents = flatten_documents(data)
        if not documents:
            logger.warning("  - 적재할 문서가 없습니다.")
            logger.info("=" * 60)
            return False

        logger.info(f"  - 적재할 문서 수: {len(documents)}개")

        # 5. Neo4j에 적재
        success_count, error_count = load_documents_to_neo4j_silent(documents)

        # 6. 결과 출력
        if success_count > 0:
            logger.info(f"Neo4j 자동 적재 완료!")
            logger.info(f"  - 성공: {success_count}개")
            if error_count > 0:
                logger.warning(f"  - 실패: {error_count}개")
            logger.info("=" * 60)
            return True
        else:
            logger.error("Neo4j 적재 실패: 성공한 문서가 없습니다.")
            logger.info("=" * 60)
            return False

    except Exception as e:
        logger.error(f"Neo4j 자동 적재 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        logger.info("=" * 60)
        return False


def get_neo4j_quick_stats() -> Dict[str, int]:
    """Neo4j 간단한 통계 조회"""
    try:
        with neo4j_service.get_session() as session:
            result = session.run("""
                MATCH (d:Document) WITH count(d) as doc_count
                MATCH (k:Keyword) WITH doc_count, count(k) as keyword_count
                MATCH (c:Category) WITH doc_count, keyword_count, count(c) as category_count
                MATCH (p:Provider) WITH doc_count, keyword_count, category_count, count(p) as provider_count
                RETURN doc_count, keyword_count, category_count, provider_count
            """)
            record = result.single()
            if record:
                stats = {
                    "documents": record["doc_count"],
                    "keywords": record["keyword_count"],
                    "categories": record["category_count"],
                    "providers": record["provider_count"]
                }
                logger.info(f"Neo4j 통계: {stats}")
                return stats
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")

    return {}

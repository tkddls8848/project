"""Advanced Insights API Router

Phase 4 고급 분석 기능 API 엔드포인트:
- 관계 체인 발견
- 숨겨진 연결 발견
- 커뮤니티 탐지
- 중심성 분석
- 보완 데이터 추천
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import logging

from app.models import (
    RelationshipChainsResponse,
    HiddenConnectionsResponse,
    CommunitiesResponse,
    CentralityAnalysisResponse,
    ComplementaryDataResponse
)
from app.auth import verify_api_key
from app.domain.common.dependencies import get_insight_engine
from app.domain.insights import (
    validate_chain_length,
    validate_community_size,
    validate_centrality_limit,
    validate_hidden_connections_limit,
    validate_complementary_data_limit
)
from app.services.insight_engine import InsightEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])


# ==========================================
# Relationship Chains
# ==========================================

@router.get("/chains/{doc_id}", response_model=RelationshipChainsResponse)
async def get_relationship_chains(
    doc_id: str,
    min_length: int = 2,
    max_length: int = 4,
    limit: int = 10,
    _: bool = Depends(verify_api_key),
    insight_engine: InsightEngine = Depends(get_insight_engine)
) -> JSONResponse:
    """
    특정 문서에서 시작하는 관계 체인을 발견합니다.

    Args:
        doc_id: 기준 문서 ID
        min_length: 최소 체인 길이 (기본값 2)
        max_length: 최대 체인 길이 (기본값 4)
        limit: 최대 반환 개수 (기본값 10)

    Returns:
        RelationshipChainsResponse: 발견된 관계 체인 목록
    """
    try:
        # 파라미터 검증 (Domain Layer - Pure Functions)
        min_length, max_length = validate_chain_length(
            min_length=min_length,
            max_length=max_length,
            min_allowed=1,
            max_allowed=5
        )
        limit = validate_complementary_data_limit(limit, max_limit=50)

        result = insight_engine.discover_chains(
            doc_id=doc_id,
            min_length=min_length,
            max_length=max_length,
            limit=limit
        )

        return JSONResponse(content=result)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting relationship chains for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Hidden Connections
# ==========================================

@router.get("/hidden-connections/{doc_id}", response_model=HiddenConnectionsResponse)
async def get_hidden_connections(
    doc_id: str,
    limit: int = 10,
    _: bool = Depends(verify_api_key),
    insight_engine: InsightEngine = Depends(get_insight_engine)
) -> JSONResponse:
    """
    간접적으로 연결되어 있지만 직접 관계가 없는 문서들을 발견합니다.

    Args:
        doc_id: 기준 문서 ID
        limit: 최대 반환 개수 (기본값 10)

    Returns:
        HiddenConnectionsResponse: 발견된 숨겨진 연결 목록
    """
    try:
        # 파라미터 검증 (Domain Layer - Pure Function)
        limit = validate_hidden_connections_limit(limit, max_limit=50)

        result = insight_engine.find_hidden_connections(
            doc_id=doc_id,
            limit=limit
        )

        return JSONResponse(content=result)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting hidden connections for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Community Detection
# ==========================================

@router.get("/communities", response_model=CommunitiesResponse)
async def get_communities(
    min_size: int = 3,
    _: bool = Depends(verify_api_key),
    insight_engine: InsightEngine = Depends(get_insight_engine)
) -> JSONResponse:
    """
    그래프 내 커뮤니티를 탐지합니다 (Louvain 알고리즘).

    Args:
        min_size: 최소 커뮤니티 크기 (기본값 3)

    Returns:
        CommunitiesResponse: 발견된 커뮤니티 목록
    """
    try:
        # 파라미터 검증 (Domain Layer - Pure Function)
        min_size = validate_community_size(min_size, min_allowed=2, max_allowed=20)

        result = insight_engine.detect_communities(min_size=min_size)

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error detecting communities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Centrality Analysis
# ==========================================

@router.get("/centrality", response_model=CentralityAnalysisResponse)
async def get_centrality_analysis(
    limit: int = 20,
    _: bool = Depends(verify_api_key),
    insight_engine: InsightEngine = Depends(get_insight_engine)
) -> JSONResponse:
    """
    그래프 내 중요 노드를 중심성 지표로 분석합니다.
    - Degree Centrality (연결 중심성)
    - Betweenness Centrality (매개 중심성)
    - PageRank (페이지랭크)

    Args:
        limit: 최대 반환 노드 개수 (기본값 20)

    Returns:
        CentralityAnalysisResponse: 상위 중요 노드 목록
    """
    try:
        # 파라미터 검증 (Domain Layer - Pure Function)
        limit = validate_centrality_limit(limit, max_limit=100)

        result = insight_engine.calculate_centrality(limit=limit)

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error calculating centrality: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Complementary Data Recommendations
# ==========================================

@router.get("/complementary/{doc_id}", response_model=ComplementaryDataResponse)
async def get_complementary_data(
    doc_id: str,
    limit: int = 10,
    _: bool = Depends(verify_api_key),
    insight_engine: InsightEngine = Depends(get_insight_engine)
) -> JSONResponse:
    """
    현재 문서 및 연결된 문서들을 분석하여 부족한 영역을 채울 수 있는
    보완 데이터를 추천합니다.

    Args:
        doc_id: 기준 문서 ID
        limit: 최대 추천 개수 (기본값 10)

    Returns:
        ComplementaryDataResponse: 보완 데이터 추천 목록
    """
    try:
        # 파라미터 검증 (Domain Layer - Pure Function)
        limit = validate_complementary_data_limit(limit, max_limit=50)

        result = insight_engine.suggest_complementary_data(
            doc_id=doc_id,
            limit=limit
        )

        return JSONResponse(content=result)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting complementary data for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

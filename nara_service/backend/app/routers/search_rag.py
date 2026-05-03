"""
Search RAG Router - RAG 검색 페이지용 API

Why: 프론트엔드 RAG 검색 페이지(/search)를 위한 검색 API를 제공합니다.
     FAISS 기반 청크 검색과 문서 그룹핑을 통해 관련도 높은 문서를 반환합니다.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.services.search_rag_service import SearchRAGService
from app.domain.common.dependencies import get_search_rag_service

router = APIRouter(prefix="/search", tags=["Search RAG"])


class SearchRequest(BaseModel):
    """
    RAG 검색 요청 모델

    Why: 검색 파라미터를 검증하고 타입 안전성을 보장합니다.
    """
    query: str = Field(..., min_length=1, description="검색 쿼리")
    n_results: int = Field(3, ge=1, le=20, description="최종 반환 개수")
    initial_results: int = Field(20, ge=1, le=100, description="초기 검색 개수 (그룹핑 전)")
    doc_type: Optional[str] = Field(None, description="문서 타입 필터 (rest_api, file_download, standard_data)")


class SearchResponse(BaseModel):
    """
    RAG 검색 응답 모델

    Why: API 응답 형식을 명확하게 정의하여 프론트엔드와의 인터페이스를 보장합니다.
    """
    query: str = Field(..., description="입력된 검색 쿼리")
    total_results: int = Field(..., description="반환된 결과 개수")
    results: List[Dict[str, Any]] = Field(..., description="검색 결과 리스트")


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    service: SearchRAGService = Depends(get_search_rag_service)
) -> SearchResponse:
    """
    RAG 검색 API

    Why: 자연어 쿼리를 받아 FAISS 벡터 검색으로 관련 문서를 찾고,
         doc_id별로 그룹핑하여 중복을 제거한 뒤 상위 결과를 반환합니다.
         이는 사용자가 동일 문서의 여러 청크를 중복으로 보지 않도록 하기 위함입니다.

    Technical Flow:
        1단계: FAISS 코사인 유사도 기반 초기 검색 (initial_results * 3개)
        2단계: doc_id별로 청크 그룹핑 및 최대 점수 선택
        3단계: 그룹을 점수순 정렬 후 상위 initial_results개 선택
        4단계: 최종 n_results개만 반환
        5단계: 응답 형식 변환 (엔드포인트 정보 포함)

    Args:
        request: 검색 요청 (query, n_results, doc_type 필터 등)
        service: SearchRAG 서비스 인스턴스 (의존성 주입)

    Returns:
        검색 결과 응답 (query, total_results, results)

    Raises:
        HTTPException: 검색 중 오류 발생 시 500 에러
    """

    try:
        # 1단계: FAISS 검색 수행 (initial_results * 3개 검색)
        initial_results = service.search_chunks(
            query=request.query,
            top_k=request.initial_results * 3,  # 더 많이 검색해서 그룹핑 후 필터링
            doc_type_filter=request.doc_type
        )

        # 2단계: doc_id별로 청크 그룹핑 (Domain Layer - Pure Function)
        from app.domain.rag import group_chunks_by_doc_id, sort_groups_by_score

        doc_groups = group_chunks_by_doc_id(initial_results)

        # 3단계: 그룹을 점수순으로 정렬하고 상위 initial_results개 선택
        sorted_groups = sort_groups_by_score(doc_groups, request.initial_results)

        # 4단계: 최종 n_results개만 선택
        final_groups = sorted_groups[:request.n_results]

        # 5단계: 응답 형식 변환 (Domain Layer - Pure Function)
        from app.domain.rag import format_batch_results

        enhanced_results = format_batch_results(final_groups, include_endpoints=True)

        return SearchResponse(
            query=request.query,
            total_results=len(enhanced_results),
            results=enhanced_results
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats(
    service: SearchRAGService = Depends(get_search_rag_service)
) -> Dict[str, Any]:
    """
    RAG 통계 정보를 반환합니다.

    Why: 프론트엔드에서 현재 인덱싱된 데이터의 규모를
         사용자에게 표시하기 위해 제공합니다.

    Args:
        service: SearchRAG 서비스 인스턴스 (의존성 주입)

    Returns:
        총 청크 수, 문서 수, 문서 타입별 분포 등

    Raises:
        HTTPException: 통계 조회 중 오류 발생 시 500 에러
    """
    try:
        stats = service.get_chunk_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health() -> Dict[str, Any]:
    """
    헬스 체크 엔드포인트

    Why: 서비스 상태를 모니터링하고 RAG 서비스 초기화 여부를 확인합니다.

    Returns:
        서비스 상태 정보
    """
    from app.domain.common.dependencies import get_search_rag_service_optional

    return {
        "status": "healthy",
        "service": "Search RAG API",
        "rag_service_ready": get_search_rag_service_optional() is not None
    }

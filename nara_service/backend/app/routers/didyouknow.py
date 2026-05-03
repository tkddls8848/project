"""
Did You Know Router - 흥미로운 공공데이터 사실 API

Why: 공공데이터 API 문서에서 LLM으로 생성한 흥미로운 사실을 제공합니다.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.services.didyouknow_service import DidYouKnowService, FactCategory
from app.domain.common.dependencies import get_didyouknow_service

router = APIRouter(prefix="/didyouknow", tags=["Did You Know"])


# ==================== 모델 정의 ====================

class FactResponse(BaseModel):
    """단일 사실 응답"""
    id: str = Field(..., description="고유 ID (UUID)")
    category: str = Field(..., description="카테고리")
    content: str = Field(..., description="사실 내용 (한 문장)")
    source_doc_id: Optional[str] = Field(None, description="원천 문서 ID")
    created_at: str = Field(..., description="생성 시간 (ISO 8601)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")


class FactsListResponse(BaseModel):
    """사실 목록 응답"""
    total: int = Field(..., description="총 개수")
    facts: List[FactResponse] = Field(..., description="사실 목록")


class LLMParams(BaseModel):
    """LLM 생성 파라미터"""
    temperature: float = Field(0.8, ge=0.0, le=1.0, description="Temperature (0.0-1.0)")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Top P (0.0-1.0)")
    max_tokens: int = Field(150, ge=50, le=500, description="최대 토큰 수")


class CategoryCounts(BaseModel):
    """카테고리별 생성 개수"""
    api_introduction: int = Field(34, ge=0, le=100, description="API 소개 개수")
    provider_introduction: int = Field(34, ge=0, le=100, description="제공 기관 소개 개수")
    usage_tip: int = Field(34, ge=0, le=100, description="활용 팁 개수")


class GenerateRequest(BaseModel):
    """콘텐츠 생성 요청 (관리자용)"""
    counts: CategoryCounts = Field(..., description="카테고리별 생성 개수")
    llm_params: LLMParams = Field(default_factory=LLMParams, description="LLM 생성 파라미터")


# ==================== 엔드포인트 ====================

@router.get("/facts", response_model=FactsListResponse)
async def get_all_facts(
    category: Optional[str] = None,
    service: DidYouKnowService = Depends(get_didyouknow_service)
) -> FactsListResponse:
    """
    저장된 모든 사실 조회

    Why: 프론트엔드에서 슬라이드쇼에 표시할 사실 목록을 가져옵니다.
         캐시된 facts.json에서 로드하므로 매우 빠릅니다 (1ms 이내).

    Query Parameters:
        category: 카테고리 필터 (선택)
            - api_introduction: 특정 API 소개
            - provider_introduction: 제공 기관 소개
            - usage_tip: 데이터 활용 팁

    Returns:
        사실 목록 (total, facts)

    Raises:
        HTTPException: 로드 실패 시 500 에러
    """
    try:
        facts = service.load_facts()

        if category:
            facts = [f for f in facts if f.get('category') == category]

        return FactsListResponse(
            total=len(facts),
            facts=facts
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load facts: {str(e)}")


@router.get("/random", response_model=FactResponse)
async def get_random_fact(
    category: Optional[str] = None,
    service: DidYouKnowService = Depends(get_didyouknow_service)
) -> FactResponse:
    """
    랜덤 사실 1개 반환

    Why: 매번 다른 사실을 보여주거나 API 테스트용으로 사용합니다.

    Query Parameters:
        category: 카테고리 필터 (선택)

    Returns:
        랜덤 사실 1개

    Raises:
        HTTPException: 사실이 없으면 404, 로드 실패 시 500
    """
    try:
        fact = service.get_random_fact(category)

        if not fact:
            raise HTTPException(
                status_code=404,
                detail="No facts available" + (f" for category: {category}" if category else "")
            )

        return fact
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get random fact: {str(e)}")


@router.post("/generate")
async def generate_facts(
    request: GenerateRequest,
    service: DidYouKnowService = Depends(get_didyouknow_service)
) -> Dict[str, Any]:
    """
    새로운 콘텐츠 생성 (관리자용)

    Why: 캐시된 사실이 없거나 새로운 콘텐츠를 생성하고 싶을 때 사용합니다.
         LLM 호출이 필요하므로 5-10분 소요될 수 있습니다.
         기존 facts.json을 삭제하고 새로 생성합니다.

    Body:
        category: 특정 카테고리만 생성 (선택, null이면 전체)
        count_per_category: 카테고리당 생성 개수 (기본 34개, 3개 카테고리 = 총 102개)

    Returns:
        생성 결과 (generated_count, total_count)

    Technical Flow:
        1단계: RAG 시스템에서 원천 문서 선택
        2단계: 카테고리별 LLM 프롬프트 생성
        3단계: Ollama gemma3:1b로 콘텐츠 생성
        4단계: 기존 파일 삭제 후 새로 생성된 사실만 저장

    Raises:
        HTTPException: 생성 실패 시 500 에러
    """
    try:
        # 카테고리별 개수 설정
        counts = {
            FactCategory.API_INTRODUCTION: request.counts.api_introduction,
            FactCategory.PROVIDER_INTRO: request.counts.provider_introduction,
            FactCategory.USAGE_TIP: request.counts.usage_tip,
        }

        # LLM 파라미터 추출
        llm_params = {
            "temperature": request.llm_params.temperature,
            "top_p": request.llm_params.top_p,
            "max_tokens": request.llm_params.max_tokens,
        }

        # 새 사실 생성 (LLM 파라미터 전달)
        new_facts = service.generate_batch(counts, llm_params)

        # 기존 파일 삭제하고 새로 생성된 사실만 저장
        service.save_facts(new_facts)

        return {
            "status": "success",
            "generated_count": len(new_facts),
            "total_count": len(new_facts)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate facts: {str(e)}")


@router.get("/stats")
async def get_stats(
    service: DidYouKnowService = Depends(get_didyouknow_service)
) -> Dict[str, Any]:
    """
    통계 정보 반환

    Why: 관리자가 현재 캐시된 사실의 현황을 파악하기 위해 사용합니다.

    Returns:
        통계 정보 (total, by_category)

    Raises:
        HTTPException: 로드 실패 시 500 에러
    """
    try:
        facts = service.load_facts()

        stats = {
            "total": len(facts),
            "by_category": {}
        }

        for cat in FactCategory:
            stats["by_category"][cat.value] = len([f for f in facts if f.get('category') == cat.value])

        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

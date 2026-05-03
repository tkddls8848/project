"""
Prometheus API Router

Why: Prometheus 워크플로우 관리 및 RAG 기반 대화형 검색 기능을 제공합니다.
     사용자가 생성한 워크플로우(Prometheus)를 CRUD 하고,
     선택한 컨텍스트를 기반으로 AI와 대화할 수 있습니다.
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any, AsyncGenerator
import json
import logging

from app.models import (
    QueryRequest,
    PrometheusChatRequest,
    PrometheusCreateRequest,
    PrometheusUpdateRequest,
    PrometheusResponse,
    PrometheusListResponse
)
from app.auth import verify_api_key
from app.domain.common.dependencies import (
    get_rag_service,
    get_prometheus_service
)
from app.domain.streaming import (
    create_token_message,
    create_done_message,
    create_error_message,
)
from app.services.rag_service import RAGService
from app.services.prometheus_service import PrometheusService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prometheus", tags=["prometheus"])


# ==================== CRUD Endpoints ====================

@router.post("", response_model=PrometheusResponse)
async def create_prometheus(
    request: PrometheusCreateRequest,
    _: bool = Depends(verify_api_key),
    service: PrometheusService = Depends(get_prometheus_service)
) -> PrometheusResponse:
    """
    새로운 Prometheus 워크플로우를 생성합니다.

    Why: 사용자가 RAG 검색 결과와 대화 내용을 저장하여
         나중에 다시 확인하거나 공유할 수 있도록 합니다.

    Args:
        request: 생성 요청 (user_id, title, description 등)
        _: API 키 검증 (의존성 주입)
        service: Prometheus 서비스 인스턴스 (의존성 주입)

    Returns:
        생성된 Prometheus 정보

    Raises:
        HTTPException: 서비스 초기화 실패 시 503 에러
    """
    return service.create_prometheus(request)


@router.get("", response_model=PrometheusListResponse)
async def list_prometheuss(
    user_id: str,
    _: bool = Depends(verify_api_key),
    service: PrometheusService = Depends(get_prometheus_service)
) -> PrometheusListResponse:
    """
    사용자의 Prometheus 목록을 조회합니다.

    Why: 사용자가 생성한 모든 워크플로우를 확인할 수 있도록 합니다.

    Args:
        user_id: 사용자 ID
        _: API 키 검증 (의존성 주입)
        service: Prometheus 서비스 인스턴스 (의존성 주입)

    Returns:
        Prometheus 목록 및 총 개수
    """
    prometheuss = service.list_prometheuss(user_id)
    return {"prometheuss": prometheuss, "total": len(prometheuss)}


@router.get("/{prometheus_id}", response_model=PrometheusResponse)
async def get_prometheus(
    prometheus_id: str,
    _: bool = Depends(verify_api_key),
    service: PrometheusService = Depends(get_prometheus_service)
) -> PrometheusResponse:
    """
    특정 Prometheus 워크플로우를 조회합니다.

    Why: 저장된 워크플로우의 상세 정보를 가져옵니다.

    Args:
        prometheus_id: Prometheus ID
        _: API 키 검증 (의존성 주입)
        service: Prometheus 서비스 인스턴스 (의존성 주입)

    Returns:
        Prometheus 정보

    Raises:
        HTTPException: Prometheus를 찾을 수 없는 경우 404 에러
    """
    prometheus = service.get_prometheus(prometheus_id)
    if not prometheus:
        raise HTTPException(status_code=404, detail="Prometheus not found")
    return prometheus


@router.put("/{prometheus_id}", response_model=PrometheusResponse)
async def update_prometheus(
    prometheus_id: str,
    request: PrometheusUpdateRequest,
    user_id: str,
    _: bool = Depends(verify_api_key),
    service: PrometheusService = Depends(get_prometheus_service)
) -> PrometheusResponse:
    """
    Prometheus 워크플로우를 수정합니다.

    Why: 사용자가 워크플로우의 제목, 설명 등을 업데이트할 수 있도록 합니다.

    Args:
        prometheus_id: Prometheus ID
        request: 수정 요청 (title, description 등)
        user_id: 사용자 ID (권한 확인용)
        _: API 키 검증 (의존성 주입)
        service: Prometheus 서비스 인스턴스 (의존성 주입)

    Returns:
        수정된 Prometheus 정보

    Raises:
        HTTPException:
            - 404: Prometheus를 찾을 수 없는 경우
            - 403: 수정 권한이 없는 경우
    """
    try:
        prometheus = service.update_prometheus(prometheus_id, request, user_id)
        if not prometheus:
            raise HTTPException(status_code=404, detail="Prometheus not found")
        return prometheus
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this prometheus"
        )


@router.delete("/{prometheus_id}")
async def delete_prometheus(
    prometheus_id: str,
    user_id: str,
    _: bool = Depends(verify_api_key),
    service: PrometheusService = Depends(get_prometheus_service)
) -> Dict[str, str]:
    """
    Prometheus 워크플로우를 삭제합니다.

    Why: 사용자가 더 이상 필요 없는 워크플로우를 제거할 수 있도록 합니다.

    Args:
        prometheus_id: Prometheus ID
        user_id: 사용자 ID (권한 확인용)
        _: API 키 검증 (의존성 주입)
        service: Prometheus 서비스 인스턴스 (의존성 주입)

    Returns:
        삭제 성공 메시지

    Raises:
        HTTPException:
            - 404: Prometheus를 찾을 수 없는 경우
            - 403: 삭제 권한이 없는 경우
    """
    try:
        success = service.delete_prometheus(prometheus_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Prometheus not found")
        return {"status": "success", "message": "Prometheus deleted"}
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this prometheus"
        )


# ==================== Search & Chat Endpoints ====================

@router.post("/search")
async def prometheus_search(
    request: Request,
    query_req: QueryRequest,
    _: bool = Depends(verify_api_key),
    rag_service: RAGService = Depends(get_rag_service)
) -> Dict[str, Any]:
    """
    워크플로우용 검색 엔드포인트

    Why: LLM 생성 없이 RAG 검색만 수행하여,
         사용자가 원하는 문서를 직접 선택할 수 있도록 합니다.
         이는 워크플로우에서 컨텍스트를 직접 제어할 수 있게 합니다.

    Args:
        request: FastAPI Request
        query_req: 검색 쿼리 요청
        _: API 키 검증 (의존성 주입)
        rag_service: RAG 서비스 인스턴스 (의존성 주입)

    Returns:
        검색된 문서 리스트 및 총 개수

    Raises:
        HTTPException: 검색 실패 시 500 에러
    """
    try:
        # 검색만 수행 (LLM 생성 없음)
        relevant_docs = rag_service.search(query_req.message, top_k=5)

        return {
            "documents": relevant_docs,
            "total": len(relevant_docs)
        }
    except Exception as e:
        logger.error(f"Prometheus Search Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def prometheus_chat(
    request: Request,
    chat_req: PrometheusChatRequest,
    _: bool = Depends(verify_api_key),
    rag_service: RAGService = Depends(get_rag_service)
) -> StreamingResponse:
    """
    워크플로우용 채팅 엔드포인트 (스트리밍)

    Why: 클라이언트가 선택한 컨텍스트(context_docs)를 사용하여 응답을 생성합니다.
         이를 통해 사용자는 RAG 검색 결과 중 원하는 문서만 선택하여
         더 정확하고 관련성 높은 답변을 얻을 수 있습니다.

    Technical Flow:
        1단계: 클라이언트가 제공한 컨텍스트 문서 사용 (검색 단계 생략)
        2단계: LLM에 "insight" 모드로 프롬프트 전달
        3단계: 생성된 토큰을 실시간 스트리밍

    Args:
        request: FastAPI Request
        chat_req: 채팅 요청 (query, context_docs, relationships, llm_type)
        _: API 키 검증 (의존성 주입)
        rag_service: RAG 서비스 인스턴스 (의존성 주입)

    Returns:
        NDJSON 형식의 스트리밍 응답

    Note:
        - 제공된 컨텍스트로 바로 생성 시작 (검색 없음)
        - prompt_mode="insight"로 더 심층적인 분석 제공
    """

    async def generate() -> AsyncGenerator[str, None]:
        """
        스트리밍 응답 생성기

        Why: NDJSON 형식으로 LLM 응답을 실시간 전송합니다.
        """
        try:
            # 제공된 컨텍스트로 바로 생성 시작 (Domain Layer - Pure Function)
            generator = rag_service.generate_response(
                chat_req.query,
                chat_req.context_docs,
                relationships=chat_req.relationships,
                llm_type=chat_req.llm_type,
                prompt_mode="insight"
            )

            # LLM 토큰 스트리밍 (Domain Layer - Pure Function)
            for chunk in generator:
                yield create_token_message(chunk)

            # 완료 신호 (Domain Layer - Pure Function)
            yield create_done_message()

        except Exception as e:
            logger.error(f"Prometheus Chat Error: {e}")
            yield create_error_message("Internal Processing Error")

    return StreamingResponse(generate(), media_type="application/x-ndjson")

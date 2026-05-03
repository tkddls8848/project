"""
General API Router - Health, Index, Feedback, Query

Why: 프로젝트의 기본 API 엔드포인트를 제공합니다.
     헬스 체크, 인덱스 조회, 피드백 저장, RAG 기반 자연어 쿼리를 처리합니다.
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any, AsyncGenerator
import json
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models import QueryRequest, FeedbackRequest, FeedbackResponse
from app.auth import verify_api_key
from app.core.config import settings
from app.domain.common.dependencies import get_rag_service
from app.domain.streaming import (
    create_documents_message,
    create_related_documents_message,
    create_token_message,
    create_done_message,
    create_error_message,
    should_send_related_documents,
)
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)


# ==================== General Routes ====================

@router.get("/")
async def root() -> Dict[str, str]:
    """
    루트 엔드포인트

    Why: API 버전 및 기본 정보를 제공합니다.

    Returns:
        환영 메시지 및 버전 정보
    """
    return {
        "message": "Welcome to NARA Service API",
        "version": settings.APP_VERSION,
    }


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    헬스 체크 엔드포인트

    Why: 서비스 상태를 모니터링하기 위해 사용합니다.

    Returns:
        서비스 상태 정보
    """
    return {"status": "healthy"}


@router.get("/index")
async def get_index(_: bool = Depends(verify_api_key)) -> JSONResponse:
    """
    storage/index.json 파일을 읽어서 반환합니다.

    Why: 인덱싱된 문서 목록을 Frontend에 제공하여
         사용자가 어떤 데이터가 있는지 확인할 수 있도록 합니다.

    Args:
        _: API 키 검증 (의존성 주입)

    Returns:
        index.json 파일의 내용

    Raises:
        HTTPException:
            - 404: 파일이 없는 경우
            - 500: 파일 읽기/파싱 실패
    """
    try:
        # settings에서 storage 경로 가져오기
        index_file_path = settings.storage_path / "index.json"

        if not index_file_path.exists():
            logger.error(f"File not found: {index_file_path}")
            raise HTTPException(
                status_code=404,
                detail="index.json file not found"
            )

        with open(index_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return JSONResponse(content=data)

    except json.JSONDecodeError as e:
        logger.error(f"JSON Parse Error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )
    except Exception as e:
        logger.error(f"File Read Error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )


# ==================== Feedback Route ====================

@router.post("/feedback", response_model=FeedbackResponse)
@limiter.limit("5/minute")
async def save_feedback(
    request: Request,
    feedback: FeedbackRequest,
    _: bool = Depends(verify_api_key)
) -> FeedbackResponse:
    """
    사용자 피드백을 storage/cookies 디렉토리에 저장합니다.

    Why: 사용자 피드백을 수집하여 서비스 품질을 개선하고,
         LLM 응답의 정확도를 모니터링합니다.

    Args:
        request: FastAPI Request (rate limiting용)
        feedback: 피드백 데이터 (query, response, feedback, llm_type, timestamp, user)
        _: API 키 검증 (의존성 주입)

    Returns:
        저장 결과 및 총 피드백 개수

    Raises:
        HTTPException: 파일 저장 실패 시 500 에러
    """
    try:
        # storage/cookies 디렉토리 경로
        cookies_dir = settings.storage_path / "cookies"
        cookies_dir.mkdir(parents=True, exist_ok=True)

        # 파일명: feedbacks.json (모든 피드백을 하나의 파일에 누적)
        feedback_file = cookies_dir / "feedbacks.json"

        # 기존 피드백 읽기
        if feedback_file.exists():
            with open(feedback_file, "r", encoding="utf-8") as f:
                feedbacks = json.load(f)
        else:
            feedbacks = []

        # 새 피드백 추가
        feedbacks.append({
            "query": feedback.query,
            "response": feedback.response,
            "feedback": feedback.feedback,
            "llm_type": feedback.llm_type,
            "timestamp": feedback.timestamp,
            "user": feedback.user
        })

        # 파일에 저장
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(feedbacks, f, ensure_ascii=False, indent=2)

        return FeedbackResponse(
            status="success",
            message="피드백이 저장되었습니다",
            total_feedbacks=len(feedbacks)
        )

    except Exception as e:
        logger.error(f"Feedback Save Error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )


# ==================== Query Route ====================

@router.post("/query/stream")
@limiter.limit("10/minute")
async def query_data_stream(
    request: Request,
    query_req: QueryRequest,
    _: bool = Depends(verify_api_key),
    rag_service: RAGService = Depends(get_rag_service)
) -> StreamingResponse:
    """
    RAG를 사용한 자연어 질의 처리 (스트리밍)

    Why: 사용자의 자연어 질문에 대해 RAG(Retrieval-Augmented Generation)를 사용하여
         관련 문서를 검색하고, LLM이 생성하는 답변을 실시간 스트리밍으로 제공합니다.
         FAISS 벡터 검색과 Neo4j 그래프 탐색을 결합하여 더 풍부한 컨텍스트를 제공합니다.

    Technical Flow:
        1단계: FAISS 벡터 검색으로 관련 문서 찾기
        2단계: Neo4j 그래프 탐색으로 관련 문서 추가
        3단계: 검색 결과를 Frontend에 스트리밍 전송
        4단계: LLM이 생성하는 답변을 토큰 단위로 스트리밍

    Args:
        request: FastAPI Request (rate limiting용)
        query_req: 쿼리 요청 (message, llm_type)
        _: API 키 검증 (의존성 주입)
        rag_service: RAG 서비스 인스턴스 (의존성 주입)

    Returns:
        NDJSON 형식의 스트리밍 응답

    Note:
        - Ollama 사용 시 스트리밍으로 실시간 응답
        - OpenAI는 일반 응답 반환
    """

    async def generate() -> AsyncGenerator[str, None]:
        """
        스트리밍 응답 생성기

        Why: NDJSON 형식으로 검색 결과와 LLM 응답을 실시간 전송합니다.
        """
        try:
            # 1단계: 검색 (FAISS + Neo4j 통합)
            search_results = rag_service.search_with_relations(
                query_req.message,
                top_k=3
            )

            main_docs = search_results["main_results"]
            related_docs = search_results["related_docs"]
            context_insights = search_results["context_insights"]

            # 2단계: 메인 검색 결과 전송 (Domain Layer - Pure Function)
            yield create_documents_message(
                documents=main_docs,
                total_count=len(rag_service.documents)
            )

            # 3단계: Neo4j 관련 문서 전송 (있는 경우)
            if should_send_related_documents(related_docs, context_insights):
                yield create_related_documents_message(
                    related_docs=related_docs,
                    insights=context_insights
                )

            # 4단계: 스트리밍 응답 생성 (메인 + 관련 문서 모두 컨텍스트로 사용)
            all_context_docs = main_docs + related_docs

            generator = rag_service.generate_response(
                query_req.message,
                all_context_docs,
                relationships=context_insights,  # Neo4j 컨텍스트를 관계 정보로 전달
                llm_type=query_req.llm_type,
                prompt_mode="standard"
            )

            # 5단계: LLM 토큰 스트리밍 (Domain Layer - Pure Function)
            for chunk in generator:
                yield create_token_message(chunk)

            # 6단계: 완료 신호 (Domain Layer - Pure Function)
            yield create_done_message()

        except Exception as e:
            logger.error(f"Streaming Error: {e}")
            yield create_error_message("Internal Processing Error")

    return StreamingResponse(generate(), media_type="application/x-ndjson")

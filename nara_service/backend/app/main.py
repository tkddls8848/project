"""
FastAPI Main Application

Why: NARA Service의 백엔드 API 서버 진입점입니다.
     서비스 초기화, CORS 설정, 라우터 등록, Rate Limiting 등을
     중앙에서 관리합니다.
"""
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.services.rag_service import RAGService
from app.services.search_rag_service import SearchRAGService
from app.services.prometheus_service import PrometheusService
from app.services.ai_relationship_inferrer import AIRelationshipInferrer
from app.services.relationship_chat_service import RelationshipChatService
from app.services.didyouknow_service import DidYouKnowService, FactCategory
from app.services.neo4j_service import Neo4jService
from app.services.insight_engine import InsightEngine
from app.routers import (
    docs,
    general,
    detail,
    prometheus,
    relationship_chat,
    search_rag,
    didyouknow,
    insights
)
from app.domain.common.dependencies import (
    set_rag_service,
    set_search_rag_service,
    set_prometheus_service,
    set_ai_inferrer,
    set_chat_service,
    set_didyouknow_service,
    set_neo4j_service,
    set_insight_engine
)

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== FastAPI App ====================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    docs_url=None,  # 기본 docs 비활성화 (커스텀 라우트로 대체)
    redoc_url=None,  # 기본 redoc 비활성화 (커스텀 라우트로 대체)
)

# Rate Limiter setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 서비스 초기화
# Why: 타입 안전성을 위해 Optional로 명시합니다.
#      서비스들은 startup_event에서 초기화됩니다.
rag_service: Optional[RAGService] = None
search_rag_service: Optional[SearchRAGService] = None
prometheus_service: Optional[PrometheusService] = None
ai_inferrer: Optional[AIRelationshipInferrer] = None
relationship_chat_service: Optional[RelationshipChatService] = None
didyouknow_service: Optional[DidYouKnowService] = None
neo4j_service: Optional[Neo4jService] = None
insight_engine: Optional[InsightEngine] = None

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    max_age=600,
)


# ==================== App Events ====================
@app.on_event("startup")
async def startup_event() -> None:
    """
    앱 시작 시 서비스 초기화

    Why: 서버가 시작될 때 한 번만 실행되어 무거운 초기화 작업을 수행합니다.
         RAG 모델 로딩, 인덱스 구축 등이 여기서 진행됩니다.

    Technical Flow:
        1. RAG 서비스 초기화 (임베딩 모델 로딩)
        2. Search RAG 서비스 초기화 (FAISS 인덱스 구축)
        3. Prometheus 서비스 초기화
        4. AI Relationship Inferrer 초기화 (LLM 기반 관계 추론)
        5. Relationship Chat 서비스 초기화 (NotebookLM 스타일)
        6. Did You Know 서비스 초기화
        7. 각 라우터에 서비스 주입

    Note: 예외가 발생해도 서버는 계속 실행됩니다 (Graceful Degradation).
          RAG 기능만 비활성화되고 다른 API는 정상 동작합니다.
    """
    global rag_service, search_rag_service, prometheus_service, ai_inferrer, relationship_chat_service, didyouknow_service, neo4j_service, insight_engine
    try:
        print("=" * 50)
        print("Initializing Services...")

        # RAG Service
        rag_service = RAGService(
            openai_api_key=settings.OPENAI_API_KEY or None,
            ollama_url=settings.OLLAMA_URL
        )

        # Search RAG Service (FAISS-based chunk search)
        search_rag_service = SearchRAGService(storage_path=settings.storage_path)

        # Prometheus Service
        prometheus_service = PrometheusService(storage_path=settings.storage_path)

        # AI Relationship Inferrer
        ai_inferrer = AIRelationshipInferrer(
            openai_api_key=settings.OPENAI_API_KEY or None,
            ollama_url=settings.OLLAMA_URL
        )

        # Relationship Chat Service (NotebookLM Style) - Ollama gemma3:4b
        relationship_chat_service = RelationshipChatService(
            ollama_url=settings.OLLAMA_URL,
            model="gemma3:4b"
        )

        # Did You Know Service - 공공데이터 흥미로운 사실 생성
        didyouknow_service = DidYouKnowService(
            rag_service=rag_service,
            ollama_url=settings.OLLAMA_URL
        )

        # Neo4j Service (for Insights)
        try:
            neo4j_service = Neo4jService(
                uri=settings.NEO4J_URI,
                username=settings.NEO4J_USERNAME,
                password=settings.NEO4J_PASSWORD
            )
            logger.info("Neo4j Service initialized successfully")

            # Insight Engine (Advanced Graph Analysis)
            insight_engine = InsightEngine(neo4j_service=neo4j_service)
            logger.info("Insight Engine initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Neo4j/Insight Engine: {e}")
            logger.warning("Prometheus insights functionality will be unavailable")
            neo4j_service = None
            insight_engine = None

        # 서비스 주입 (Domain Layer - Dependency Injection)
        set_rag_service(rag_service)
        set_search_rag_service(search_rag_service)
        set_prometheus_service(prometheus_service)
        set_ai_inferrer(ai_inferrer)
        set_chat_service(relationship_chat_service)
        set_didyouknow_service(didyouknow_service)

        # Neo4j and Insight Engine (optional - only if initialized successfully)
        if neo4j_service:
            set_neo4j_service(neo4j_service)
        if insight_engine:
            set_insight_engine(insight_engine)

        # Did You Know 초기 콘텐츠 생성 (facts.json 없을 경우만)
        from pathlib import Path
        facts_file = Path("storage/didyouknow/facts.json")
        if not facts_file.exists():
            logger.info("Generating initial Did You Know facts...")
            try:
                initial_facts = didyouknow_service.generate_batch({
                    FactCategory.API_INTRODUCTION: 30,
                    FactCategory.PROVIDER_INTRO: 15,
                    FactCategory.USAGE_TIP: 15
                })
                didyouknow_service.save_facts(initial_facts)
                logger.info(f"Generated {len(initial_facts)} initial facts")
            except Exception as e:
                logger.error(f"Failed to generate initial facts: {e}")
                # 실패해도 서버는 계속 실행 (Graceful Degradation)
        else:
            logger.info("Did You Know facts already exist, skipping generation")

        print("Services initialized successfully")
        print("=" * 50)
    except Exception as e:
        import traceback
        print(f"Failed to initialize services: {e}")
        print("Full traceback:")
        traceback.print_exc()
        print("Service will continue without RAG functionality")
        print("=" * 50)


# ==================== Include Routers ====================
app.include_router(docs.router)
app.include_router(general.router)
app.include_router(detail.router)
app.include_router(prometheus.router)
app.include_router(relationship_chat.router)
app.include_router(search_rag.router)
app.include_router(didyouknow.router)
app.include_router(insights.router)

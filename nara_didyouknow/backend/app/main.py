"""
Did You Know Service - FastAPI Main Application
"""
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from pathlib import Path

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.services.didyouknow_service import DidYouKnowService, FactCategory
from app.routers import didyouknow
from app.domain.common.dependencies import set_didyouknow_service

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== FastAPI App ====================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
)

# Rate Limiter setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 서비스 초기화
didyouknow_service: Optional[DidYouKnowService] = None

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
    """앱 시작 시 서비스 초기화"""
    global didyouknow_service
    try:
        print("=" * 50)
        print("Initializing Did You Know Service...")

        # Did You Know Service 초기화
        didyouknow_service = DidYouKnowService(
            ollama_url=settings.OLLAMA_URL
        )

        # 서비스 주입
        set_didyouknow_service(didyouknow_service)

        # index.json 없을 경우 경고
        if not didyouknow_service.documents:
            print("=" * 50)
            print("[WARNING] storage/index.json 파일이 없습니다.")
            print("API 문서 없이 서비스가 시작됩니다.")
            print("콘텐츠 생성 및 관련 API 매칭 기능이 비활성화됩니다.")
            print("index.json 파일을 storage/ 디렉토리에 추가해주세요.")
            print("=" * 50)

        # 초기 콘텐츠 생성 (facts.json 없을 경우만)
        facts_file = Path("storage/didyouknow/facts.json")
        if not facts_file.exists():
            logger.info("Generating initial Did You Know facts...")
            try:
                initial_facts = didyouknow_service.generate_batch({
                    FactCategory.API_INTRODUCTION: 10,
                    FactCategory.PROVIDER_INTRO: 5,
                    FactCategory.USAGE_TIP: 5
                })
                didyouknow_service.save_facts(initial_facts)
                logger.info(f"Generated {len(initial_facts)} initial facts")
            except Exception as e:
                logger.error(f"Failed to generate initial facts: {e}")
        else:
            logger.info("Did You Know facts already exist, skipping generation")

        print("Service initialized successfully")
        print("=" * 50)
    except Exception as e:
        import traceback
        print(f"Failed to initialize service: {e}")
        print("Full traceback:")
        traceback.print_exc()
        print("=" * 50)


# ==================== Include Routers ====================
app.include_router(didyouknow.router)


# ==================== Health Check ====================
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Did You Know Service",
        "version": settings.APP_VERSION,
        "status": "healthy"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

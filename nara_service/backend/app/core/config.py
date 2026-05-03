from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    APP_NAME: str = "NARA Service API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False  # Production: False, Development: True

    API_V1_PREFIX: str = "/api/v1"

    # CORS: 로컬 개발 및 프로덕션 배포용 기본 도메인
    # 중요: Railway 배포 시 환경 변수로 덮어쓰기 가능
    # 예시: ALLOWED_ORIGINS=http://localhost:3000,https://your-app.vercel.app
    # 와일드카드 지원: https://*.vercel.app
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,https://*.vercel.app,https://*.railway.app"

    # API Key (프론트엔드 인증용)
    # 주의: 프론트엔드 환경변수명을 NEXT_PUBLIC_으로 하면 브라우저에 노출됨
    # Railway 배포 시 반드시 강력한 랜덤 키로 설정!
    # 생성 방법: openssl rand -hex 32
    NEXT_API_ROUTE_KEY: str = "dev-api-key-change-in-production"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Ollama
    OLLAMA_URL: str = "http://localhost:11434"

    # Neo4j (for Insights - Prometheus only)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Swagger Docs Authentication (프로덕션에서 반드시 변경!)
    DOCS_USERNAME: str = "admin"
    DOCS_PASSWORD: str = "changeme"  # 배포 전 강력한 비밀번호로 변경 필수!
    ENABLE_DOCS: bool = False  # Production: False (보안), Development: True

    # Storage Path (Railway: /app/storage, Local: ../storage)
    STORAGE_PATH: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def storage_path(self) -> Path:
        """Storage 디렉토리 경로 반환 (환경에 따라 자동 설정)"""
        if self.STORAGE_PATH:
            return Path(self.STORAGE_PATH)

        # 1. 로컬 개발 환경 및 Docker (relative path)
        # Docker: /app/app/core/config.py -> /app/storage
        # Local: .../backend/app/core/config.py -> .../backend/storage
        local_path = Path(__file__).resolve().parent.parent.parent / "storage"
        if local_path.exists():
            return local_path

        # 2. Docker 환경 Fallback (혹시 경로 계산이 안 맞는 경우)
        if os.path.exists("/app/storage"):
            return Path("/app/storage")

        return local_path


settings = Settings()

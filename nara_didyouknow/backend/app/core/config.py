from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    APP_NAME: str = "Did You Know Service API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    API_V1_PREFIX: str = "/api/v1"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,https://*.vercel.app,https://*.railway.app"

    # API Key
    NEXT_API_ROUTE_KEY: str = "dev-api-key-change-in-production"

    # Ollama
    OLLAMA_URL: str = "http://localhost:11434"

    # Swagger Docs Authentication
    DOCS_USERNAME: str = "admin"
    DOCS_PASSWORD: str = "changeme"
    ENABLE_DOCS: bool = False

    # Storage Path
    STORAGE_PATH: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def storage_path(self) -> Path:
        """Storage 디렉토리 경로 반환"""
        if self.STORAGE_PATH:
            return Path(self.STORAGE_PATH)

        # 로컬 개발 환경
        local_path = Path(__file__).resolve().parent.parent.parent / "storage"
        if local_path.exists():
            return local_path

        # Docker 환경 Fallback
        if os.path.exists("/app/storage"):
            return Path("/app/storage")

        return local_path


settings = Settings()

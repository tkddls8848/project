"""Authentication & Authorization - 인증 및 권한 관리"""
from fastapi import HTTPException, Request, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

from app.core.config import settings

# HTTP Basic Authentication
security = HTTPBasic()


def verify_docs_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Swagger 문서 접근 인증"""
    correct_username = secrets.compare_digest(
        credentials.username, settings.DOCS_USERNAME
    )
    correct_password = secrets.compare_digest(
        credentials.password, settings.DOCS_PASSWORD
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


def verify_api_key(request: Request):
    """API Key 인증 (프론트엔드 요청 검증용)"""
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is required"
        )

    if not secrets.compare_digest(api_key, settings.NEXT_API_ROUTE_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )

    return True

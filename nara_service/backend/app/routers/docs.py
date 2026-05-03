"""Documentation Router - Swagger & ReDoc"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.security import HTTPBasicCredentials

from app.auth import verify_docs_credentials
from app.core.config import settings

router = APIRouter(tags=["documentation"])


@router.get("/docs", include_in_schema=False)
async def get_documentation(
    credentials: HTTPBasicCredentials = Depends(verify_docs_credentials)
) -> HTMLResponse:
    """Swagger UI (인증 필요)"""
    if not settings.ENABLE_DOCS:
        raise HTTPException(status_code=404, detail="Documentation not available")
    return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{settings.APP_NAME} - Swagger UI")


@router.get("/redoc", include_in_schema=False)
async def get_redoc(
    credentials: HTTPBasicCredentials = Depends(verify_docs_credentials)
) -> HTMLResponse:
    """ReDoc (인증 필요)"""
    if not settings.ENABLE_DOCS:
        raise HTTPException(status_code=404, detail="Documentation not available")
    return get_redoc_html(openapi_url="/openapi.json", title=f"{settings.APP_NAME} - ReDoc")


@router.get("/openapi.json", include_in_schema=False)
async def get_openapi_json(
    credentials: HTTPBasicCredentials = Depends(verify_docs_credentials),
    request: Request = None
) -> JSONResponse:
    """OpenAPI JSON (인증 필요)"""
    if not settings.ENABLE_DOCS:
        raise HTTPException(status_code=404, detail="Documentation not available")
    # app 객체를 request.app으로 가져오기 (순환 import 방지)
    return JSONResponse(request.app.openapi())

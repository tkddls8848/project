"""
의존성 주입 헬퍼 (FastAPI Depends)
"""
from typing import TYPE_CHECKING

from app.domain.common.service_registry import ServiceRegistry

if TYPE_CHECKING:
    from app.services.didyouknow_service import DidYouKnowService


def set_didyouknow_service(service: 'DidYouKnowService') -> None:
    """Did You Know 서비스 인스턴스를 주입합니다."""
    from app.services.didyouknow_service import DidYouKnowService
    ServiceRegistry.register(DidYouKnowService, service)


def get_didyouknow_service() -> 'DidYouKnowService':
    """Did You Know 서비스 인스턴스를 반환합니다."""
    from app.services.didyouknow_service import DidYouKnowService
    return ServiceRegistry.get(DidYouKnowService)

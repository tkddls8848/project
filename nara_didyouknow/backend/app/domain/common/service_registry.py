"""
Service Registry Pattern
"""
from typing import Dict, Type, TypeVar, Optional, cast
from fastapi import HTTPException

T = TypeVar('T')


class ServiceRegistry:
    """서비스 인스턴스를 타입 안전하게 관리하는 레지스트리"""
    _services: Dict[Type, object] = {}

    @classmethod
    def register(cls, service_type: Type[T], instance: T) -> None:
        """서비스 인스턴스를 등록합니다."""
        cls._services[service_type] = instance

    @classmethod
    def get(cls, service_type: Type[T]) -> T:
        """서비스 인스턴스를 반환합니다."""
        instance = cls._services.get(service_type)
        if instance is None:
            service_name = service_type.__name__
            raise HTTPException(
                status_code=503,
                detail=f"{service_name} not initialized. Please restart the server."
            )
        return cast(T, instance)

    @classmethod
    def get_optional(cls, service_type: Type[T]) -> Optional[T]:
        """서비스 인스턴스를 반환하되, 없으면 None을 반환합니다."""
        instance = cls._services.get(service_type)
        return cast(Optional[T], instance)

    @classmethod
    def clear(cls) -> None:
        """모든 서비스를 제거합니다."""
        cls._services.clear()

    @classmethod
    def is_registered(cls, service_type: Type) -> bool:
        """서비스가 등록되어 있는지 확인합니다."""
        return service_type in cls._services

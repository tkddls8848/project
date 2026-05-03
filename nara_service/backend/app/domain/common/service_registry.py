"""
Service Registry Pattern

Why: 서비스 인스턴스 관리를 중앙화하여 중복 코드를 제거합니다.
     타입 안전성을 유지하면서 DRY 원칙을 준수합니다.

CODING_RULES 준수:
    - DRY: setter/getter 중복 제거
    - Type Safety: Generic을 활용한 타입 안전성
    - Singleton: 서비스 레지스트리는 전역 단일 인스턴스
"""
from typing import Dict, Type, TypeVar, Optional, cast
from fastapi import HTTPException

T = TypeVar('T')


class ServiceRegistry:
    """
    서비스 인스턴스를 타입 안전하게 관리하는 레지스트리

    Why: 8개 서비스에 대한 중복된 setter/getter 코드를
         하나의 범용 레지스트리로 통합합니다.

    Example:
        >>> # 서비스 등록
        >>> ServiceRegistry.register(RAGService, rag_service_instance)

        >>> # 서비스 조회
        >>> rag = ServiceRegistry.get(RAGService)

        >>> # Optional 조회
        >>> rag_opt = ServiceRegistry.get_optional(RAGService)
    """
    _services: Dict[Type, object] = {}

    @classmethod
    def register(cls, service_type: Type[T], instance: T) -> None:
        """
        서비스 인스턴스를 등록합니다.

        Args:
            service_type: 서비스 클래스 타입
            instance: 서비스 인스턴스

        Example:
            >>> ServiceRegistry.register(RAGService, rag_instance)
        """
        cls._services[service_type] = instance

    @classmethod
    def get(cls, service_type: Type[T]) -> T:
        """
        서비스 인스턴스를 반환합니다.

        Args:
            service_type: 서비스 클래스 타입

        Returns:
            서비스 인스턴스

        Raises:
            HTTPException: 서비스가 등록되지 않은 경우 503 에러

        Example:
            >>> rag = ServiceRegistry.get(RAGService)
        """
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
        """
        서비스 인스턴스를 반환하되, 없으면 None을 반환합니다.

        Args:
            service_type: 서비스 클래스 타입

        Returns:
            서비스 인스턴스 또는 None

        Example:
            >>> rag = ServiceRegistry.get_optional(RAGService)
            >>> if rag:
            ...     rag.search(query)
        """
        instance = cls._services.get(service_type)
        return cast(Optional[T], instance)

    @classmethod
    def clear(cls) -> None:
        """
        모든 서비스를 제거합니다.

        Why: 주로 테스트에서 사용됩니다.
        """
        cls._services.clear()

    @classmethod
    def is_registered(cls, service_type: Type) -> bool:
        """
        서비스가 등록되어 있는지 확인합니다.

        Args:
            service_type: 서비스 클래스 타입

        Returns:
            등록 여부

        Example:
            >>> if ServiceRegistry.is_registered(RAGService):
            ...     print("RAG service is ready")
        """
        return service_type in cls._services

"""
Result Pattern 구현

Why: 예외(Exception)를 던지는 대신 성공/실패를 명시적으로 표현합니다.
     이를 통해 호출자가 에러 처리를 강제하고, 더 나은 에러 메시지를 제공합니다.

CODING_RULES 준수:
    - Error Handling (5장): Result Pattern 사용
    - Type Safety (4장): Generic을 활용한 타입 안전성
    - FP First: 불변성 유지 (dataclass frozen)

References:
    - Rust의 Result<T, E> 패턴
    - TypeScript의 { success: boolean, data?, error? } 패턴
"""
from typing import TypeVar, Generic, Optional
from dataclasses import dataclass

T = TypeVar('T')  # 성공 시 데이터 타입


@dataclass(frozen=True)  # 불변성 보장
class Result(Generic[T]):
    """
    작업 결과를 나타내는 타입입니다.

    Why: 예외를 던지는 대신 성공/실패를 값으로 반환하여
         에러 처리를 명시적으로 만들고, 타입 안전성을 보장합니다.

    Attributes:
        success: 작업 성공 여부
        data: 성공 시 반환 데이터 (success=True일 때만 존재)
        error: 실패 시 에러 메시지 (success=False일 때만 존재)
        error_code: 에러 코드 (분류 및 처리용)

    Example:
        >>> # 성공 케이스
        >>> result = Result.ok([1, 2, 3])
        >>> if result.success:
        ...     print(result.data)
        [1, 2, 3]

        >>> # 실패 케이스
        >>> result = Result.fail("Database connection failed", "DB_ERROR")
        >>> if not result.success:
        ...     print(f"{result.error_code}: {result.error}")
        DB_ERROR: Database connection failed
    """
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None

    @staticmethod
    def ok(data: T) -> 'Result[T]':
        """
        성공 결과를 생성합니다.

        Args:
            data: 성공 시 반환할 데이터

        Returns:
            success=True인 Result 인스턴스

        Example:
            >>> result = Result.ok({"id": 123, "name": "API"})
            >>> result.success
            True
            >>> result.data
            {'id': 123, 'name': 'API'}
        """
        return Result(success=True, data=data)

    @staticmethod
    def fail(error: str, error_code: str = "UNKNOWN_ERROR") -> 'Result[T]':
        """
        실패 결과를 생성합니다.

        Args:
            error: 사용자 친화적인 에러 메시지
            error_code: 에러 코드 (분류 및 로깅용)

        Returns:
            success=False인 Result 인스턴스

        Example:
            >>> result = Result.fail(
            ...     "Invalid query parameter",
            ...     "VALIDATION_ERROR"
            ... )
            >>> result.success
            False
            >>> result.error_code
            'VALIDATION_ERROR'
        """
        return Result(success=False, error=error, error_code=error_code)

    def unwrap(self) -> T:
        """
        성공 시 데이터를 반환하고, 실패 시 예외를 발생시킵니다.

        Why: Result를 명시적으로 체크하지 않고 데이터를 가져올 때 사용합니다.
             하지만 가급적 if result.success로 체크하는 것을 권장합니다.

        Returns:
            성공 시 data

        Raises:
            ValueError: 실패한 Result를 unwrap하려고 할 때

        Example:
            >>> result = Result.ok(42)
            >>> result.unwrap()
            42

            >>> result = Result.fail("Error occurred")
            >>> result.unwrap()  # doctest: +SKIP
            Traceback (most recent call last):
                ...
            ValueError: Cannot unwrap failed Result: Error occurred
        """
        if not self.success:
            raise ValueError(f"Cannot unwrap failed Result: {self.error}")
        return self.data  # type: ignore

    def unwrap_or(self, default: T) -> T:
        """
        성공 시 데이터를 반환하고, 실패 시 기본값을 반환합니다.

        Args:
            default: 실패 시 반환할 기본값

        Returns:
            성공 시 data, 실패 시 default

        Example:
            >>> result = Result.ok([1, 2, 3])
            >>> result.unwrap_or([])
            [1, 2, 3]

            >>> result = Result.fail("Error")
            >>> result.unwrap_or([])
            []
        """
        if self.success:
            return self.data  # type: ignore
        return default


# 공통 에러 코드 상수
class ErrorCode:
    """
    표준 에러 코드 정의

    Why: 일관된 에러 코드를 사용하여 Frontend에서
         에러 타입별로 적절한 UI를 표시할 수 있습니다.
    """
    # 4xx Client Errors
    VALIDATION_ERROR = "VALIDATION_ERROR"           # 입력 검증 실패
    NOT_FOUND = "NOT_FOUND"                         # 리소스 없음
    UNAUTHORIZED = "UNAUTHORIZED"                   # 인증 필요
    FORBIDDEN = "FORBIDDEN"                         # 권한 없음
    INVALID_PARAMS = "INVALID_PARAMS"               # 잘못된 파라미터

    # 5xx Server Errors
    INTERNAL_ERROR = "INTERNAL_ERROR"               # 내부 서버 오류
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"     # DB 연결 실패
    DB_QUERY_ERROR = "DB_QUERY_ERROR"               # DB 쿼리 실패
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"     # 서비스 사용 불가
    TIMEOUT_ERROR = "TIMEOUT_ERROR"                 # 타임아웃

    # External Service Errors
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"       # 외부 API 오류
    LLM_ERROR = "LLM_ERROR"                         # LLM 호출 오류
    EMBEDDING_ERROR = "EMBEDDING_ERROR"             # 임베딩 생성 오류


# HTTP 상태 코드 매핑
ERROR_CODE_TO_HTTP_STATUS = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.INVALID_PARAMS: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.DB_CONNECTION_ERROR: 503,
    ErrorCode.DB_QUERY_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.TIMEOUT_ERROR: 504,
    ErrorCode.EXTERNAL_API_ERROR: 502,
    ErrorCode.LLM_ERROR: 500,
    ErrorCode.EMBEDDING_ERROR: 500,
}


def get_http_status_from_error_code(error_code: str) -> int:
    """
    에러 코드에 해당하는 HTTP 상태 코드를 반환합니다.

    Args:
        error_code: 에러 코드

    Returns:
        HTTP 상태 코드 (기본값: 500)

    Example:
        >>> get_http_status_from_error_code(ErrorCode.NOT_FOUND)
        404
        >>> get_http_status_from_error_code(ErrorCode.DB_CONNECTION_ERROR)
        503
        >>> get_http_status_from_error_code("UNKNOWN")
        500
    """
    return ERROR_CODE_TO_HTTP_STATUS.get(error_code, 500)

"""
Query Result Pattern

Explicit success/failure representation for query operations.

Design Decision:
- Result Pattern over exceptions for expected failures
- Explicit error codes for better error handling
- Type-safe generic result wrapper
- Follows CODING_RULES Rule 5: Error Handling - "Prefer Result Pattern"
"""
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel
from enum import Enum


T = TypeVar('T')


class ErrorCode(str, Enum):
    """
    Error codes for query operations

    Design Decision:
    - Specific error codes allow different handling strategies
    - HTTP status codes can be mapped from these
    """
    NEO4J_CONNECTION_ERROR = "NEO4J_CONNECTION_ERROR"
    NEO4J_QUERY_ERROR = "NEO4J_QUERY_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class QueryResult(BaseModel, Generic[T]):
    """
    Query result wrapper

    Wraps query results with success/failure information.

    Example Success:
        result = QueryResult.ok(data=SearchResult(...))
        if result.success:
            return result.data

    Example Failure:
        result = QueryResult.fail(
            error="Connection timeout",
            code=ErrorCode.NEO4J_CONNECTION_ERROR
        )
        if not result.success:
            logger.error(f"{result.error_code}: {result.error}")

    Design Decision:
    - Generic type T allows type-safe data access
    - Factory methods (ok/fail) provide clear construction
    - Pydantic enables serialization for API responses
    """
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[ErrorCode] = None

    class Config:
        arbitrary_types_allowed = True

    @staticmethod
    def ok(data: T) -> 'QueryResult[T]':
        """
        Create a successful result

        Args:
            data: The result data

        Returns:
            QueryResult with success=True
        """
        return QueryResult(success=True, data=data)

    @staticmethod
    def fail(error: str, code: ErrorCode = ErrorCode.UNKNOWN_ERROR) -> 'QueryResult[T]':
        """
        Create a failed result

        Args:
            error: Error message
            code: Error code for categorization

        Returns:
            QueryResult with success=False
        """
        return QueryResult(success=False, error=error, error_code=code)

    def unwrap(self) -> T:
        """
        Unwrap the result data

        Returns:
            The data if success=True

        Raises:
            ValueError: If success=False

        Design Decision:
        - Similar to Rust's unwrap()
        - Forces explicit error handling
        """
        if not self.success:
            raise ValueError(f"Cannot unwrap failed result: {self.error}")
        return self.data

    def unwrap_or(self, default: T) -> T:
        """
        Unwrap with default value

        Args:
            default: Default value if failed

        Returns:
            Data if success, otherwise default
        """
        if self.success:
            return self.data
        return default

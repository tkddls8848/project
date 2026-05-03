"""
Query Domain Models

Pydantic models for type-safe query operations.
"""

from .filters import (
    FilterOperator,
    NodeFilter,
    RelationshipFilter,
    SearchQuery
)
from .result import (
    ErrorCode,
    QueryResult
)
from .search_result import (
    DocumentInfo,
    SearchResult
)

__all__ = [
    "FilterOperator",
    "NodeFilter",
    "RelationshipFilter",
    "SearchQuery",
    "ErrorCode",
    "QueryResult",
    "DocumentInfo",
    "SearchResult",
]

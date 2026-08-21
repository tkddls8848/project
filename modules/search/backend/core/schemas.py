from typing import Any

from pydantic import BaseModel, Field

from . import config


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=config.MAX_QUERY_LENGTH)
    top_k: int = Field(default=config.DEFAULT_TOP_K, ge=1, le=config.MAX_TOP_K)
    use_vector: bool = True


class SearchResponse(BaseModel):
    query: str
    results: list[dict[str, Any]]
    diagnostics: dict[str, Any]

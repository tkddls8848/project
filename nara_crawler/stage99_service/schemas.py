from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=300)
    top_k: int = Field(default=5, ge=1, le=20)
    use_vector: bool = False


class SearchResponse(BaseModel):
    query: str
    results: list[dict[str, Any]]
    diagnostics: dict[str, Any]

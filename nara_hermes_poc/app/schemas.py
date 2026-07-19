"""Public request and response schemas for the PoC."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DesignRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    use_vector: bool = True
    selected_service_ids: list[str] = Field(default_factory=list, max_length=3)
    compose: bool = True


class StageRecord(BaseModel):
    name: Literal["search", "detail", "relations", "compose"]
    status: Literal["running", "completed", "skipped", "failed"]
    message: str


class DesignResponse(BaseModel):
    query: str
    selected_service_ids: list[str]
    search: dict[str, Any]
    details: list[dict[str, Any]]
    relations: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    stages: list[StageRecord]
    warnings: list[str] = Field(default_factory=list)


class AgentRunRequest(DesignRequest):
    """A bounded, read-only Hermes run request."""


class AgentEvent(BaseModel):
    sequence: int
    name: Literal["queued", "agent", "search", "detail", "relations", "compose", "completed", "failed", "cancelled"]
    status: Literal["queued", "running", "completed", "skipped", "failed", "cancelled"]
    message: str


class AgentRunResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    query: str
    events: list[AgentEvent] = Field(default_factory=list)
    result: DesignResponse | None = None
    hermes: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

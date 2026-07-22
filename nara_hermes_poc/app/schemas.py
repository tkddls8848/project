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
    name: Literal["search", "detail", "relations", "compose", "critic"]
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
    name: Literal["queued", "agent", "search", "detail", "relations", "compose", "freshness", "critic", "completed", "failed", "cancelled"]
    status: Literal["queued", "running", "completed", "skipped", "failed", "cancelled"]
    message: str


class CriticFinding(BaseModel):
    check: str
    severity: Literal["info", "unverified", "violation"]
    target: str
    message: str
    evidence: list[str] = Field(default_factory=list)


class CriticReport(BaseModel):
    verdict: Literal["pass", "evidence_gap", "contradiction", "skipped", "failed"]
    findings: list[CriticFinding] = Field(default_factory=list)
    deterministic: bool
    hermes: dict[str, Any] = Field(default_factory=dict)


class DocumentFreshness(BaseModel):
    """Read-only comparison of crawler manifests with the active index."""

    service_id: str
    status: Literal["fresh", "stale", "unverified"]
    message: str
    index_built_at: str | None = None
    latest_crawl_at: str | None = None
    checksum: str | None = None


class AgentRunResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    query: str
    events: list[AgentEvent] = Field(default_factory=list)
    result: DesignResponse | None = None
    hermes: dict[str, Any] = Field(default_factory=dict)
    critic: CriticReport | None = None
    freshness: list[DocumentFreshness] = Field(default_factory=list)
    error: str | None = None